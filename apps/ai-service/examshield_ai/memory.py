from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import urllib.parse
import urllib.request
from html import escape
from typing import Any
from uuid import uuid4

from .detect import get_alert_severity
from .store import EvidenceStore, JsonObject, detection_confidence_score, utc_now

logger = logging.getLogger(__name__)

MEMORY_ITEMS = "memory-items"
MEMORY_CORRELATIONS = "memory-correlations"
DEFAULT_MATCH_THRESHOLD = float(os.environ.get("EXAMSHIELD_MEMORY_MATCH_THRESHOLD", "0.76"))
DEFAULT_MATCH_COUNT = int(os.environ.get("EXAMSHIELD_MEMORY_MATCH_COUNT", "8"))

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_RE = re.compile(r"(?<!\w)\+?\d[\d\s().-]{7,}\d(?!\w)")
USERNAME_RE = re.compile(r"(?<!\w)@[A-Za-z0-9_]{3,32}\b")
URL_RE = re.compile(r"\b(?:https?://|www\.|t\.me/|telegram\.me/)\S+", re.IGNORECASE)
LONG_ID_RE = re.compile(r"(?<![A-Z0-9-])-?\d{7,}(?![A-Z0-9-])", re.IGNORECASE)
TOKEN_RE = re.compile(r"[a-z0-9]{3,}", re.IGNORECASE)

STOPWORDS = {
    "about",
    "after",
    "alert",
    "and",
    "are",
    "center",
    "detected",
    "evidence",
    "exam",
    "file",
    "from",
    "have",
    "into",
    "paper",
    "redacted",
    "score",
    "source",
    "text",
    "that",
    "the",
    "this",
    "with",
}

SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}


class MemoryManager:
    """Unified, privacy-first threat memory for cross-evidence correlation."""

    def __init__(self, store: EvidenceStore, telegram: Any | None = None) -> None:
        self.store = store
        self.telegram = telegram
        self.function_name = os.environ.get("EXAMSHIELD_EMBED_FUNCTION", "embed").strip() or "embed"

    @property
    def vector_enabled(self) -> bool:
        return self.store.supabase_enabled

    def status(self) -> JsonObject:
        return {
            "enabled": True,
            "storage": "supabase-pgvector" if self.vector_enabled else "local-json",
            "embeddingFunction": self.function_name if self.vector_enabled else None,
            "matchThreshold": DEFAULT_MATCH_THRESHOLD,
        }

    def ingest_from_analysis(
        self,
        analysis: JsonObject,
        *,
        detection: JsonObject | None = None,
        text: str | None = None,
        notify: bool = True,
    ) -> JsonObject:
        evidence = analysis.get("evidence") if isinstance(analysis.get("evidence"), dict) else None
        if not evidence:
            return {"stored": False, "reason": "missing_evidence"}
        return self.ingest_evidence(evidence, detection=detection, analysis=analysis, text=text, notify=notify)

    def ingest_evidence(
        self,
        evidence: JsonObject,
        *,
        detection: JsonObject | None = None,
        analysis: JsonObject | None = None,
        text: str | None = None,
        notify: bool = True,
    ) -> JsonObject:
        item = self._build_item(evidence, detection=detection, analysis=analysis or {}, text=text)
        if not item["content"].strip():
            return {"stored": False, "reason": "empty_content"}
        stored = self._upsert_item(item)
        correlation = self.correlate_item(stored, notify=notify)
        return {"stored": True, "item": stored, "correlation": correlation}

    def ingest_manual(self, payload: JsonObject) -> JsonObject:
        evidence_id = str(payload.get("evidenceId") or "").strip()
        if evidence_id:
            bundle = self.store.get_bundle(evidence_id)
            if not bundle:
                raise LookupError("Evidence not found.")
            detection = {
                "score": bundle["evidence"].get("detectionScore") or 0,
                "max_score": bundle["evidence"].get("detectionMaxScore") or 50,
                "categories": bundle["evidence"].get("detectionCategories") or [],
                "matches": bundle["evidence"].get("detectionMatches") or [],
            }
            return self.ingest_evidence(bundle["evidence"], detection=detection, analysis=bundle)

        content = redact_text(str(payload.get("content") or ""))
        if not content:
            raise ValueError("content or evidenceId is required.")
        now = utc_now()
        content_hash = stable_hash(content)
        source_ref = f"manual:{content_hash[:24]}"
        memory_type = str(payload.get("memoryType") or "manual-signal")
        severity = normalize_severity(payload.get("severity"), "medium")
        item = {
            "id": str(uuid4()),
            "memory_type": memory_type,
            "memoryType": memory_type,
            "source": "manual",
            "source_ref": source_ref,
            "sourceRef": source_ref,
            "source_evidence_id": None,
            "sourceEvidenceId": None,
            "content": content,
            "content_hash": content_hash,
            "contentHash": content_hash,
            "fingerprint_hash": stable_hash(fingerprint_from_content(content)),
            "fingerprintHash": stable_hash(fingerprint_from_content(content)),
            "severity": severity,
            "status": "active",
            "metadata": {
                "memoryType": memory_type,
                "confirmed": False,
                "sourceEvidenceId": None,
            },
            "created_at": now,
            "createdAt": now,
            "updated_at": now,
            "updatedAt": now,
        }
        stored = self._upsert_item(item)
        return {"stored": True, "item": stored, "correlation": self.correlate_item(stored)}

    def search(
        self,
        query: str,
        *,
        threshold: float = DEFAULT_MATCH_THRESHOLD,
        match_count: int = DEFAULT_MATCH_COUNT,
        exclude_source_ref: str | None = None,
    ) -> JsonObject:
        redacted = redact_text(query)
        if not redacted:
            return {"query": redacted, "matches": []}

        if self.vector_enabled:
            try:
                embedding = self._embed(redacted)
                if embedding:
                    rows = self.store._supabase_json(
                        "POST",
                        "/rest/v1/rpc/match_examshield_memory",
                        {
                            "query_embedding": embedding,
                            "match_threshold": threshold,
                            "match_count": match_count,
                            "exclude_source_ref": exclude_source_ref,
                        },
                    )
                    if isinstance(rows, list):
                        return {
                            "query": redacted,
                            "matches": [normalize_item(row) for row in rows if isinstance(row, dict)],
                        }
            except Exception as exc:
                logger.warning("Supabase vector memory search failed; using fallback: %s", exc)

        matches: list[JsonObject] = []
        query_tokens = content_tokens(redacted)
        for item in self._list_items(limit=200):
            if exclude_source_ref and item.get("sourceRef") == exclude_source_ref:
                continue
            similarity = jaccard(query_tokens, content_tokens(str(item.get("content") or "")))
            if similarity >= threshold:
                matches.append({**item, "similarity": similarity})
        matches.sort(key=lambda row: float(row.get("similarity") or 0), reverse=True)
        return {"query": redacted, "matches": matches[:match_count]}

    def get_memory(self, memory_id: str) -> JsonObject | None:
        for item in self._list_items(limit=500):
            if str(item.get("id")) == str(memory_id):
                related = self.correlate_item(item, notify=False)
                return {"item": item, "correlation": related}
        return None

    def correlate_memory_id(self, memory_id: str) -> JsonObject:
        found = self.get_memory(memory_id)
        if not found:
            raise LookupError("Memory item not found.")
        return found["correlation"] or {"correlated": False, "reason": "insufficient_sources"}

    def correlate_item(self, item: JsonObject, *, notify: bool = True) -> JsonObject | None:
        matches = self.search(
            str(item.get("content") or ""),
            threshold=DEFAULT_MATCH_THRESHOLD,
            match_count=DEFAULT_MATCH_COUNT,
            exclude_source_ref=str(item.get("sourceRef") or item.get("source_ref") or ""),
        )["matches"]
        exact_matches = self._items_by_fingerprint(str(item.get("fingerprintHash") or item.get("fingerprint_hash") or ""))
        combined = combine_matches(item, matches, exact_matches)
        confirmed = bool((item.get("metadata") or {}).get("confirmed"))

        evidence_ids = distinct(
            str(row.get("sourceEvidenceId") or row.get("source_evidence_id") or "")
            for row in combined
            if row.get("sourceEvidenceId") or row.get("source_evidence_id")
        )
        source_refs = distinct(
            str(row.get("sourceRef") or row.get("source_ref") or "")
            for row in combined
            if row.get("sourceRef") or row.get("source_ref")
        )
        source_count = len(evidence_ids) if evidence_ids else len(source_refs)
        if not confirmed and source_count < 2:
            return None

        max_similarity = max([float(row.get("similarity") or 0) for row in combined] or [1.0 if confirmed else 0.0])
        correlation_key = f"memory:{str(item.get('fingerprintHash') or item.get('fingerprint_hash'))[:32]}"
        summary = correlation_summary(item, combined, source_count, confirmed)
        severity = highest_severity([str(row.get("severity") or "low") for row in combined])
        if confirmed:
            severity = highest_severity([severity, "critical"])

        now = utc_now()
        existing = self._read_correlation(correlation_key)
        correlation = {
            **(existing or {}),
            "id": (existing or {}).get("id") or str(uuid4()),
            "correlation_key": correlation_key,
            "correlationKey": correlation_key,
            "trigger_memory_id": item.get("id"),
            "triggerMemoryId": item.get("id"),
            "memory_ids": [str(row.get("id")) for row in combined if row.get("id")],
            "memoryIds": [str(row.get("id")) for row in combined if row.get("id")],
            "evidence_ids": evidence_ids,
            "evidenceIds": evidence_ids,
            "source_count": source_count,
            "sourceCount": source_count,
            "max_similarity": round(max_similarity, 4),
            "maxSimilarity": round(max_similarity, 4),
            "severity": severity,
            "status": (existing or {}).get("status") or "open",
            "summary": summary,
            "metadata": {
                "confirmed": confirmed,
                "paperId": first_metadata(combined, "paperId"),
                "centerCode": first_metadata(combined, "centerCode"),
                "watermarkId": first_metadata(combined, "watermarkId"),
                "memoryTypes": distinct(str(row.get("memoryType") or row.get("memory_type") or "") for row in combined),
            },
            "created_at": (existing or {}).get("createdAt") or (existing or {}).get("created_at") or now,
            "createdAt": (existing or {}).get("createdAt") or (existing or {}).get("created_at") or now,
            "updated_at": now,
            "updatedAt": now,
        }
        alert = self._create_memory_alert(correlation, item, notify=notify and not existing)
        if alert:
            correlation["alert_id"] = alert.get("alertId")
            correlation["alertId"] = alert.get("alertId")
        return self._upsert_correlation(correlation)

    def _build_item(
        self,
        evidence: JsonObject,
        *,
        detection: JsonObject | None,
        analysis: JsonObject,
        text: str | None,
    ) -> JsonObject:
        evidence_id = str(evidence.get("evidenceId") or "")
        report = dict_value(analysis.get("forensicReport") or analysis.get("forensic_report"))
        attribution = dict_value(analysis.get("attribution"))
        watermark = dict_value(analysis.get("watermark"))
        ocr_text = text if text is not None else str(evidence.get("ocrText") or "")
        detection = detection or {
            "score": evidence.get("detectionScore") or 0,
            "max_score": evidence.get("detectionMaxScore") or 50,
            "categories": evidence.get("detectionCategories") or [],
            "matches": evidence.get("detectionMatches") or [],
        }
        confirmed = is_confirmed_match(report, watermark)
        memory_type = "confirmed-match" if confirmed else "security-signal"
        severity = memory_severity(detection, report, confirmed)
        metadata = whitelisted_metadata(evidence, detection, report, attribution, watermark, memory_type, confirmed)
        content = build_memory_content(evidence_id, ocr_text, detection, metadata)
        fingerprint = fingerprint_from_metadata(content, metadata, detection)
        now = utc_now()
        source_ref = f"evidence:{evidence_id}:{memory_type}"
        content_hash = stable_hash(content)
        fingerprint_hash = stable_hash(fingerprint)
        return {
            "id": str(uuid4()),
            "memory_type": memory_type,
            "memoryType": memory_type,
            "source": "examshield",
            "source_ref": source_ref,
            "sourceRef": source_ref,
            "source_evidence_id": evidence_id,
            "sourceEvidenceId": evidence_id,
            "content": content,
            "content_hash": content_hash,
            "contentHash": content_hash,
            "fingerprint_hash": fingerprint_hash,
            "fingerprintHash": fingerprint_hash,
            "severity": severity,
            "status": "active",
            "metadata": metadata,
            "created_at": now,
            "createdAt": now,
            "updated_at": now,
            "updatedAt": now,
        }

    def _upsert_item(self, item: JsonObject) -> JsonObject:
        existing = self._read_item_by_source_ref(str(item.get("sourceRef") or item.get("source_ref") or ""))
        if existing:
            item = {
                **existing,
                **item,
                "id": existing.get("id"),
                "created_at": existing.get("createdAt") or existing.get("created_at") or item.get("created_at"),
                "createdAt": existing.get("createdAt") or existing.get("created_at") or item.get("createdAt"),
                "updated_at": utc_now(),
                "updatedAt": utc_now(),
            }

        if self.vector_enabled:
            try:
                embedding = self._embed(str(item.get("content") or ""))
                payload = denormalize_item({**item, "embedding": embedding})
                rows = self.store._supabase_json(
                    "POST",
                    "/rest/v1/examshield_memory_items?on_conflict=source_ref&select=*",
                    payload,
                    extra_headers={"Prefer": "resolution=merge-duplicates,return=representation"},
                )
                if isinstance(rows, list) and rows:
                    normalized = normalize_item(rows[0])
                    self._mirror_item_document(normalized)
                    return normalized
            except Exception as exc:
                logger.warning("Supabase memory upsert failed; using local document fallback: %s", exc)

        filename = f"{stable_hash(str(item.get('sourceRef') or item.get('source_ref')))[:32]}.json"
        self.store._write_json(MEMORY_ITEMS, filename, normalize_item(item))
        return normalize_item(item)

    def _upsert_correlation(self, correlation: JsonObject) -> JsonObject:
        if self.vector_enabled:
            try:
                rows = self.store._supabase_json(
                    "POST",
                    "/rest/v1/examshield_memory_correlations?on_conflict=correlation_key&select=*",
                    denormalize_correlation(correlation),
                    extra_headers={"Prefer": "resolution=merge-duplicates,return=representation"},
                )
                if isinstance(rows, list) and rows:
                    normalized = normalize_correlation(rows[0])
                    self._mirror_correlation_document(normalized)
                    return normalized
            except Exception as exc:
                logger.warning("Supabase memory correlation upsert failed; using local fallback: %s", exc)
        filename = f"{stable_hash(str(correlation.get('correlationKey') or correlation.get('correlation_key')))[:32]}.json"
        self.store._write_json(MEMORY_CORRELATIONS, filename, normalize_correlation(correlation))
        return normalize_correlation(correlation)

    def _read_item_by_source_ref(self, source_ref: str) -> JsonObject | None:
        if not source_ref:
            return None
        if self.vector_enabled:
            try:
                encoded = urllib.parse.quote(source_ref)
                rows = self.store._supabase_json(
                    "GET",
                    f"/rest/v1/examshield_memory_items?source_ref=eq.{encoded}&select=*&limit=1",
                )
                if isinstance(rows, list) and rows:
                    return normalize_item(rows[0])
            except Exception as exc:
                logger.warning("Supabase memory lookup failed: %s", exc)
        return next((item for item in self.store._read_json_dir(MEMORY_ITEMS) if item.get("sourceRef") == source_ref), None)

    def _read_correlation(self, correlation_key: str) -> JsonObject | None:
        if self.vector_enabled:
            try:
                encoded = urllib.parse.quote(correlation_key)
                rows = self.store._supabase_json(
                    "GET",
                    f"/rest/v1/examshield_memory_correlations?correlation_key=eq.{encoded}&select=*&limit=1",
                )
                if isinstance(rows, list) and rows:
                    return normalize_correlation(rows[0])
            except Exception as exc:
                logger.warning("Supabase memory correlation lookup failed: %s", exc)
        return next(
            (
                item
                for item in self.store._read_json_dir(MEMORY_CORRELATIONS)
                if item.get("correlationKey") == correlation_key
            ),
            None,
        )

    def _list_items(self, *, limit: int = 100) -> list[JsonObject]:
        if self.vector_enabled:
            try:
                rows = self.store._supabase_json(
                    "GET",
                    f"/rest/v1/examshield_memory_items?select=*&order=created_at.desc&limit={limit}",
                )
                if isinstance(rows, list):
                    return [normalize_item(row) for row in rows if isinstance(row, dict)]
            except Exception as exc:
                logger.warning("Supabase memory list failed; using local fallback: %s", exc)
        return sorted(
            self.store._read_json_dir(MEMORY_ITEMS),
            key=lambda row: str(row.get("createdAt") or ""),
            reverse=True,
        )[:limit]

    def _items_by_fingerprint(self, fingerprint_hash: str) -> list[JsonObject]:
        if not fingerprint_hash:
            return []
        return [
            {**item, "similarity": 1.0}
            for item in self._list_items(limit=200)
            if str(item.get("fingerprintHash") or item.get("fingerprint_hash")) == fingerprint_hash
        ]

    def _mirror_item_document(self, item: JsonObject) -> None:
        filename = f"{stable_hash(str(item.get('sourceRef') or item.get('source_ref')))[:32]}.json"
        try:
            self.store._write_json(MEMORY_ITEMS, filename, normalize_item(item))
        except Exception as exc:
            logger.warning("Failed to mirror memory item into document feed: %s", exc)

    def _mirror_correlation_document(self, correlation: JsonObject) -> None:
        filename = f"{stable_hash(str(correlation.get('correlationKey') or correlation.get('correlation_key')))[:32]}.json"
        try:
            self.store._write_json(MEMORY_CORRELATIONS, filename, normalize_correlation(correlation))
        except Exception as exc:
            logger.warning("Failed to mirror memory correlation into document feed: %s", exc)

    def _embed(self, content: str) -> list[float] | None:
        if not self.vector_enabled:
            return None
        request = urllib.request.Request(
            f"{self.store.settings.supabase_url}/functions/v1/{self.function_name}",
            data=json.dumps({"input": content[:8000]}).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.store.settings.supabase_service_role_key}",
                "apikey": self.store.settings.supabase_service_role_key,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.store.settings.supabase_timeout_seconds) as response:
            parsed = json.loads(response.read().decode("utf-8"))
        embedding = parsed.get("embedding") if isinstance(parsed, dict) else None
        return list(embedding) if isinstance(embedding, list) else None

    def _create_memory_alert(
        self,
        correlation: JsonObject,
        trigger_item: JsonObject,
        *,
        notify: bool,
    ) -> JsonObject | None:
        existing = next(
            (
                alert
                for alert in self.store._read_json_dir("alerts")
                if alert.get("memoryCorrelationId") == correlation.get("correlationKey")
            ),
            None,
        )
        if existing:
            return existing

        metadata = correlation.get("metadata") if isinstance(correlation.get("metadata"), dict) else {}
        evidence_ids = correlation.get("evidenceIds") if isinstance(correlation.get("evidenceIds"), list) else []
        now = utc_now()
        alert = {
            "alertId": "MEM-" + stable_hash(str(correlation.get("correlationKey")))[:12].upper(),
            "evidenceId": (evidence_ids or [trigger_item.get("sourceEvidenceId") or "MEMORY"])[0],
            "paperId": metadata.get("paperId"),
            "centerCode": metadata.get("centerCode"),
            "watermarkId": metadata.get("watermarkId"),
            "confidence": max(80, min(100, round(float(correlation.get("maxSimilarity") or 0.8) * 100))),
            "risk": correlation.get("severity") or "medium",
            "createdAt": now,
            "status": "open",
            "memoryCorrelationId": correlation.get("correlationKey"),
            "memorySourceCount": correlation.get("sourceCount"),
            "memorySimilarity": correlation.get("maxSimilarity"),
            "summary": correlation.get("summary"),
        }
        self.store._write_json("alerts", f"memory-{stable_hash(str(correlation.get('correlationKey')))[:32]}.json", alert)
        self.store.record_activity(
            {
                "type": "memory-correlation-generated",
                "title": "Unified Memory Alert",
                "evidenceId": str(alert["evidenceId"]),
                "timestamp": now,
                "detail": str(correlation.get("summary") or "Unified memory correlation detected."),
            }
        )
        if notify:
            self._notify_team(alert, correlation)
        return alert

    def _notify_team(self, alert: JsonObject, correlation: JsonObject) -> None:
        if not self.telegram:
            return
        settings = getattr(self.telegram, "settings", None)
        token = str(getattr(settings, "telegram_bot_token", "") or "")
        chat_id = str(getattr(settings, "telegram_admin_chat_id", "") or "")
        if not token or not chat_id or token == "test-token":
            return
        text = (
            "<b>ExamShield memory alert</b>\n\n"
            f"{escape(str(correlation.get('summary') or 'Threat memory correlation detected.'))}\n\n"
            f"Sources: <b>{escape(str(correlation.get('sourceCount') or 0))}</b>\n"
            f"Severity: <b>{escape(str(alert.get('risk') or 'medium')).upper()}</b>\n"
            f"Alert: <code>{escape(str(alert.get('alertId') or ''))}</code>"
        )
        try:
            self.telegram.send_message(chat_id, text, parse_mode="HTML")
        except Exception as exc:
            logger.warning("Memory team Telegram alert failed: %s", exc)


def redact_text(value: str) -> str:
    text = str(value or "")
    text = EMAIL_RE.sub("[redacted-email]", text)
    text = URL_RE.sub("[redacted-url]", text)
    text = USERNAME_RE.sub("[redacted-user]", text)
    text = PHONE_RE.sub("[redacted-phone]", text)
    text = LONG_ID_RE.sub("[redacted-id]", text)
    return " ".join(text.split())[:4000]


def build_memory_content(
    evidence_id: str,
    ocr_text: str,
    detection: JsonObject | None,
    metadata: JsonObject,
) -> str:
    matches = detection.get("matches") if isinstance((detection or {}).get("matches"), list) else []
    categories = detection.get("categories") if isinstance((detection or {}).get("categories"), list) else []
    parts = [
        f"Evidence: {evidence_id}",
        f"Memory type: {metadata.get('memoryType')}",
        f"Severity: {metadata.get('detectionSeverity') or metadata.get('riskLevel') or 'unknown'}",
    ]
    if categories:
        parts.append("Detection categories: " + ", ".join(sorted(str(item) for item in categories)))
    if matches:
        match_text = ", ".join(
            redact_text(str(item.get("text") or item.get("description") or ""))
            for item in matches[:8]
            if isinstance(item, dict)
        )
        if match_text:
            parts.append("Detection evidence: " + match_text)
    for label, key in (("Paper", "paperId"), ("Watermark", "watermarkId"), ("Center", "centerCode")):
        if metadata.get(key):
            parts.append(f"{label}: {metadata[key]}")
    if ocr_text:
        parts.append("OCR snippet: " + redact_text(ocr_text)[:1600])
    return "\n".join(part for part in parts if part)


def whitelisted_metadata(
    evidence: JsonObject,
    detection: JsonObject | None,
    report: JsonObject,
    attribution: JsonObject,
    watermark: JsonObject,
    memory_type: str,
    confirmed: bool,
) -> JsonObject:
    return {
        "memoryType": memory_type,
        "sourceEvidenceId": evidence.get("evidenceId"),
        "fileType": evidence.get("fileType"),
        "paperId": report.get("paperIdentified") or attribution.get("matchedPaperId"),
        "centerCode": report.get("centerCode") or attribution.get("centerCode"),
        "watermarkId": report.get("watermarkId") or watermark.get("watermarkId") or attribution.get("matchedWatermarkId"),
        "riskLevel": report.get("riskLevel") or evidence.get("riskLevel"),
        "finalConfidence": report.get("finalConfidence") or attribution.get("finalConfidence"),
        "watermarkConfidence": watermark.get("confidence"),
        "detectionScore": (detection or {}).get("score"),
        "detectionMaxScore": (detection or {}).get("max_score") or 50,
        "detectionCategories": (detection or {}).get("categories") or [],
        "detectionSeverity": get_alert_severity(detection or {"score": 0}),
        "confirmed": confirmed,
    }


def fingerprint_from_metadata(content: str, metadata: JsonObject, detection: JsonObject | None) -> str:
    signals: list[str] = []
    for key in ("paperId", "watermarkId"):
        if metadata.get(key):
            signals.append(f"{key}:{str(metadata[key]).lower()}")
    categories = metadata.get("detectionCategories") if isinstance(metadata.get("detectionCategories"), list) else []
    signals.extend(f"category:{str(item).lower()}" for item in categories)
    matches = detection.get("matches") if isinstance((detection or {}).get("matches"), list) else []
    for item in matches[:6]:
        if isinstance(item, dict) and item.get("text"):
            signals.append("match:" + normalize_signal(str(item["text"])))
    if not signals:
        signals.append(fingerprint_from_content(content))
    return "|".join(sorted(set(item for item in signals if item)))


def fingerprint_from_content(content: str) -> str:
    return "|".join(content_tokens(content)[:16])


def content_tokens(content: str) -> list[str]:
    tokens = [normalize_signal(token) for token in TOKEN_RE.findall(content.lower())]
    return [token for token in tokens if len(token) > 2 and token not in STOPWORDS]


def normalize_signal(value: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "", value.lower())


def is_confirmed_match(report: JsonObject, watermark: JsonObject) -> bool:
    try:
        final_confidence = int(report.get("finalConfidence") or 0)
        watermark_confidence = int(watermark.get("confidence") or 0)
    except (TypeError, ValueError):
        return False
    if report.get("status") == "investigation-complete" and final_confidence >= 80:
        return True
    return watermark.get("status") == "detected" and watermark_confidence >= 90


def memory_severity(detection: JsonObject | None, report: JsonObject, confirmed: bool) -> str:
    if confirmed:
        return "critical"
    risk = normalize_severity(report.get("riskLevel"), "")
    if risk:
        return risk
    return get_alert_severity(detection or {"score": 0})


def normalize_severity(value: Any, fallback: str = "low") -> str:
    text = str(value or "").strip().lower()
    return text if text in SEVERITY_RANK else fallback


def highest_severity(values: list[str]) -> str:
    return max((normalize_severity(value) for value in values), key=lambda value: SEVERITY_RANK.get(value, 0))


def correlation_summary(item: JsonObject, rows: list[JsonObject], source_count: int, confirmed: bool) -> str:
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    if confirmed:
        paper = metadata.get("paperId") or "registered paper"
        center = metadata.get("centerCode") or "unknown center"
        return f"Confirmed high-confidence memory signal for {paper} from {center}."
    categories = first_metadata(rows, "detectionCategories") or []
    category_text = ", ".join(categories) if isinstance(categories, list) and categories else "security signal"
    return f"Unified memory linked {source_count} independent evidence records around {category_text}."


def combine_matches(item: JsonObject, *groups: list[JsonObject]) -> list[JsonObject]:
    by_id: dict[str, JsonObject] = {str(item.get("id")): {**item, "similarity": 1.0}}
    item_source = str(item.get("sourceRef") or item.get("source_ref") or "")
    for group in groups:
        for row in group:
            source_ref = str(row.get("sourceRef") or row.get("source_ref") or "")
            if source_ref and source_ref == item_source:
                continue
            key = str(row.get("id") or source_ref)
            existing = by_id.get(key)
            if not existing or float(row.get("similarity") or 0) > float(existing.get("similarity") or 0):
                by_id[key] = normalize_item(row)
    return list(by_id.values())


def first_metadata(rows: list[JsonObject], key: str) -> Any:
    for row in rows:
        metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        if metadata.get(key):
            return metadata[key]
    return None


def distinct(values: Any) -> list[str]:
    items: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in items:
            items.append(text)
    return items


def jaccard(left: list[str], right: list[str]) -> float:
    left_set = set(left)
    right_set = set(right)
    if not left_set or not right_set:
        return 0.0
    return len(left_set & right_set) / len(left_set | right_set)


def stable_hash(value: str) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def dict_value(value: Any) -> JsonObject:
    return value if isinstance(value, dict) else {}


def normalize_item(row: JsonObject) -> JsonObject:
    return {
        "id": str(row.get("id") or uuid4()),
        "memoryType": row.get("memoryType") or row.get("memory_type"),
        "source": row.get("source") or "examshield",
        "sourceRef": row.get("sourceRef") or row.get("source_ref"),
        "sourceEvidenceId": row.get("sourceEvidenceId") or row.get("source_evidence_id"),
        "content": row.get("content") or "",
        "contentHash": row.get("contentHash") or row.get("content_hash"),
        "fingerprintHash": row.get("fingerprintHash") or row.get("fingerprint_hash"),
        "severity": normalize_severity(row.get("severity"), "low"),
        "status": row.get("status") or "active",
        "metadata": row.get("metadata") if isinstance(row.get("metadata"), dict) else {},
        "similarity": row.get("similarity"),
        "createdAt": row.get("createdAt") or row.get("created_at"),
        "updatedAt": row.get("updatedAt") or row.get("updated_at"),
    }


def denormalize_item(row: JsonObject) -> JsonObject:
    return {
        "id": row.get("id"),
        "memory_type": row.get("memoryType") or row.get("memory_type"),
        "source": row.get("source") or "examshield",
        "source_ref": row.get("sourceRef") or row.get("source_ref"),
        "source_evidence_id": row.get("sourceEvidenceId") or row.get("source_evidence_id"),
        "content": row.get("content") or "",
        "content_hash": row.get("contentHash") or row.get("content_hash"),
        "fingerprint_hash": row.get("fingerprintHash") or row.get("fingerprint_hash"),
        "embedding": row.get("embedding"),
        "severity": normalize_severity(row.get("severity"), "low"),
        "status": row.get("status") or "active",
        "metadata": row.get("metadata") if isinstance(row.get("metadata"), dict) else {},
        "created_at": row.get("createdAt") or row.get("created_at"),
        "updated_at": row.get("updatedAt") or row.get("updated_at"),
    }


def normalize_correlation(row: JsonObject) -> JsonObject:
    return {
        "id": str(row.get("id") or uuid4()),
        "correlationKey": row.get("correlationKey") or row.get("correlation_key"),
        "triggerMemoryId": row.get("triggerMemoryId") or row.get("trigger_memory_id"),
        "memoryIds": row.get("memoryIds") or row.get("memory_ids") or [],
        "evidenceIds": row.get("evidenceIds") or row.get("evidence_ids") or [],
        "sourceCount": row.get("sourceCount") or row.get("source_count") or 0,
        "maxSimilarity": row.get("maxSimilarity") or row.get("max_similarity") or 0,
        "severity": normalize_severity(row.get("severity"), "medium"),
        "status": row.get("status") or "open",
        "alertId": row.get("alertId") or row.get("alert_id"),
        "summary": row.get("summary") or "",
        "metadata": row.get("metadata") if isinstance(row.get("metadata"), dict) else {},
        "createdAt": row.get("createdAt") or row.get("created_at"),
        "updatedAt": row.get("updatedAt") or row.get("updated_at"),
    }


def denormalize_correlation(row: JsonObject) -> JsonObject:
    return {
        "id": row.get("id"),
        "correlation_key": row.get("correlationKey") or row.get("correlation_key"),
        "trigger_memory_id": row.get("triggerMemoryId") or row.get("trigger_memory_id"),
        "memory_ids": row.get("memoryIds") or row.get("memory_ids") or [],
        "evidence_ids": row.get("evidenceIds") or row.get("evidence_ids") or [],
        "source_count": row.get("sourceCount") or row.get("source_count") or 0,
        "max_similarity": row.get("maxSimilarity") or row.get("max_similarity") or 0,
        "severity": normalize_severity(row.get("severity"), "medium"),
        "status": row.get("status") or "open",
        "alert_id": row.get("alertId") or row.get("alert_id"),
        "summary": row.get("summary") or "",
        "metadata": row.get("metadata") if isinstance(row.get("metadata"), dict) else {},
        "created_at": row.get("createdAt") or row.get("created_at"),
        "updated_at": row.get("updatedAt") or row.get("updated_at"),
    }
