from __future__ import annotations

import hmac
import json
import logging
import os
import threading
import time
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from .agent_telegram import AgentTelegramService
from .chat import ChatSession
from .detect import is_suspicious, scan_text
from .events import sse_bytes
from .llm import KiloClient
from .llm_providers import ProviderConfig, list_providers, validate_api_key
from .llm_providers import chat_completion as provider_chat_completion
from .memory import MemoryManager
from .multipart_parse import parse_multipart
from .normalize import (
    normalize_api_key,
    normalize_current_evidence_id,
    normalize_evidence_id,
)
from .ocr import SUPPORTED_TYPES, analyze_image, ocr_runtime_status
from .operator import resolve_operator
from .pipeline import EvidencePipeline
from .planner import ToolPlanner
from .rag import (
    RAGConfig,
    chunk_text,
    extract_text_from_file,
    ingest_knowledge_source,
    search_agent_knowledge,
)
from .ratelimit import RateLimiter, make_ocr_limiter, make_upload_limiter
from .response_cache import ReadResponseCache, cached_get
from .settings import Settings, load_settings
from .store import AgentStore, EvidenceStore, UploadedFile, normalize_telegram_timestamp
from .telegram import TelegramWebhook
from .watermark import decode_watermark, parse_token
from .tools import ExamshieldToolRegistry
from .workers import AnalysisTask, AnalysisWorkerPool


def _error_payload(message: str) -> dict[str, str]:
    """Build a safe error body. Never includes exception internals (audit §6.3).

    Handlers must pass a fixed, client-safe message rather than `str(exc)`,
    which can leak stack traces or internal identifiers to clients.
    """
    return {"error": message}


def resolve_cors_headers(settings: Settings, origin: str | None) -> dict[str, str]:
    """Resolve CORS response headers against an allow-list.

    Replaces the old behaviour of blindly echoing `cors_origin` (which defaulted
    to `*`). Now the request's `Origin` is only reflected when it is explicitly
    present in the allow-list. `EXAMSHIELD_AI_CORS_ORIGIN` accepts a
    comma/space-separated list of allowed origins; an explicit `*` opts back into
    allow-all (discouraged). With an empty allow-list (the new default) no
    `Access-Control-Allow-Origin` header is emitted.
    """
    allowed = [o.strip() for o in (settings.cors_origin or "").split(",") if o.strip()]
    if origin and ("*" in allowed or origin in allowed):
        return {"Access-Control-Allow-Origin": origin, "Vary": "Origin"}
    return {}


# ── Backend API authentication (audit §2.2) ───────────────────────────────────
# A shared secret gate between the Vercel frontend proxy and the Render backend.
# The frontend sends `X-Examshield-Api-Key` on every upstream call; an
# `Authorization: Bearer <secret>` is also accepted. Enforced only when a secret
# is configured — when it is empty the gate is disabled (dev/offline) with a
# loud startup warning, mirroring the `EXAMSHIELD_AI_MASTER_KEY` fallback.
API_AUTH_HEADER = "X-Examshield-Api-Key"
# Routes that must never require the backend secret:
#  - /health is the Render health check.
#  - /telegram/webhook and /telegram/events are called directly by Telegram's
#    servers and carry their own TELEGRAM_WEBHOOK_SECRET validation; gating them
#    here would break inbound Telegram delivery.
API_AUTH_EXEMPT = {"/health", "/", "/telegram/webhook", "/telegram/events"}


def is_path_exempt(path: str) -> bool:
    """Return True if *path* must never require the backend shared secret."""
    return path in API_AUTH_EXEMPT


def _bearer_secret(authorization: str | None) -> str | None:
    if not authorization:
        return None
    authorization = authorization.strip()
    if authorization.lower().startswith("bearer "):
        token = authorization[len("bearer "):].strip()
        return token or None
    return None


def is_authorized(headers: Any, secret: str, path: str) -> bool:
    """Decide whether a request may proceed.

    - No secret configured -> auth disabled (backward-compatible offline mode).
    - Exempt path -> always allowed (health check, Telegram inbound).
    - Otherwise the request must carry the matching shared secret, compared in
      constant time to avoid leaking the secret via timing.
    """
    if not secret:
        return True
    if is_path_exempt(path):
        return True
    provided = headers.get(API_AUTH_HEADER) or _bearer_secret(headers.get("Authorization"))
    return bool(provided) and hmac.compare_digest(provided, secret)


_UNAUTHORIZED_BODY = json.dumps({"error": "Unauthorized."}).encode("utf-8")


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

class ExamshieldAiHandler(BaseHTTPRequestHandler):
    server_version = "ExamshieldAi/0.1"
    settings: Settings
    store: EvidenceStore
    registry: ExamshieldToolRegistry
    client: KiloClient
    telegram: TelegramWebhook
    workers: AnalysisWorkerPool
    pipeline: EvidencePipeline
    memory: MemoryManager
    agent_store: AgentStore
    # Wired up on ConfiguredExamshieldAiHandler at startup (see make_handler).
    _get_cache: ReadResponseCache
    _ocr_limiter: RateLimiter
    _upload_limiter: RateLimiter

    def do_OPTIONS(self) -> None:
        self._send_empty(204)

    def do_HEAD(self) -> None:
        path = urlparse(self.path).path
        if path in {"/health", "/"}:
            self.send_response(200)
            self._cors_headers()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            return
        self.send_response(404)
        self.end_headers()

    def _authorize_request(self) -> bool:
        """Gate non-exempt routes behind the backend shared secret.

        Returns True when the request may proceed; returns False after writing a
        401 response (so the caller should `return` immediately).
        """
        path = urlparse(self.path).path
        if is_authorized(self.headers, self.settings.api_auth_secret, path):
            return True
        self.send_response(401)
        self._cors_headers()
        self.send_header("WWW-Authenticate", 'Bearer realm="examshield-api"')
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(_UNAUTHORIZED_BODY)))
        self.end_headers()
        self.wfile.write(_UNAUTHORIZED_BODY)
        return False

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if not self._authorize_request():
            return
        parts = [part for part in path.split("/") if part]
        if path == "/health":
            self._send_json(
                {
                    "status": "ok",
                    "service": "examshield-ai",
                    "model": self.settings.model,
                    "nimConfigured": self.client.configured,
                    "kiloConfigured": self.client.configured,
                    "tools": self.registry.names(),
                    "ocr": {
                        "endpoint": "/ocr/analyze",
                        "supportedTypes": sorted(SUPPORTED_TYPES.keys()),
                        "runtime": ocr_runtime_status(),
                        "workers": self.workers.stats(),
                    },
                    "uploadRoot": str(self.settings.upload_root),
                    "registryPath": str(self.settings.registry_path),
                    "storage": "supabase" if self.store.supabase_enabled else "local-json",
                    "memory": self.memory.status(),
                    "telegram": {
                        "webhookConfigured": self.telegram.configured,
                        "botTokenSet": bool(self.settings.telegram_bot_token),
                        "publicUrl": self.settings.public_url or "NOT SET",
                        "chatId": self.settings.telegram_chat_id or "NOT SET",
                        "adminChatId": self.settings.telegram_admin_chat_id or "NOT SET",
                    },
                    "ocrWorkers": self.workers.stats(),
                }
            )
            return
        if path == "/tools":
            self._send_json({"tools": self.registry.schemas()})
            return
        if path == "/evidence":
            self._send_json(cached_get(self._get_cache, self.path, self.store.list_evidence))
            return
        if len(parts) == 2 and parts[0] == "evidence":
            bundle = self.store.get_bundle(parts[1])
            self._send_json(bundle if bundle else {"error": "Evidence not found."}, status=200 if bundle else 404)
            return
        if path == "/alerts":
            self._send_json(
                cached_get(
                    self._get_cache,
                    self.path,
                    lambda: {"alerts": self.store.list_evidence()["alerts"]},
                )
            )
            return
        if len(parts) == 2 and parts[0] == "memory":
            self._get_memory(parts[1])
            return
        # Monitored Telegram groups
        if path == "/telegram/groups":
            self._send_json(
                cached_get(
                    self._get_cache,
                    self.path,
                    lambda: {"groups": self.store.list_monitored_groups()},
                )
            )
            return
        if path == "/telegram/status":
            self._get_telegram_status()
            return
        # Question Registry
        if path == "/registry":
            self._list_registry_papers()
            return
        if path == "/registry/stats":
            self._get_registry_stats()
            return
        # Issued watermark copies (preventive minting)
        if path == "/watermark/copies":
            self._list_watermark_copies()
            return
        if len(parts) == 2 and parts[0] == "registry":
            self._get_registry_paper(parts[1])
            return
        if len(parts) == 3 and parts[0] == "analysis" and parts[1] == "jobs":
            try:
                self._send_json(self.store.analysis_job_snapshot(parts[2]))
            except LookupError:
                self._send_json(_error_payload("Not found."), status=404)
            return
        # Community Agents
        if path == "/llm/providers":
            self._send_json(cached_get(self._get_cache, self.path, lambda: {"providers": list_providers()}))
            return
        if path == "/llm/validate":
            self._validate_llm_key()
            return
        if path == "/agents":
            self._list_agents()
            return
        if len(parts) == 2 and parts[0] == "agents":
            self._get_agent(parts[1])
            return
        if len(parts) == 3 and parts[0] == "agents" and parts[2] == "stats":
            self._get_agent_stats(parts[1])
            return
        if len(parts) == 3 and parts[0] == "agents" and parts[2] == "knowledge":
            self._list_knowledge_sources(parts[1])
            return
        if len(parts) == 3 and parts[0] == "agents" and parts[2] == "conversations":
            self._list_conversations(parts[1])
            return
        # Reports
        if path == "/reports/templates":
            self._send_json({
                "templates": [
                    {"id": "evidence", "name": "Evidence Report", "description": "Detailed forensic report for a specific evidence item."},
                    {"id": "summary", "name": "Dashboard Summary", "description": "High-level summary of all evidence, alerts, and investigations."},
                ]
            })
            return
        self._send_json({"error": "Not found"}, status=404)

    def do_POST(self) -> None:
        if self._reject_oversized_request():
            return
        path = urlparse(self.path).path
        if not self._authorize_request():
            return
        parts = [part for part in path.split("/") if part]

        if path in {"/ocr/analyze", "/analyze"}:
            self._run_ocr()
            return
        if path == "/llm/validate":
            self._validate_llm_key()
            return

        if path == "/evidence/upload":
            self._upload_evidence()
            return
        if path == "/analysis/jobs":
            self._create_analysis_job()
            return
        if len(parts) == 4 and parts[0] == "analysis" and parts[1] == "jobs" and parts[3] == "process":
            self._process_analysis_job(parts[2])
            return
        if path == "/telegram/events":
            self._ingest_telegram_event()
            return
        if path == "/telegram/webhook":
            self._ingest_telegram_webhook()
            return
        if path == "/telegram/register":
            self._register_telegram_webhook()
            return
        if path == "/telegram/groups":
            self._add_monitored_group()
            return
        if path == "/memory/ingest":
            self._memory_ingest()
            return
        if path == "/memory/search":
            self._memory_search()
            return
        if path == "/memory/correlate":
            self._memory_correlate()
            return
        if path == "/demo/reset":
            self._send_json(self.store.reset_demo_environment())
            return

        if path == "/telegram/chat":
            self._test_telegram_chat()
            return

        # Question Registry
        if path == "/registry":
            self._create_registry_paper()
            return
        if path == "/registry/reset":
            self._reset_registry()
            return
        if path == "/registry/match":
            self._match_evidence_to_registry()
            return
        # Issued watermark copies (preventive minting)
        if path == "/watermark/mint":
            self._mint_watermark()
            return
        if path == "/watermark/decode":
            self._decode_watermark()
            return

        if path == "/plan":
            self._run_plan()
            return

        if path == "/chat":
            self._run_chat()
            return
        # Community Agents
        if path == "/agents":
            self._create_agent()
            return
        if len(parts) == 3 and parts[0] == "agents" and parts[1] == "llm" and parts[2] == "validate":
            self._validate_llm_key()
            return
        if len(parts) == 3 and parts[0] == "agents" and parts[2] == "llm":
            self._upsert_agent_llm(parts[1])
            return
        if len(parts) == 3 and parts[0] == "agents" and parts[2] == "telegram":
            self._upsert_agent_telegram(parts[1])
            return
        if len(parts) == 3 and parts[0] == "agents" and parts[2] == "knowledge":
            self._create_knowledge_source(parts[1])
            return
        if len(parts) == 5 and parts[0] == "agents" and parts[2] == "knowledge" and parts[4] == "upload":
            self._upload_knowledge_files(parts[1], parts[3])
            return
        if len(parts) == 3 and parts[0] == "agents" and parts[2] == "test":
            self._test_agent(parts[1])
            return
        if len(parts) == 3 and parts[0] == "agents" and parts[2] == "deploy":
            self._deploy_agent(parts[1])
            return
        if path == "/telegram/verify-bot":
            self._verify_bot_token()
            return
        if path == "/reports/generate":
            self._generate_report()
            return

        self._send_json({"error": "Not found"}, status=404)

    def _run_ocr(self) -> None:
        # ── Rate limit ──
        if not self._rate_limit_check(self._ocr_limiter, "OCR"):
            return

        content_type = (self.headers.get("Content-Type") or "").split(";")[0].lower()
        suffix = SUPPORTED_TYPES.get(content_type)
        if not suffix:
            self._send_json(
                {
                    "status": "failed",
                    "error": "Only image/jpeg and image/png are supported by the unified OCR endpoint.",
                },
                status=200,
            )
            return

        try:
            content_length = int(self.headers.get("Content-Length") or "0")
        except ValueError:
            content_length = 0

        if content_length <= 0:
            self._send_json({"status": "failed", "error": "Image payload is required."}, status=400)
            return

        # ── Size enforcement ──
        max_bytes = self.settings.max_upload_bytes
        if max_bytes > 0 and content_length > max_bytes:
            self._send_json(
                {"status": "failed", "error": f"Image too large. Maximum is {max_bytes} bytes."},
                status=413,
            )
            return

        image_bytes = self.rfile.read(content_length)

        # ── Magic-byte validation ──
        magic_err = self._validate_image_magic(image_bytes, content_type)
        if magic_err:
            self._send_json({"status": "failed", "error": magic_err}, status=400)
            return

        self._send_json(analyze_image(image_bytes, suffix))

    def _upload_evidence(self) -> None:
        # ── Rate limit ──
        if not self._rate_limit_check(self._upload_limiter, "upload"):
            return
        try:
            uploaded = self._read_multipart_file("file")
            created = self.store.create_evidence(uploaded)
            self._send_json({"message": "Evidence Created", **created}, status=201)
        except Exception:
            self._send_json(_error_payload("Evidence upload failed."), status=400)

    def _create_analysis_job(self) -> None:
        payload = self._read_json()
        evidence_id = normalize_evidence_id(payload)
        async_mode = bool(payload.get("async"))
        if not evidence_id:
            self._send_json({"error": "evidenceId is required."}, status=400)
            return
        try:
            evidence = self.store.get_evidence_by_id(evidence_id)
            if not evidence:
                raise LookupError("Evidence not found.")
            if evidence.get("fileType") == "text/plain":
                self._send_json({"error": "Text-only evidence does not require OCR."}, status=400)
                return

            existing_job = self.store.get_active_job_for_evidence(evidence_id)
            if existing_job:
                self._send_json(
                    {
                        "message": "Analysis Already Queued",
                        "evidence": evidence,
                        "job": existing_job,
                    }
                )
                return

            queued = self.store.create_analysis_job(evidence_id)
            job = queued["job"]
            if async_mode:
                submitted = self.pipeline.queue_media_analysis(
                    created={"evidence": evidence, "activity": [queued["activity"]]},
                    detection={"score": 0, "categories": []},
                    text=None,
                    chat_id=str(evidence.get("telegramChatId") or ""),
                    message={},
                    ocr_runner=analyze_image,
                    job=job,
                )
                if not submitted:
                    submitted = job
                self._send_json(
                    {
                        "message": "Analysis Queued",
                        "evidence": evidence,
                        "job": submitted,
                        "activity": [queued["activity"]],
                        "async": True,
                    },
                    status=202,
                )
                return

            self._send_json(
                {
                    "message": "Analysis Queued",
                    "evidence": evidence,
                    "job": job,
                    "activity": [queued["activity"]],
                }
            )
        except LookupError:
            self._send_json(_error_payload("Not found."), status=404)
        except Exception:
            self._send_json(_error_payload("Analysis failed."), status=400)

    def _process_analysis_job(self, job_id: str) -> None:
        try:
            job = self.store.get_analysis_job(job_id)
            if not job:
                self._send_json({"error": "Analysis job not found."}, status=404)
                return
            if job.get("status") == "completed":
                self._send_json(self.store.analysis_job_snapshot(job_id))
                return
            if job.get("status") == "failed":
                self._send_json(self.store.analysis_job_snapshot(job_id))
                return
            if job.get("status") == "processing" or self.workers.is_job_active(job_id):
                snapshot = self.store.analysis_job_snapshot(job_id)
                snapshot["message"] = "Analysis In Progress"
                self._send_json(snapshot, status=202)
                return

            evidence_id = normalize_evidence_id(job)
            if self.workers.is_evidence_active(evidence_id):
                snapshot = self.store.analysis_job_snapshot(job_id)
                snapshot["message"] = "Analysis In Progress"
                self._send_json(snapshot, status=202)
                return

            def on_complete(_analysis: dict[str, Any], error: Exception | None) -> None:
                if error:
                    try:
                        self.store.fail_analysis_job(job_id, str(error) or "Background OCR failed")
                    except Exception as fail_exc:
                        logger.error("Failed to mark job %s failed: %s", job_id, fail_exc)
                    return
                try:
                    self.memory.ingest_from_analysis(_analysis, notify=True)
                except Exception as memory_exc:
                    logger.warning("Memory correlation failed for manual job %s: %s", job_id, memory_exc)

            submitted = self.workers.submit(
                self.store,
                AnalysisTask(job_id=job_id, evidence_id=evidence_id),
                analyze_image,
                on_complete=on_complete,
            )
            if submitted is None:
                snapshot = self.store.analysis_job_snapshot(job_id)
                snapshot["message"] = "Analysis In Progress"
                self._send_json(snapshot, status=202)
                return

            snapshot = self.store.analysis_job_snapshot(job_id)
            snapshot["message"] = "Analysis In Progress"
            self._send_json(snapshot, status=202)
        except LookupError:
            self._send_json(_error_payload("Not found."), status=404)
        except Exception:
            self._send_json(_error_payload("Analysis failed."), status=400)

    def _ingest_telegram_event(self) -> None:
        try:
            content_type = self.headers.get("Content-Type") or ""
            if "multipart/form-data" in content_type:
                fields = self._read_multipart()
                file_field = fields.get("file")
                uploaded = file_field if isinstance(file_field, UploadedFile) else None
                message_id = require_text(fields, "messageId")
                chat_id = require_text(fields, "chatId")
                timestamp = normalize_telegram_timestamp(fields.get("timestamp"))
                text = optional_text(fields.get("text"))
            else:
                payload = self._read_json()
                message_id = str(payload.get("messageId") or "").strip()
                chat_id = str(payload.get("chatId") or "").strip()
                if not message_id or not chat_id:
                    raise ValueError("messageId and chatId are required.")
                timestamp = normalize_telegram_timestamp(payload.get("timestamp"))
                text = optional_text(payload.get("text"))
                uploaded = None

            detection = scan_text(text)
            created = self.store.create_telegram_event(
                message_id=message_id,
                chat_id=chat_id,
                timestamp=timestamp,
                text=text,
                file=uploaded,
                detection=detection,
            )
            detection_payload = {
                "score": detection["score"],
                "categories": detection["categories"],
                "isSuspicious": is_suspicious(detection),
            }
            if created["duplicate"]:
                self._send_json(
                    {
                        "message": "Telegram Event Already Processed",
                        "telegramEvent": created["telegramEvent"],
                        "evidence": created["evidence"],
                        "activity": created["activity"],
                    }
                )
                return
            if not created["evidence"]:
                self._send_json(
                    {
                        "message": "Telegram Event Stored",
                        "telegramEvent": created["telegramEvent"],
                        "evidence": None,
                        "activity": created["activity"],
                        "detection": detection_payload,
                    },
                    status=202,
                )
                return

            message = {"message_id": message_id, "chat": {"id": chat_id}, "text": text}
            if created["evidence"].get("fileType") == "text/plain":
                alert_sent = self.pipeline.process_text_only_alert(
                    created, detection, text, chat_id, message
                )
                latest_evidence = (
                    self.store.get_evidence_by_id(normalize_evidence_id(created["evidence"]))
                    or created["evidence"]
                )
                self._send_json(
                    {
                        "message": "Suspicious Text Captured",
                        "telegramEvent": created["telegramEvent"],
                        "evidence": latest_evidence,
                        "detection": detection_payload,
                        "alertSent": alert_sent,
                        "activity": created["activity"],
                    },
                    status=201,
                )
                return

            job = self.pipeline.queue_media_analysis(
                created=created,
                detection=detection,
                text=text,
                chat_id=chat_id,
                message=message,
                ocr_runner=analyze_image,
            )
            self._send_json(
                {
                    "message": "Telegram Evidence Queued For Analysis",
                    "telegramEvent": created["telegramEvent"],
                    "evidence": created["evidence"],
                    "job": job,
                    "detection": detection_payload,
                    "async": True,
                    "activity": created["activity"],
                },
                status=202,
            )
        except Exception:
            self._send_json(_error_payload("Telegram event ingestion failed."), status=400)

    def _ingest_telegram_webhook(self) -> None:
        secret = self.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if not self.telegram.validate_secret(secret):
            logger.warning(f"Webhook secret mismatch: expected={'SET' if self.telegram.settings.telegram_webhook_secret else 'NONE'}, received={'SET' if secret else 'NONE'}")
            self._send_json({"error": "Invalid Telegram webhook secret."}, status=401)
            return
        try:
            update = self._read_json()
            logger.info(f"Webhook received: keys={list(update.keys())}")
            result = self.telegram.process_update(
                update, self.store, analyze_image, pipeline=self.pipeline
            )
            logger.info(f"Webhook processed: {result.get('message')}, processed={result.get('processed')}")
            self._send_json(result)
        except Exception as exc:
            logger.error(f"Webhook processing failed: {type(exc).__name__}: {exc}", exc_info=True)
            self._send_json(_error_payload("Telegram webhook failed."), status=400)

    def _register_telegram_webhook(self) -> None:
        payload = self._read_json()
        url_override = str(payload.get("url") or "").strip()
        try:
            if url_override:
                self.telegram = TelegramWebhook(replace(self.settings, public_url=url_override))
            self.telegram.register()
            self._send_json({
                "message": "Telegram webhook registered",
                "configured": self.telegram.configured,
                "publicUrl": self.telegram.settings.public_url or "NOT SET",
                "botTokenSet": bool(self.telegram.settings.telegram_bot_token),
            })
        except Exception:
            self._send_json(_error_payload("Webhook registration failed."), status=400)

    def _get_telegram_status(self) -> None:
        try:
            info = self.telegram._api("getWebhookInfo", {})
            payload = {
                "configured": self.telegram.configured,
                "publicUrl": self.settings.public_url or "NOT SET",
                "botTokenSet": bool(self.settings.telegram_bot_token),
                "webhookUrl": info.get("url", "NOT SET"),
                "hasCustomCertificate": info.get("has_custom_certificate", False),
                "pendingUpdateCount": info.get("pending_update_count", 0),
                "lastErrorDate": info.get("last_error_date"),
                "lastErrorMessage": info.get("last_error_message"),
            }
        except Exception:
            self._send_json(_error_payload("Failed to get Telegram status."), status=400)
            return
        # The Telegram API call is the expensive part; cache the assembled status
        # for read_cache_ttl_seconds so dashboard polling doesn't hit Telegram each time.
        self._send_json(cached_get(self._get_cache, self.path, lambda: payload))

    def _run_chat(self) -> None:
        payload = self._read_json()
        prompt = str(payload.get("prompt") or "").strip()
        if not prompt:
            self._send_json({"error": "Prompt is required."}, status=400)
            return

        history = payload.get("messages") if isinstance(payload.get("messages"), list) else []
        current_evidence_id = normalize_current_evidence_id(payload)
        current_evidence_id = str(current_evidence_id) if current_evidence_id else None

        # Resolve the operator (logged-in user) so the model can address them by
        # name. Client-sent profile is preferred; the forwarded Supabase JWT is
        # the fallback. A fresh per-request registry scopes the operator safely
        # under the threaded server (the shared class registry stays operator-free
        # for /tools and /plan).
        operator = resolve_operator(payload, self.headers.get("Authorization"), self.settings)
        registry = ExamshieldToolRegistry(self.store)
        registry.operator = operator

        self.send_response(200)
        self._cors_headers()
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-transform")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

        def write_event(event: dict[str, Any]) -> None:
            self.wfile.write(sse_bytes(event))
            self.wfile.flush()

        session = ChatSession(client=self.client, registry=registry, write=write_event)
        try:
            session.run(prompt, history, current_evidence_id, operator, tenant=self._client_ip())
        except Exception as exc:
            logger.error("Chat stream failed: %s", exc, exc_info=True)
            write_event({"type": "error", "message": str(exc) or "Chat failed."})
            write_event({"type": "done"})

    def _run_plan(self) -> None:
        payload = self._read_json()
        prompt = str(payload.get("prompt") or "").strip()
        if not prompt:
            self._send_json({"error": "Prompt is required."}, status=400)
            return

        history = payload.get("messages") if isinstance(payload.get("messages"), list) else []
        current_evidence_id = normalize_current_evidence_id(payload)
        current_evidence_id = str(current_evidence_id) if current_evidence_id else None

        if not self.client.configured:
            self._send_json({"tool": None, "error": "KILO_API_KEY is not configured."})
            return

        try:
            command = ToolPlanner(self.client, self.registry).plan(prompt, current_evidence_id, history)
        except Exception as exc:
            self._send_json({"tool": None, "error": f"Tool planner unavailable: {type(exc).__name__}."})
            return

        if not command:
            self._send_json({"tool": None})
            return

        execution = self.registry.execute(command["tool"], command.get("arguments") or {})
        self._send_json({
            "tool": execution.result["tool"],
            "result": execution.result,
            "model_context": execution.model_context,
        })

    def _memory_ingest(self) -> None:
        try:
            self._send_json(self.memory.ingest_manual(self._read_json()), status=201)
        except LookupError:
            self._send_json(_error_payload("Not found."), status=404)
        except Exception:
            self._send_json(_error_payload("Memory ingest failed."), status=400)

    def _memory_search(self) -> None:
        try:
            payload = self._read_json()
            query = str(payload.get("query") or payload.get("content") or "").strip()
            if not query:
                self._send_json({"error": "query is required."}, status=400)
                return
            threshold = float(payload.get("threshold") or payload.get("matchThreshold") or 0.76)
            match_count = int(payload.get("matchCount") or payload.get("limit") or 8)
            created_after = (
                str(payload.get("createdAfter") or payload.get("minCreatedAt") or payload.get("since") or "").strip()
                or None
            )
            self._send_json(
                self.memory.search(
                    query,
                    threshold=threshold,
                    match_count=match_count,
                    created_after=created_after,
                )
            )
        except Exception:
            self._send_json(_error_payload("Memory search failed."), status=400)

    def _memory_correlate(self) -> None:
        try:
            payload = self._read_json()
            memory_id = str(payload.get("memoryId") or "").strip()
            evidence_id = normalize_evidence_id(payload)
            if memory_id:
                self._send_json(self.memory.correlate_memory_id(memory_id))
                return
            if evidence_id:
                result = self.memory.ingest_manual({"evidenceId": evidence_id})
                self._send_json(result.get("correlation") or {"correlated": False})
                return
            self._send_json({"error": "memoryId or evidenceId is required."}, status=400)
        except LookupError:
            self._send_json(_error_payload("Not found."), status=404)
        except Exception:
            self._send_json(_error_payload("Memory correlation failed."), status=400)

    def _get_memory(self, memory_id: str) -> None:
        try:
            result = self.memory.get_memory(memory_id)
            self._send_json(result if result else {"error": "Memory item not found."}, status=200 if result else 404)
        except Exception:
            self._send_json(_error_payload("Memory lookup failed."), status=400)

    # ─────────────────────────────────────────────────────────────────
    # Community Agents
    # ─────────────────────────────────────────────────────────────────

    def _list_agents(self) -> None:
        try:
            status = None
            parsed = urlparse(self.path)
            for param in (parsed.query or "").split("&"):
                if param.startswith("status="):
                    status = param.split("=", 1)[1] or None
            agents = cached_get(
                self._get_cache,
                self.path,
                lambda: self.agent_store.list_agents(status=status),
            )
            self._send_json({"agents": agents, "total": len(agents)})
        except Exception:
            self._send_json(_error_payload("Failed to list agents."), status=400)

    def _get_agent(self, agent_id: str) -> None:
        try:
            agent = self.agent_store.get_agent(agent_id)
            if not agent:
                self._send_json({"error": "Agent not found."}, status=404)
                return
            llm_config = self.agent_store.get_llm_config(agent_id)
            tg_config = self.agent_store.get_telegram_config(agent_id)
            sources = self.agent_store.list_knowledge_sources(agent_id)
            stats = self.agent_store.get_agent_stats(agent_id)
            safe_telegram = None
            if tg_config:
                safe_telegram = {k: v for k, v in tg_config.items() if k != "botToken"}
                safe_telegram["botTokenSet"] = bool(tg_config.get("botToken"))
            self._send_json({
                "agent": {
                    **agent,
                    "knowledgeCount": stats["totalKnowledgeSources"],
                    "conversationCount": stats["totalConversations"],
                },
                "llmConfig": {k: v for k, v in (llm_config or {}).items() if k != "apiKeyEncrypted"} if llm_config else None,
                "telegramConfig": safe_telegram,
                "knowledgeSources": sources,
                "stats": stats,
            })
        except Exception:
            self._send_json(_error_payload("Failed to get agent."), status=400)

    def _create_agent(self) -> None:
        try:
            data = self._read_json()
            agent = self.agent_store.create_agent(data)
            self._send_json({"agent": agent, "message": "Agent created."}, status=201)
        except Exception:
            self._send_json(_error_payload("Failed to create agent."), status=400)

    def _update_agent(self, agent_id: str) -> None:
        try:
            data = self._read_json()
            agent = self.agent_store.update_agent(agent_id, data)
            self._send_json({"agent": agent, "message": "Agent updated."})
        except LookupError:
            self._send_json(_error_payload("Not found."), status=404)
        except Exception:
            self._send_json(_error_payload("Failed to update agent."), status=400)

    def _delete_agent(self, agent_id: str) -> None:
        try:
            deleted = self.agent_store.delete_agent(agent_id)
            if deleted:
                self._send_json({"message": "Agent deleted."})
            else:
                self._send_json({"error": "Agent not found."}, status=404)
        except Exception:
            self._send_json(_error_payload("Failed to delete agent."), status=400)

    def _upsert_agent_llm(self, agent_id: str) -> None:
        try:
            data = self._read_json()
            config = self.agent_store.upsert_llm_config(agent_id, data)
            self._send_json({"config": {k: v for k, v in config.items() if k != "apiKeyEncrypted"}, "message": "LLM config saved."})
        except LookupError:
            self._send_json(_error_payload("Not found."), status=404)
        except Exception:
            self._send_json(_error_payload("Failed to save LLM config."), status=400)

    def _upsert_agent_telegram(self, agent_id: str) -> None:
        try:
            data = self._read_json()
            config = self.agent_store.upsert_telegram_config(agent_id, data)
            safe_config = {k: v for k, v in config.items() if k != "botToken"}
            safe_config["botTokenSet"] = bool(config.get("botToken"))
            self._send_json({"config": safe_config, "message": "Telegram config saved."})
        except LookupError:
            self._send_json(_error_payload("Not found."), status=404)
        except Exception:
            self._send_json(_error_payload("Failed to save Telegram config."), status=400)

    def _validate_llm_key(self) -> None:
        try:
            data = self._read_json()
            provider = str(data.get("provider", "")).strip()
            api_key = str(data.get("apiKey", "")).strip()
            model = str(data.get("model", "")).strip()
            endpoint_url = str(data.get("endpointUrl", "")).strip()

            if not provider:
                self._send_json({"error": "provider is required."}, status=400)
                return

            if provider != "custom" and not api_key:
                self._send_json({"error": "apiKey is required for this provider."}, status=400)
                return

            if provider == "custom" and not endpoint_url:
                self._send_json({"error": "endpointUrl is required for custom provider."}, status=400)
                return

            if not model:
                from .llm_providers import PROVIDER_REGISTRY
                models = PROVIDER_REGISTRY.get(provider, {}).get("models", [])
                model = models[0] if models else "gpt-4o"

            config = ProviderConfig(provider=provider, api_key=api_key, model=model, endpoint_url=endpoint_url)
            result = validate_api_key(config)
            self._send_json(result)
        except Exception:
            self._send_json(_error_payload("Validation failed."), status=400)

    def _create_knowledge_source(self, agent_id: str) -> None:
        try:
            data = self._read_json()
            source = self.agent_store.create_knowledge_source(agent_id, data)
            self._send_json({"source": source, "message": "Knowledge source created."}, status=201)
        except LookupError:
            self._send_json(_error_payload("Not found."), status=404)
        except Exception:
            self._send_json(_error_payload("Failed to create knowledge source."), status=400)

    def _list_knowledge_sources(self, agent_id: str) -> None:
        try:
            sources = self.agent_store.list_knowledge_sources(agent_id)
            self._send_json({"sources": sources, "total": len(sources)})
        except Exception:
            self._send_json(_error_payload("Failed to list sources."), status=400)

    def _delete_knowledge_source(self, agent_id: str, source_id: str) -> None:
        try:
            source = self.agent_store.get_knowledge_source(source_id)
            if not source or source.get("agentId") != agent_id:
                self._send_json({"error": "Knowledge source not found."}, status=404)
                return
            self.agent_store.delete_knowledge_source(source_id)
            self._send_json({"message": "Knowledge source deleted."})
        except Exception:
            self._send_json(_error_payload("Failed to delete source."), status=400)

    def _verify_bot_token(self) -> None:
        try:
            data = self._read_json()
            token = str(data.get("token", "")).strip()
            if not token:
                self._send_json({"error": "Bot token is required."}, status=400)
                return

            import urllib.error
            import urllib.request
            url = f"https://api.telegram.org/bot{token}/getMe"
            req = urllib.request.Request(url, method="GET")
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    result = json.loads(resp.read().decode())
                    if result.get("ok"):
                        bot = result.get("result", {})
                        self._send_json({
                            "valid": True,
                            "botUsername": bot.get("username", ""),
                            "botFirstName": bot.get("first_name", ""),
                            "botId": bot.get("id"),
                            "canJoinGroups": bot.get("can_join_groups", False),
                            "canReadAllGroupMessages": bot.get("can_read_all_group_messages", False),
                        })
                    else:
                        self._send_json({"valid": False, "error": result.get("description", "Invalid token.")})
            except urllib.error.HTTPError as exc:
                if exc.code == 401:
                    self._send_json({"valid": False, "error": "Invalid bot token."})
                else:
                    self._send_json({"valid": False, "error": f"Telegram API error ({exc.code})."})
            except urllib.error.URLError:
                self._send_json({"valid": False, "error": "Network error reaching Telegram API."})
        except Exception:
            self._send_json(_error_payload("Verification failed."), status=400)

    def _deploy_agent(self, agent_id: str) -> None:
        try:
            agent = self.agent_store.get_agent(agent_id)
            if not agent:
                self._send_json({"error": "Agent not found."}, status=404)
                return

            llm_config = self.agent_store.get_llm_config(agent_id)
            if not llm_config:
                self._send_json({"error": "LLM not configured. Complete provider setup first."}, status=400)
                return

            telegram_config = self.agent_store.get_telegram_config(agent_id)
            if not telegram_config or not telegram_config.get("botToken"):
                self._send_json({"error": "Telegram not configured. Add a bot token first."}, status=400)
                return

            self.agent_store.update_agent(agent_id, {"status": "deploying"})

            import urllib.error
            import urllib.request
            token = telegram_config["botToken"]
            url = f"https://api.telegram.org/bot{token}/getMe"
            req = urllib.request.Request(url, method="GET")
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    result = json.loads(resp.read().decode())
                    if not result.get("ok"):
                        self.agent_store.update_agent(agent_id, {"status": "failed"})
                        self.agent_store.update_telegram_config(agent_id, {"deploymentStatus": "invalid-token"})
                        self._send_json({"error": "Bot token is invalid."}, status=400)
                        return
            except Exception:
                self.agent_store.update_agent(agent_id, {"status": "failed"})
                self.agent_store.update_telegram_config(agent_id, {"deploymentStatus": "network-error"})
                self._send_json({"error": "Failed to verify bot with Telegram."}, status=500)
                return

            webhook_url = f"{self.settings.public_url}/telegram/webhook" if self.settings.public_url else ""
            if webhook_url:
                set_url = f"https://api.telegram.org/bot{token}/setWebhook"
                set_body = json.dumps({"url": webhook_url}).encode()
                set_req = urllib.request.Request(set_url, data=set_body, method="POST", headers={"Content-Type": "application/json"})
                try:
                    with urllib.request.urlopen(set_req, timeout=10) as resp:
                        result = json.loads(resp.read().decode())
                        if not result.get("ok"):
                            self.agent_store.update_agent(agent_id, {"status": "failed"})
                            self._send_json({"error": f"Webhook setup failed: {result.get('description', 'unknown')}"}, status=500)
                            return
                except Exception as exc:
                    self.agent_store.update_agent(agent_id, {"status": "failed"})
                    self._send_json({"error": f"Webhook setup failed: {exc}"}, status=500)
                    return

            self.agent_store.update_agent(agent_id, {"status": "active"})
            self.agent_store.update_telegram_config(agent_id, {
                "deploymentStatus": "deployed",
                "botVerified": True,
                "webhookUrl": webhook_url,
            })
            self._send_json({"message": "Agent deployed successfully.", "status": "active", "webhookUrl": webhook_url})
        except Exception:
            try:
                self.agent_store.update_agent(agent_id, {"status": "failed"})
            except Exception:
                pass
            self._send_json(_error_payload("Deployment failed."), status=500)

    def _upload_knowledge_files(self, agent_id: str, source_id: str) -> None:
        try:
            source = self.agent_store.get_knowledge_source(source_id)
            if not source or source.get("agentId") != agent_id:
                self._send_json({"error": "Knowledge source not found."}, status=404)
                return

            self.agent_store.update_knowledge_source(source_id, {"status": "processing"})

            content_type = (self.headers.get("Content-Type") or "").lower()
            if "multipart/form-data" not in content_type:
                self._send_json({"error": "multipart/form-data required."}, status=400)
                return

            fields = self._read_multipart()
            files_data = []
            for key, value in fields.items():
                if isinstance(value, UploadedFile) and value.data:
                    files_data.append({
                        "filename": value.filename,
                        "data": value.data,
                        "contentType": value.content_type,
                    })

            if not files_data:
                self.agent_store.update_knowledge_source(source_id, {"status": "failed", "errorMessage": "No files uploaded."})
                self._send_json({"error": "No files uploaded."}, status=400)
                return

            self.agent_store.update_knowledge_source(source_id, {"fileCount": len(files_data)})

            rag_config = RAGConfig(
                supabase_url=self.settings.supabase_url or "",
                supabase_service_role_key=self.settings.supabase_service_role_key or "",
                embed_function_url=f"{self.settings.supabase_url}/functions/v1/embed" if self.settings.supabase_url else "",
            )

            result: dict[str, Any] | None = None
            if rag_config.supabase_url and rag_config.supabase_service_role_key:
                result = ingest_knowledge_source(source_id, agent_id, files_data, rag_config)

            if not result or result.get("status") != "ready":
                local_chunks: list[dict[str, Any]] = []
                total_chars = 0
                for file_info in files_data:
                    extracted = extract_text_from_file(
                        str(file_info.get("filename") or ""),
                        file_info.get("data") or b"",
                        str(file_info.get("contentType") or "application/octet-stream"),
                    )
                    if not extracted:
                        continue
                    total_chars += len(extracted)
                    for item in chunk_text(extracted):
                        local_chunks.append({
                            **item,
                            "filename": file_info.get("filename", ""),
                        })
                if not local_chunks:
                    message = "No text could be extracted from the uploaded files. Use PDF, TXT, or Markdown files with selectable text."
                    self.agent_store.update_knowledge_source(source_id, {"status": "failed", "errorMessage": message})
                    self._send_json({"error": message}, status=400)
                    return
                stored = self.agent_store.replace_knowledge_chunks(source_id, agent_id, local_chunks)
                result = {"status": "ready", "chunksStored": stored, "totalChars": total_chars, "storage": "local"}

            self.agent_store.update_knowledge_source(source_id, {
                "status": "ready",
                "chunkCount": int(result.get("chunksStored") or 0),
                "totalChars": int(result.get("totalChars") or 0),
                "errorMessage": None,
            })
            self._send_json(result)
        except Exception as exc:
            try:
                self.agent_store.update_knowledge_source(source_id, {"status": "failed", "errorMessage": str(exc)})
            except Exception:
                pass
            self._send_json(_error_payload("Upload failed."), status=400)

    def _test_agent(self, agent_id: str) -> None:
        try:
            data = self._read_json()
            question = str(data.get("question", "")).strip()
            if not question:
                self._send_json({"error": "question is required."}, status=400)
                return

            agent = self.agent_store.get_agent(agent_id)
            if not agent:
                self._send_json({"error": "Agent not found."}, status=404)
                return

            llm_config = self.agent_store.get_llm_config(agent_id)
            if not llm_config:
                self._send_json({"error": "LLM not configured for this agent."}, status=400)
                return

            rag_config = RAGConfig(
                supabase_url=self.settings.supabase_url or "",
                supabase_service_role_key=self.settings.supabase_service_role_key or "",
                embed_function_url=f"{self.settings.supabase_url}/functions/v1/embed" if self.settings.supabase_url else "",
            )

            context_chunks: list[dict[str, Any]] = []
            if rag_config.supabase_url:
                try:
                    context_chunks = search_agent_knowledge(question, agent_id, rag_config)
                except Exception as exc:
                    logger.warning("RAG search failed for agent test: %s", exc)
            if not context_chunks:
                context_chunks = self.agent_store.search_knowledge_chunks(agent_id, question)

            system_prompt = agent.get("systemPrompt", "") or "You are a helpful assistant."
            if context_chunks:
                context_text = "\n\n".join(c.get("content", "") for c in context_chunks)
                system_prompt += f"\n\nUse the following knowledge to answer:\n\n{context_text}"

            style = agent.get("responseStyle", "balanced")
            if style == "short":
                system_prompt += "\n\nKeep responses concise (1-2 paragraphs)."
            elif style == "detailed":
                system_prompt += "\n\nProvide detailed, comprehensive answers."

            if agent.get("citationMode") and context_chunks:
                system_prompt += "\n\nCite sources when referencing specific information."

            provider_config = ProviderConfig(
                provider=llm_config.get("provider", "openai"),
                api_key=normalize_api_key(llm_config),
                model=llm_config.get("model", "gpt-4o"),
                endpoint_url=llm_config.get("endpointUrl", ""),
                extra_headers=llm_config.get("extraHeaders", {}),
            )

            import time as _time
            start = _time.monotonic()
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question},
            ]
            result = provider_chat_completion(provider_config, messages, max_tokens=1024, timeout=15)
            latency_ms = int((_time.monotonic() - start) * 1000)

            response_text = result.get("content", "")
            if result.get("error"):
                self._send_json({
                    "error": f"{provider_config.provider} request failed: {result['error']}",
                    "provider": provider_config.provider,
                    "model": provider_config.model,
                }, status=502)
                return
            if not str(response_text).strip():
                self._send_json({"error": "The configured model returned an empty response."}, status=502)
                return

            self.agent_store.log_conversation(
                agent_id=agent_id,
                user_message=question,
                agent_response=response_text,
                sources=[{"content": c.get("content", "")[:200], "similarity": c.get("similarity", 0)} for c in context_chunks],
                latency_ms=latency_ms,
            )

            self._send_json({
                "response": response_text,
                "sources": context_chunks,
                "latencyMs": latency_ms,
                "model": provider_config.model,
                "provider": provider_config.provider,
            })
        except Exception:
            self._send_json(_error_payload("Agent test failed."), status=400)

    def _get_agent_stats(self, agent_id: str) -> None:
        try:
            stats = self.agent_store.get_agent_stats(agent_id)
            self._send_json(stats)
        except Exception:
            self._send_json(_error_payload("Failed to get stats."), status=400)

    def _list_conversations(self, agent_id: str) -> None:
        try:
            convs = self.agent_store.list_conversations(agent_id)
            self._send_json({"conversations": convs, "total": len(convs)})
        except Exception:
            self._send_json(_error_payload("Failed to list conversations."), status=400)

    # ── Rate limiting / abuse helpers ───────────────────────────────────

    def _client_ip(self) -> str:
        """Extract client IP, respecting X-Forwarded-For (first entry)."""
        xff = (self.headers.get("X-Forwarded-For") or "").strip()
        if xff:
            return xff.split(",")[0].strip()
        return self.client_address[0]

    def _rate_limit_check(self, limiter, label: str) -> bool:
        """Check rate limit; send 429 if exceeded. Returns True if allowed."""
        if limiter.max_requests <= 0:
            return True
        allowed, info = limiter.allow(self._client_ip())
        if not allowed:
            self._send_json(
                {"error": f"Rate limit exceeded for {label}. Retry after {info['retry_after']:.0f}s."},
                status=429,
            )
            return False
        return True

    @staticmethod
    def _validate_image_magic(data: bytes, content_type: str) -> str | None:
        """Check magic bytes match declared content-type. Returns error or None."""
        if not data:
            return "Empty file payload."
        if content_type == "image/jpeg" and data[:2] != b"\xff\xd8":
            return "Content-Type says JPEG but file does not start with JPEG magic bytes."
        if content_type == "image/png" and data[:8] != b"\x89PNG\r\n\x1a\n":
            return "Content-Type says PNG but file does not start with PNG magic bytes."
        return None

    def _read_json(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length") or "0")
        except ValueError:
            length = 0
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _read_multipart_file(self, field_name: str) -> UploadedFile:
        fields = self._read_multipart()
        value = fields.get(field_name)
        if not isinstance(value, UploadedFile):
            raise ValueError("Evidence file is required.")
        return value

    def _read_multipart(self) -> dict[str, str | UploadedFile]:
        try:
            length = int(self.headers.get("Content-Length") or "0")
        except ValueError:
            length = 0
        # ── Size enforcement ──
        max_bytes = self.settings.max_upload_bytes
        if max_bytes > 0 and length > max_bytes:
            raise ValueError(f"Payload too large ({length} bytes). Maximum is {max_bytes}.")
        body = self.rfile.read(length)
        content_type = self.headers.get("Content-Type") or ""
        return parse_multipart(body, content_type)

    def _body_exceeds_server_cap(self) -> bool:
        """Server-level request body cap (audit §8 — Backend Weaknesses).

        Returns True when the declared ``Content-Length`` exceeds
        ``settings.max_request_body_bytes``. A missing/invalid length is
        treated as zero and never rejected here (the endpoint still validates
        the bytes it actually reads).
        """
        cap = self.settings.max_request_body_bytes
        if cap <= 0:
            return False
        try:
            length = int(self.headers.get("Content-Length") or "0")
        except ValueError:
            length = 0
        return length > cap

    def _reject_oversized_request(self) -> bool:
        """If the request body exceeds the server cap, send 413 and return True."""
        if self._body_exceeds_server_cap():
            self._send_json(
                {"status": "failed", "error": "Payload too large for this endpoint."},
                status=413,
            )
            return True
        return False

    def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        try:
            self.send_response(status)
            self._cors_headers()
            self.send_header("Content-Type", "application/json")
            # Read endpoints are safe for browsers/CDNs to cache briefly, which
            # keeps the dashboard's polling from re-fetching unchanged data on
            # every tick. /health stays no-cache so it always reflects liveness.
            if self.command == "GET" and urlparse(self.path).path != "/health":
                self.send_header(
                    "Cache-Control",
                    f"public, max-age={self.settings.cache_control_max_age}",
                )
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            logger.warning("Client disconnected before JSON response completed")

    def do_DELETE(self) -> None:
        path = urlparse(self.path).path
        if not self._authorize_request():
            return
        parts = [part for part in path.split("/") if part]
        if len(parts) == 3 and parts[0] == "telegram" and parts[1] == "groups":
            self._remove_monitored_group(parts[2])
            return
        if len(parts) == 2 and parts[0] == "agents":
            self._delete_agent(parts[1])
            return
        if len(parts) == 4 and parts[0] == "agents" and parts[2] == "knowledge":
            self._delete_knowledge_source(parts[1], parts[3])
            return
        if len(parts) == 2 and parts[0] == "registry":
            self._delete_registry_paper(parts[1])
            return
        self._send_json({"error": "Not found"}, status=404)

    def do_PUT(self) -> None:
        if self._reject_oversized_request():
            return
        path = urlparse(self.path).path
        if not self._authorize_request():
            return
        parts = [part for part in path.split("/") if part]
        if len(parts) == 2 and parts[0] == "agents":
            self._update_agent(parts[1])
            return
        if len(parts) == 2 and parts[0] == "registry":
            self._update_registry_paper(parts[1])
            return
        self._send_json({"error": "Not found"}, status=404)

    # ── Question Registry ──

    def _list_registry_papers(self) -> None:
        try:
            papers = cached_get(self._get_cache, self.path, self.store.read_registry)
            self._send_json({"papers": papers, "total": len(papers)})
        except Exception:
            self._send_json(_error_payload("Failed to list papers."), status=400)

    def _get_registry_paper(self, paper_id: str) -> None:
        try:
            paper = self.store.get_registry_paper(paper_id)
            if not paper:
                self._send_json({"error": "Paper not found."}, status=404)
                return
            self._send_json({"paper": paper})
        except Exception:
            self._send_json(_error_payload("Request failed."), status=400)

    def _get_registry_stats(self) -> None:
        try:
            papers = cached_get(self._get_cache, self.path, self.store.read_registry)
            total = len(papers)
            protected = sum(1 for p in papers if p.get("protected", True))
            compromised = sum(1 for p in papers if p.get("status") == "compromised")
            investigating = sum(1 for p in papers if p.get("status") == "investigating")
            by_exam: dict[str, int] = {}
            for p in papers:
                exam = p.get("exam", "Unknown")
                by_exam[exam] = by_exam.get(exam, 0) + 1
            self._send_json({
                "totalPapers": total,
                "protectedPapers": protected,
                "compromisedPapers": compromised,
                "investigatingPapers": investigating,
                "byExam": by_exam,
            })
        except Exception:
            self._send_json(_error_payload("Request failed."), status=400)

    def _create_registry_paper(self) -> None:
        try:
            data = self._read_json()
            paper_id = str(data.get("paperId", "")).strip()
            if not paper_id:
                self._send_json({"error": "paperId is required."}, status=400)
                return
            existing = self.store.get_registry_paper(paper_id)
            if existing:
                self._send_json({"error": f"Paper {paper_id} already exists."}, status=409)
                return
            paper = self.store.add_registry_paper(data)
            self._send_json({"paper": paper, "message": "Paper registered."}, status=201)
        except Exception:
            self._send_json(_error_payload("Failed to create paper."), status=400)

    def _reset_registry(self) -> None:
        try:
            self.store._write_registry([])
            self._send_json({"message": "Registry cleared.", "total": 0})
        except Exception:
            self._send_json(_error_payload("Failed to reset registry."), status=400)

    def _update_registry_paper(self, paper_id: str) -> None:
        try:
            data = self._read_json()
            paper = self.store.update_registry_paper(paper_id, data)
            self._send_json({"paper": paper})
        except LookupError:
            self._send_json(_error_payload("Not found."), status=404)
        except Exception:
            self._send_json(_error_payload("Request failed."), status=400)

    def _delete_registry_paper(self, paper_id: str) -> None:
        try:
            deleted = self.store.delete_registry_paper(paper_id)
            if not deleted:
                self._send_json({"error": "Paper not found."}, status=404)
                return
            self._send_json({"message": "Paper deleted."})
        except Exception:
            self._send_json(_error_payload("Request failed."), status=400)

    def _match_evidence_to_registry(self) -> None:
        try:
            data = self._read_json()
            ocr_text = str(data.get("ocrText", "")).strip()
            evidence_id = normalize_evidence_id(data)
            if not ocr_text:
                self._send_json({"error": "ocrText is required."}, status=400)
                return
            matches = self.store.match_evidence_against_registry(ocr_text)
            if matches and evidence_id:
                best = matches[0]
                if best.get("similarityScore", 0) > 70:
                    self.store.record_activity({
                        "type": "paper-matched",
                        "title": "Paper Matched",
                        "evidenceId": evidence_id,
                        "detail": f"Matched {best.get('matchedExam')} ({best.get('matchedSet')}) at {best.get('similarityScore')}%",
                    })
            self._send_json({"matches": matches, "total": len(matches)})
        except Exception:
            self._send_json(_error_payload("Request failed."), status=400)

    def _mint_watermark(self) -> None:
        """POST /watermark/mint — issue uniquely watermarked copies per recipient."""
        try:
            data = self._read_json()
            paper_id = str(data.get("paperId", "")).strip()
            source_text = str(data.get("sourceText", ""))
            recipients = [r for r in (data.get("recipients") or []) if isinstance(r, dict)]
            if not paper_id:
                self._send_json({"error": "paperId is required."}, status=400)
                return
            if not recipients:
                self._send_json({"error": "recipients (list) is required."}, status=400)
                return
            copies = self.store.mint_copies(paper_id, recipients, source_text)
            self._send_json(
                {"paperId": paper_id, "copies": copies, "count": len(copies), "message": "Watermarked copies issued."},
                status=201,
            )
        except LookupError as exc:
            self._send_json({"error": str(exc)}, status=404)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=400)
        except Exception:
            self._send_json(_error_payload("Failed to mint watermark."), status=400)

    def _decode_watermark(self) -> None:
        """POST /watermark/decode — recover the issuing recipient from leaked text."""
        try:
            data = self._read_json()
            text = str(data.get("text") or data.get("ocrText") or "")
            if not text.strip():
                self._send_json({"error": "text is required."}, status=400)
                return
            matches = []
            for token in decode_watermark(text):
                parsed = parse_token(token)
                if not parsed:
                    continue
                copy = self.store.find_copy_by_watermark(parsed["copyId"])
                matches.append({
                    "token": token,
                    "copyId": parsed["copyId"],
                    "paperId": parsed["paperId"],
                    "recipientRef": parsed["recipientRef"],
                    "copy": copy,
                })
            self._send_json({"matches": matches, "total": len(matches), "detected": bool(matches)})
        except Exception:
            self._send_json(_error_payload("Failed to decode watermark."), status=400)

    def _list_watermark_copies(self) -> None:
        """GET /watermark/copies?paperId= — list issued watermark copies."""
        try:
            qs = parse_qs(urlparse(self.path).query)
            paper_id = (qs.get("paperId") or [None])[0]
            copies = self.store.read_copies()
            if paper_id:
                copies = [c for c in copies if c.get("paperId") == paper_id]
            self._send_json({"copies": copies, "total": len(copies)})
        except Exception:
            self._send_json(_error_payload("Failed to list copies."), status=400)

    def _generate_report(self) -> None:
        """POST /reports/generate — Generate a Markdown report."""
        from .reports import (
            generate_evidence_report,
            generate_summary_report,
            report_to_document_bytes,
        )

        try:
            payload = self._read_json()
        except Exception:
            payload = {}

        evidence_id = normalize_evidence_id(payload)
        report_type = str(payload.get("reportType") or ("evidence" if evidence_id else "summary")).strip()
        send_to_telegram = bool(payload.get("sendToTelegram"))
        telegram_chat_id = str(payload.get("chatId") or self.settings.telegram_admin_chat_id or "").strip()

        if report_type == "evidence" and evidence_id:
            md = generate_evidence_report(evidence_id, self.store)
            filename = f"report-{evidence_id}.md"
        else:
            md = generate_summary_report(self.store)
            filename = "report-dashboard-summary.md"
            evidence_id = ""

        result = {
            "report": md,
            "filename": filename,
            "length": len(md),
            "reportType": report_type,
            "evidenceId": evidence_id or None,
        }

        # Optionally send to Telegram
        if send_to_telegram and telegram_chat_id:
            try:
                from .telegram import TelegramWebhook
                tg = TelegramWebhook(self.settings)
                data_bytes = report_to_document_bytes(md)
                caption = f"📄 Report: {evidence_id}" if evidence_id else "📊 Dashboard Summary Report"
                tg._api_multipart(
                    "sendDocument",
                    fields={"chat_id": telegram_chat_id, "caption": caption},
                    file_field="document",
                    filename=filename,
                    data=data_bytes,
                    content_type="text/markdown",
                )
                result["sentToTelegram"] = True
                result["telegramChatId"] = telegram_chat_id
                logger.info("Report %s sent to Telegram chat %s", filename, telegram_chat_id)
            except Exception as exc:
                result["sentToTelegram"] = False
                result["telegramError"] = str(exc)
                logger.error("Failed to send report to Telegram: %s", exc)

        self._send_json(result)

    def _test_telegram_chat(self) -> None:
        """Test endpoint for Telegram private chat functionality."""
        try:
            payload = self._read_json()
            chat_id = str(payload.get("chatId") or self.settings.telegram_admin_chat_id or "").strip()
            message_text = str(payload.get("message") or "").strip()
            
            if not chat_id or not message_text:
                self._send_json({"error": "chatId and message are required."}, status=400)
                return
            
            # Try to get a chat response
            llm = KiloClient(self.settings)
            if llm.configured:
                from .telegram import _clean_telegram_html
                
                system_prompt = (
                    "You are ExamShield AI, an exam security assistant. "
                    "You are chatting with someone in a private Telegram DM. "
                    "You monitor groups for potential exam leaks and suspicious activity. "
                    "You are friendly, helpful, and professional. "
                    "Respond naturally to questions about exam security, the monitoring system, or general queries. "
                    "Keep responses concise (under 200 characters). "
                    "Use Telegram HTML formatting: <b>, <i>, <code>. "
                    "If someone asks what you do, briefly explain you monitor for exam leaks. "
                    "If someone greets you, respond warmly. "
                    "Be conversational and human-like."
                )
                
                user_prompt = f"User message: {message_text}"
                
                response = llm.chat_text(
                    model=self.settings.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    max_tokens=200,
                    timeout=10,
                )
                cleaned = _clean_telegram_html(response)
                
                # Send the response to the private chat
                telegram = TelegramWebhook(self.settings)
                if telegram.configured:
                    telegram.send_message(chat_id, cleaned, parse_mode="HTML")
                
                self._send_json({
                    "status": "ok",
                    "message": message_text,
                    "chatId": chat_id,
                    "response": cleaned or "No response generated",
                    "sentToTelegram": telegram.configured,
                })
            else:
                self._send_json({"error": "KILO_API_KEY is not configured."}, status=500)
        except Exception:
            self._send_json(_error_payload("Chat test failed."), status=400)

    def _add_monitored_group(self) -> None:
        try:
            payload = self._read_json()
            chat_id = str(payload.get("chatId") or "").strip()
            if not chat_id:
                self._send_json({"error": "chatId is required."}, status=400)
                return
            name = optional_text(payload.get("name")) or str(chat_id)
            result = self.store.add_monitored_group(chat_id, name=name, added_by="api")
            self._send_json(result, status=201 if result.get("created") else 200)
        except Exception:
            self._send_json(_error_payload("Failed to add group."), status=400)

    def _remove_monitored_group(self, chat_id: str) -> None:
        try:
            result = self.store.remove_monitored_group(chat_id)
            self._send_json(result)
        except Exception:
            self._send_json(_error_payload("Failed to remove group."), status=400)

    def _send_empty(self, status: int) -> None:
        self.send_response(status)
        self._cors_headers()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _cors_headers(self) -> None:
        for name, value in resolve_cors_headers(self.settings, self.headers.get("Origin")).items():
            self.send_header(name, value)
        self.send_header("Access-Control-Allow-Methods", "GET,POST,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", f"Content-Type, Authorization, {API_AUTH_HEADER}")

    def log_message(self, format: str, *args: Any) -> None:
        print("%s - %s" % (self.address_string(), format % args))


def build_handler(settings: Settings):
    class ConfiguredExamshieldAiHandler(ExamshieldAiHandler):
        pass

    store = EvidenceStore(settings)
    telegram = TelegramWebhook(settings)
    workers = AnalysisWorkerPool()
    pipeline = EvidencePipeline(store, telegram, workers)

    ConfiguredExamshieldAiHandler.settings = settings
    ConfiguredExamshieldAiHandler.store = store
    ConfiguredExamshieldAiHandler.registry = ExamshieldToolRegistry(store)
    ConfiguredExamshieldAiHandler.client = KiloClient(settings)
    ConfiguredExamshieldAiHandler.telegram = telegram
    ConfiguredExamshieldAiHandler.workers = workers
    ConfiguredExamshieldAiHandler.pipeline = pipeline
    ConfiguredExamshieldAiHandler.memory = pipeline.memory
    ConfiguredExamshieldAiHandler.agent_store = AgentStore(store)
    ConfiguredExamshieldAiHandler._get_cache = ReadResponseCache(settings.read_cache_ttl_seconds)
    ConfiguredExamshieldAiHandler._ocr_limiter = make_ocr_limiter()
    ConfiguredExamshieldAiHandler._upload_limiter = make_upload_limiter()
    # ── Production hardening (audit §8 — Backend Weaknesses) ──
    # Slow-client / idle socket timeout, applied by BaseHTTPRequestHandler.setup()
    # via self.connection.settimeout(self.timeout). A client that trickles bytes
    # is cut off rather than pinning a worker thread indefinitely.
    ConfiguredExamshieldAiHandler.timeout = settings.request_timeout_seconds
    # Keep-alive tuning: HTTP/1.1 persistent connections when enabled, otherwise
    # close after each request (HTTP/1.0) to bound connection lifetime on a
    # single-process server.
    ConfiguredExamshieldAiHandler.protocol_version = (
        "HTTP/1.1" if settings.keep_alive_enabled else "HTTP/1.0"
    )
    return ConfiguredExamshieldAiHandler


def _start_stale_job_sweeper(store: EvidenceStore) -> None:
    interval_seconds = int(os.environ.get("EXAMSHIELD_STALE_JOB_SWEEP_SECONDS", "60"))
    max_age_seconds = int(os.environ.get("EXAMSHIELD_STALE_JOB_MAX_AGE_SECONDS", "120"))

    def sweep() -> None:
        while True:
            time.sleep(interval_seconds)
            try:
                cleaned = store.cleanup_stale_jobs(max_age_seconds=max_age_seconds)
                if cleaned:
                    logger.warning("Stale job sweeper cleaned %s stuck job(s)", cleaned)
            except Exception as exc:
                logger.error("Stale job sweeper failed: %s", exc)

    threading.Thread(target=sweep, daemon=True, name="stale-job-sweeper").start()


def main() -> None:
    settings = load_settings()
    handler = build_handler(settings)
    logger.info(f"EXAMSHIELD AI starting - telegramBotToken={'SET' if settings.telegram_bot_token else 'NOT SET'}, publicUrl={settings.public_url or 'NOT SET'}, chatId={settings.telegram_chat_id or 'NOT SET'}, adminChatId={settings.telegram_admin_chat_id or 'NOT SET'}")
    if settings.api_auth_secret:
        logger.info("API auth ENABLED — all non-exempt routes require X-Examshield-Api-Key.")
    else:
        logger.warning(
            "API auth DISABLED — set EXAMSHIELD_API_AUTH_SECRET to require a shared "
            "secret on all backend routes (the frontend must send the matching "
            "X-Examshield-Api-Key). Without it the API is reachable anonymously."
        )
    try:
        handler.telegram.register()
        if handler.telegram.configured:
            logger.info(f"Telegram webhook registered to {settings.public_url}/telegram/webhook")
        else:
            logger.warning("Telegram webhook NOT registered - set EXAMSHIELD_PUBLIC_URL in Render to enable")
    except Exception as exc:
        logger.error(f"Telegram webhook registration failed: {exc}")
    try:
        cleaned = handler.store.cleanup_stale_jobs(max_age_seconds=300)
        if cleaned:
            logger.info(f"Cleaned up {cleaned} stale analysis job(s) on startup")
    except Exception as exc:
        logger.error(f"Stale job cleanup failed: {exc}")
    try:
        handler.store.warmup_cache()
        logger.info("Evidence cache warmed on startup")
    except Exception as exc:
        logger.warning("Evidence cache warmup skipped: %s", exc)
    _start_stale_job_sweeper(handler.store)
    # When no PUBLIC_URL is configured there is no webhook, so poll Telegram
    # directly. This keeps the bot working in local/dev without a public host.
    if handler.telegram.configured:
        logger.info("Telegram webhook enabled (PUBLIC_URL set).")
    else:
        # If a community agent is configured with the SAME bot token as the
        # global ExamShield bot, that agent's poller must own the token (it
        # answers DMs as the agent). Running the global poll too would cause a
        # Telegram getUpdates 409 conflict, so we hand the bot to the agent.
        global_token = settings.telegram_bot_token or ""
        agent_owns_global = False
        if global_token:
            for ag in handler.agent_store.list_agents(status="active"):
                tg = handler.agent_store.get_telegram_config(str(ag.get("id") or ""))
                if not tg:
                    continue
                if str(tg.get("deploymentStatus", "")).lower() in ("connected", "deployed", "active") and str(tg.get("botToken") or "") == global_token:
                    agent_owns_global = True
                    break

        if agent_owns_global:
            logger.info(
                "Global Telegram bot token is owned by a community agent — the agent poller "
                "will answer DMs as that agent; global assistant DM polling is skipped to avoid a getUpdates conflict."
            )
        else:
            logger.info("Telegram webhook disabled (no PUBLIC_URL) — starting long-poll receiver.")
            threading.Thread(
                target=handler.telegram.start_polling,
                kwargs={
                    "store": handler.store,
                    "ocr_runner": analyze_image,
                    "pipeline": handler.pipeline,
                },
                daemon=True,
                name="telegram-poll",
            ).start()
    # Community agents each have their own Telegram bot (configured via the
    # agent's botToken). Poll those bots independently so DMs to an agent's bot
    # are answered as that agent. This runs regardless of PUBLIC_URL because
    # agent bots use getUpdates polling, not webhooks.
    threading.Thread(
        target=AgentTelegramService(handler.agent_store, settings).start,
        daemon=True,
        name="agent-telegram-poll",
    ).start()

    server = ThreadingHTTPServer((settings.host, settings.port), handler)
    logger.info(f"EXAMSHIELD AI service listening on http://{settings.host}:{settings.port}")
    try:
        recovered = handler.pipeline.recover_interrupted_jobs(analyze_image)
        if recovered:
            logger.info("Re-queued %s interrupted OCR job(s) after restart", recovered)
    except Exception as exc:
        logger.warning("Interrupted job recovery skipped: %s", exc)
    server.serve_forever()


def optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def require_text(fields: dict[str, str | UploadedFile], name: str) -> str:
    value = fields.get(name)
    if isinstance(value, UploadedFile) or value is None or not str(value).strip():
        raise ValueError(f"{name} is required.")
    return str(value).strip()
