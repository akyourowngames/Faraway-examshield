"""ExamShield AI — Markdown report generation.

Two report types:
  * Per-evidence detail report  →  ``generate_evidence_report()``
  * Dashboard summary report    →  ``generate_summary_report()``

Both return a Markdown string.  ``report_to_document_bytes()`` converts
the Markdown to UTF-8 bytes ready for Telegram file upload.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .store import EvidenceStore, JsonObject


# ── Helpers ──────────────────────────────────────────────────────────

def _ts(value: str | None) -> str:
    """Human-readable timestamp from ISO string."""
    if not value:
        return "—"
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.strftime("%d %b %Y, %H:%M UTC")
    except (ValueError, TypeError):
        return str(value)[:19]


def _risk_emoji(level: str | None) -> str:
    return {
        "critical": "🔴",
        "high": "🟠",
        "medium": "🟡",
        "low": "🟢",
    }.get(str(level or "").lower(), "⚪")


def _status_badge(status: str | None) -> str:
    return {
        "completed": "✅",
        "analyzing": "🔄",
        "pending-analysis": "⏳",
        "analysis-failed": "❌",
    }.get(str(status or ""), "❓")


def _safe(val: object) -> str:
    return str(val) if val else "—"


def _section(title: str) -> str:
    return f"\n## {title}\n"


def _kv(key: str, val: object) -> str:
    return f"**{key}:** {_safe(val)}\n"


# ── Per-evidence report ──────────────────────────────────────────────

def generate_evidence_report(evidence_id: str, store: "EvidenceStore") -> str:
    """Generate a detailed Markdown forensic report for a single evidence item."""
    bundle = store.get_bundle(evidence_id)
    if not bundle:
        return f"# Report Not Found\n\nEvidence `{evidence_id}` does not exist in the system.\n"

    evidence = bundle.get("evidence") or {}
    report = bundle.get("forensicReport") or {}
    attribution = bundle.get("attribution") or {}
    watermark = bundle.get("watermark") or {}
    alert = bundle.get("alert") or {}
    activity = bundle.get("activity") or []
    tg_events = bundle.get("telegramEvents") or []
    jobs = bundle.get("jobs") or []

    status = evidence.get("status", "unknown")
    risk = report.get("riskLevel") or evidence.get("riskLevel") or "unknown"
    confidence = report.get("finalConfidence") or evidence.get("ocrConfidence") or 0

    lines: list[str] = []

    # ── Header ──
    lines.append(f"# 🔍 ExamShield Evidence Report")
    lines.append(f"**Evidence ID:** `{evidence_id}`")
    lines.append(f"**Generated:** {_ts(_utc_now())}")
    lines.append(f"**Status:** {_status_badge(status)} {status}")
    lines.append(f"**Risk Level:** {_risk_emoji(risk)} {risk.upper()}")
    lines.append(f"**Confidence Score:** {confidence}%")
    lines.append("")

    # ── File Info ──
    lines.append(_section("📄 File Information"))
    lines.append(_kv("Filename", evidence.get("filename")))
    lines.append(_kv("File Type", evidence.get("fileType")))
    lines.append(_kv("Source", evidence.get("source")))
    lines.append(_kv("Uploaded At", _ts(evidence.get("uploadedAt"))))
    lines.append("")

    # ── Detection ──
    score = evidence.get("detectionScore")
    max_score = evidence.get("detectionMaxScore") or 50
    categories = evidence.get("detectionCategories") or []
    matches = evidence.get("detectionMatches") or []
    severity = evidence.get("detectionSeverity") or "unknown"

    lines.append(_section("🎯 Detection Analysis"))
    lines.append(_kv("Score", f"{score}/{max_score}" if score is not None else "—"))
    lines.append(_kv("Severity", severity.upper()))
    if categories:
        lines.append(_kv("Categories", ", ".join(categories)))
    if matches:
        lines.append("**Matched Keywords:**\n")
        for m in matches[:10]:
            kw_text = m.get("text") or "—"
            kw_cat = m.get("category") or ""
            kw_desc = m.get("description") or ""
            lines.append(f"- `{kw_text}` ({kw_cat}) — {kw_desc}")
    lines.append("")

    # ── OCR ──
    lines.append(_section("📝 OCR Extraction"))
    lines.append(_kv("OCR Status", evidence.get("ocrStatus")))
    lines.append(_kv("OCR Confidence", f"{evidence.get('ocrConfidence')}%" if evidence.get("ocrConfidence") is not None else "—"))
    lines.append(_kv("Processing Time", f"{evidence.get('ocrProcessingTimeMs')}ms" if evidence.get("ocrProcessingTimeMs") else "—"))
    ocr_text = evidence.get("ocrText") or ""
    if ocr_text:
        lines.append("**Extracted Text Preview:**\n")
        preview = ocr_text[:500]
        if len(ocr_text) > 500:
            preview += f"\n... ({len(ocr_text)} chars total)"
        lines.append(f"```\n{preview}\n```\n")
    lines.append("")

    # ── Attribution ──
    if attribution.get("status") and attribution["status"] != "no-match":
        lines.append(_section("🔗 Paper Attribution"))
        lines.append(_kv("Matched Paper", attribution.get("matchedPaperId")))
        lines.append(_kv("Exam", attribution.get("matchedExam")))
        lines.append(_kv("Paper Set", attribution.get("matchedSet")))
        lines.append(_kv("Center Code", attribution.get("centerCode")))
        lines.append(_kv("Center Name", attribution.get("centerName")))
        lines.append(_kv("City", attribution.get("city")))
        lines.append(_kv("State", attribution.get("state")))
        lines.append(_kv("Printer ID", attribution.get("printerId")))
        lines.append(_kv("Batch ID", attribution.get("batchId")))
        lines.append(_kv("Match Confidence", f"{attribution.get('confidence')}%"))
        lines.append(_kv("Final Confidence", f"{attribution.get('finalConfidence')}%"))
        lines.append("")

    # ── Watermark ──
    if watermark.get("watermarkId") or watermark.get("status") == "detected":
        lines.append(_section("💧 Watermark Analysis"))
        lines.append(_kv("Watermark ID", watermark.get("watermarkId")))
        lines.append(_kv("Status", watermark.get("status")))
        lines.append(_kv("Extraction Confidence", f"{watermark.get('confidence')}%" if watermark.get("confidence") is not None else "—"))
        lines.append(_kv("Extracted At", _ts(watermark.get("extractedAt"))))
        lines.append("")

    # ── Forensic Report ──
    if report.get("status"):
        lines.append(_section("🔬 Forensic Report"))
        lines.append(_kv("Report ID", report.get("reportId")))
        lines.append(_kv("Status", report.get("status")))
        lines.append(_kv("Paper Identified", report.get("paperIdentified") or "Not identified"))
        lines.append(_kv("Center Code", report.get("centerCode")))
        lines.append(_kv("Risk Level", f"{_risk_emoji(risk)} {risk}"))
        lines.append(_kv("Final Confidence", f"{report.get('finalConfidence', 0)}%"))
        lines.append(_kv("Comparison", report.get("comparisonStatus")))
        lines.append(_kv("Registry References", report.get("referenceCount")))
        lines.append("")

    # ── Alert ──
    if alert.get("alertId"):
        lines.append(_section("🚨 Alert Details"))
        lines.append(_kv("Alert ID", alert.get("alertId")))
        lines.append(_kv("Risk", alert.get("risk")))
        lines.append(_kv("Paper ID", alert.get("paperId")))
        lines.append(_kv("Center Code", alert.get("centerCode")))
        lines.append(_kv("Created", _ts(alert.get("createdAt"))))
        lines.append(_kv("Status", alert.get("status")))
        lines.append("")

    # ── Telegram Events ──
    if tg_events:
        lines.append(_section("📱 Telegram Source Events"))
        for evt in tg_events[:5]:
            lines.append(f"- **{_ts(evt.get('timestamp'))}** — chat `{evt.get('chatId')}`")
            evt_text = (evt.get("text") or "")[:120]
            if evt_text:
                lines.append(f"  > {evt_text}")
        lines.append("")

    # ── Analysis Jobs ──
    if jobs:
        lines.append(_section("⚙️ Analysis Jobs"))
        for job in jobs:
            lines.append(f"- `{job.get('jobId', '?')[:12]}…` — {job.get('status')} ({_ts(job.get('createdAt'))})")
        lines.append("")

    # ── Timeline ──
    if activity:
        lines.append(_section("📅 Investigation Timeline"))
        sorted_activity = sorted(activity, key=lambda a: a.get("timestamp") or "")
        for evt in sorted_activity[:30]:
            ts = _ts(evt.get("timestamp"))
            title = evt.get("title") or evt.get("type") or "event"
            detail = evt.get("detail") or ""
            detail_str = f" — {detail}" if detail else ""
            lines.append(f"- **{ts}** {title}{detail_str}")
        lines.append("")

    # ── Footer ──
    lines.append("---")
    lines.append(f"*Generated by ExamShield AI on {_ts(_utc_now())}*")

    return "\n".join(lines)


# ── Dashboard summary report ─────────────────────────────────────────

def generate_summary_report(store: "EvidenceStore") -> str:
    """Generate a high-level Markdown summary of the entire evidence system."""
    data = store.list_evidence()

    evidence_list = data.get("evidence") or []
    alerts = data.get("alerts") or []
    reports = data.get("forensicReports") or []
    tg_events = data.get("telegramEvents") or []
    activity = data.get("activity") or []
    stats = data.get("stats") or {}

    # Compute additional stats
    total = stats.get("totalEvidence", len(evidence_list))
    completed = stats.get("completed", 0)
    processing = stats.get("processing", 0)
    pending = stats.get("pendingAnalysis", 0)
    failed = stats.get("failed", 0)
    suspicious = [e for e in evidence_list if (e.get("detectionScore") or 0) > 7]
    high_risk = [e for e in evidence_list if e.get("riskLevel") in ("critical", "high")]
    matched = [r for r in reports if r.get("status") == "investigation-complete"]
    open_alerts = [a for a in alerts if a.get("status") == "open"]

    lines: list[str] = []

    # ── Header ──
    lines.append("# 📊 ExamShield Dashboard Report")
    lines.append(f"**Generated:** {_ts(_utc_now())}")
    lines.append("")

    # ── Stats Overview ──
    lines.append(_section("📈 Evidence Overview"))
    lines.append(f"| Metric | Count |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Total Evidence | **{total}** |")
    lines.append(f"| ✅ Completed | {completed} |")
    lines.append(f"| 🔄 Analyzing | {processing} |")
    lines.append(f"| ⏳ Pending | {pending} |")
    lines.append(f"| ❌ Failed | {failed} |")
    lines.append(f"| 🎯 Suspicious (score>7) | **{len(suspicious)}** |")
    lines.append(f"| 🔴 High/Critical Risk | **{len(high_risk)}** |")
    lines.append("")

    # ── Threat Posture ──
    lines.append(_section("🛡️ Threat Posture"))
    if suspicious:
        lines.append("| Evidence | Filename | Score | Risk | Source |")
        lines.append("|----------|----------|-------|------|--------|")
        for e in suspicious[:10]:
            lines.append(
                f"| `{e.get('evidenceId', '?')}` "
                f"| {e.get('filename', '?')[:25]} "
                f"| **{e.get('detectionScore', 0)}** "
                f"| {_risk_emoji(e.get('riskLevel'))} {e.get('riskLevel', '?')} "
                f"| {e.get('source', '?')} |"
            )
        lines.append("")
    else:
        lines.append("✅ No suspicious items detected.\n")

    # ── Open Alerts ──
    if open_alerts:
        lines.append(_section("🚨 Open Alerts"))
        for alert in open_alerts[:10]:
            lines.append(
                f"- **{alert.get('alertId', '?')}** — "
                f"paper={alert.get('paperId') or 'unknown'} | "
                f"center={alert.get('centerCode') or 'unknown'} | "
                f"risk={alert.get('risk', '?')} | "
                f"confidence={alert.get('confidence', '?')}%"
            )
        lines.append("")

    # ── Forensic Investigations ──
    if matched:
        lines.append(_section("🔬 Completed Investigations"))
        for rpt in matched[:10]:
            lines.append(
                f"- **{rpt.get('reportId', '?')}** — "
                f"paper={rpt.get('paperIdentified') or 'N/A'} | "
                f"center={rpt.get('centerCode') or 'N/A'} | "
                f"confidence={rpt.get('finalConfidence', 0)}% | "
                f"risk={rpt.get('riskLevel', '?')}"
            )
        lines.append("")

    # ── Telegram Monitoring ──
    lines.append(_section("📱 Telegram Monitoring"))
    lines.append(_kv("Events Captured", len(tg_events)))
    monitored = store.list_monitored_groups()
    lines.append(_kv("Monitored Groups", len(monitored)))
    if tg_events:
        lines.append("**Recent Events:**\n")
        for evt in tg_events[:5]:
            evt_text = (evt.get("text") or "")[:60]
            lines.append(
                f"- **{_ts(evt.get('timestamp'))}** — "
                f"chat `{evt.get('chatId', '?')}` "
                f"score={evt.get('detectionScore', 0)}"
            )
            if evt_text:
                lines.append(f"  > {evt_text}")
        lines.append("")

    # ── Recent Activity Timeline ──
    if activity:
        lines.append(_section("📅 Recent Activity (last 20 events)"))
        sorted_activity = sorted(activity, key=lambda a: a.get("timestamp") or "", reverse=True)
        for evt in sorted_activity[:20]:
            ts = _ts(evt.get("timestamp"))
            title = evt.get("title") or evt.get("type") or "event"
            detail = evt.get("detail") or ""
            eid = evt.get("evidenceId") or ""
            eid_str = f" [{eid}]" if eid else ""
            detail_str = f" — {detail}" if detail else ""
            lines.append(f"- **{ts}** {title}{eid_str}{detail_str}")
        lines.append("")

    # ── Footer ──
    lines.append("---")
    lines.append(f"*Generated by ExamShield AI on {_ts(_utc_now())}*")

    return "\n".join(lines)


# ── Utility ──────────────────────────────────────────────────────────

def report_to_document_bytes(markdown: str) -> bytes:
    """Convert a Markdown report to UTF-8 bytes for Telegram upload."""
    return markdown.encode("utf-8")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
