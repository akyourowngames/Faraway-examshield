"""Telegram webhook, event, status, and monitored-group routes."""
from __future__ import annotations

from dataclasses import replace

from fastapi import APIRouter, Depends, Request

from examshield_ai.detect import is_suspicious, scan_text
from examshield_ai.multipart_parse import parse_multipart
from examshield_ai.ocr import analyze_image
from examshield_ai.store import UploadedFile, normalize_telegram_timestamp
from examshield_ai.telegram import TelegramWebhook

from ..deps import backend_secret
from ..responses import json_response

router = APIRouter()


async def _read_json(request: Request) -> dict:
    try:
        payload = await request.json()
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _require_text(fields: dict, name: str) -> str:
    value = fields.get(name)
    if isinstance(value, UploadedFile) or value is None or not str(value).strip():
        raise ValueError(f"{name} is required.")
    return str(value).strip()


@router.post("/telegram/events")
async def ingest_telegram_event(request: Request, _secret: None = Depends(backend_secret)) -> dict:
    core = request.app.state.core
    try:
        content_type = request.headers.get("Content-Type") or ""
        if "multipart/form-data" in content_type:
            fields = parse_multipart(await request.body(), content_type)
            file_field = fields.get("file")
            uploaded = file_field if isinstance(file_field, UploadedFile) else None
            message_id = _require_text(fields, "messageId")
            chat_id = _require_text(fields, "chatId")
            timestamp = normalize_telegram_timestamp(fields.get("timestamp"))
            text = _optional_text(fields.get("text"))
        else:
            payload = await _read_json(request)
            message_id = str(payload.get("messageId") or "").strip()
            chat_id = str(payload.get("chatId") or "").strip()
            if not message_id or not chat_id:
                raise ValueError("messageId and chatId are required.")
            timestamp = normalize_telegram_timestamp(payload.get("timestamp"))
            text = _optional_text(payload.get("text"))
            uploaded = None

        detection = scan_text(text)
        created = core.store.create_telegram_event(
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
            return json_response(
                {
                    "message": "Telegram Event Already Processed",
                    "telegramEvent": created["telegramEvent"],
                    "evidence": created["evidence"],
                    "activity": created["activity"],
                },
                request=request,
            )
        if not created["evidence"]:
            return json_response(
                {
                    "message": "Telegram Event Stored",
                    "telegramEvent": created["telegramEvent"],
                    "evidence": None,
                    "activity": created["activity"],
                    "detection": detection_payload,
                },
                status=202,
                request=request,
            )

        message = {"message_id": message_id, "chat": {"id": chat_id}, "text": text}
        if created["evidence"].get("fileType") == "text/plain":
            alert_sent = core.pipeline.process_text_only_alert(created, detection, text, chat_id, message)
            latest_evidence = (
                core.store.get_evidence_by_id(str(created["evidence"].get("evidenceId")))
                or created["evidence"]
            )
            return json_response(
                {
                    "message": "Suspicious Text Captured",
                    "telegramEvent": created["telegramEvent"],
                    "evidence": latest_evidence,
                    "detection": detection_payload,
                    "alertSent": alert_sent,
                    "activity": created["activity"],
                },
                status=201,
                request=request,
            )

        job = core.pipeline.queue_media_analysis(
            created=created,
            detection=detection,
            text=text,
            chat_id=chat_id,
            message=message,
            ocr_runner=analyze_image,
        )
        return json_response(
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
            request=request,
        )
    except Exception:
        return json_response({"error": "Telegram event ingestion failed."}, status=400, request=request)


@router.post("/telegram/webhook")
async def ingest_telegram_webhook(request: Request, _secret: None = Depends(backend_secret)) -> dict:
    core = request.app.state.core
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if not core.telegram.validate_secret(secret):
        return json_response({"error": "Invalid Telegram webhook secret."}, status=401, request=request)
    try:
        update = await _read_json(request)
        result = core.telegram.process_update(update, core.store, analyze_image, pipeline=core.pipeline)
        return json_response(result, request=request)
    except Exception:
        return json_response({"error": "Telegram webhook failed."}, status=400, request=request)


@router.post("/telegram/register")
async def register_telegram_webhook(request: Request, _secret: None = Depends(backend_secret)) -> dict:
    core = request.app.state.core
    payload = await _read_json(request)
    url_override = str(payload.get("url") or "").strip()
    try:
        telegram = core.telegram
        if url_override:
            telegram = TelegramWebhook(replace(core.settings, public_url=url_override))
        telegram.register()
        return json_response(
            {
                "message": "Telegram webhook registered",
                "configured": telegram.configured,
                "publicUrl": telegram.settings.public_url or "NOT SET",
                "botTokenSet": bool(telegram.settings.telegram_bot_token),
            },
            request=request,
        )
    except Exception:
        return json_response({"error": "Webhook registration failed."}, status=400, request=request)


@router.get("/telegram/status")
async def telegram_status(request: Request, _secret: None = Depends(backend_secret)) -> dict:
    core = request.app.state.core
    try:
        info = core.telegram._api("getWebhookInfo", {})
        payload = {
            "configured": core.telegram.configured,
            "publicUrl": core.settings.public_url or "NOT SET",
            "botTokenSet": bool(core.settings.telegram_bot_token),
            "webhookUrl": info.get("url", "NOT SET"),
            "hasCustomCertificate": info.get("has_custom_certificate", False),
            "pendingUpdateCount": info.get("pending_update_count", 0),
            "lastErrorDate": info.get("last_error_date"),
            "lastErrorMessage": info.get("last_error_message"),
        }
    except Exception:
        return json_response({"error": "Failed to get Telegram status."}, status=400, request=request)
    return json_response(payload, request=request)


@router.get("/telegram/groups")
async def list_groups(request: Request, _secret: None = Depends(backend_secret)) -> dict:
    core = request.app.state.core
    return json_response(
        {"groups": core.store.list_monitored_groups()},
        request=request,
    )


@router.post("/telegram/groups")
async def add_group(request: Request, _secret: None = Depends(backend_secret)) -> dict:
    core = request.app.state.core
    payload = await _read_json(request)
    chat_id = str(payload.get("chatId") or "").strip()
    if not chat_id:
        return json_response({"error": "chatId is required."}, status=400, request=request)
    name = _optional_text(payload.get("name")) or str(chat_id)
    result = core.store.add_monitored_group(chat_id, name=name, added_by="api")
    return json_response(result, status=201 if result.get("created") else 200, request=request)


@router.delete("/telegram/groups/{chat_id}")
async def remove_group(chat_id: str, request: Request, _secret: None = Depends(backend_secret)) -> dict:
    core = request.app.state.core
    result = core.store.remove_monitored_group(chat_id)
    return json_response(result, request=request)
