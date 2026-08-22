"""Report generation and templates."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from examshield_ai.normalize import normalize_evidence_id
from examshield_ai.reports import (
    generate_evidence_report,
    generate_summary_report,
    report_to_document_bytes,
)
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


@router.get("/reports/templates")
async def report_templates(request: Request, _secret: None = Depends(backend_secret)) -> dict:
    return json_response(
        {
            "templates": [
                {"id": "evidence", "name": "Evidence Report", "description": "Detailed forensic report for a specific evidence item."},
                {"id": "summary", "name": "Dashboard Summary", "description": "High-level summary of all evidence, alerts, and investigations."},
            ]
        },
        request=request,
    )


@router.post("/reports/generate")
async def generate_report(request: Request, _secret: None = Depends(backend_secret)) -> dict:
    core = request.app.state.core
    payload = await _read_json(request)
    evidence_id = normalize_evidence_id(payload)
    report_type = str(payload.get("reportType") or ("evidence" if evidence_id else "summary")).strip()
    send_to_telegram = bool(payload.get("sendToTelegram"))
    telegram_chat_id = str(payload.get("chatId") or core.settings.telegram_admin_chat_id or "").strip()

    if report_type == "evidence" and evidence_id:
        md = generate_evidence_report(evidence_id, core.store)
        filename = f"report-{evidence_id}.md"
    else:
        md = generate_summary_report(core.store)
        filename = "report-dashboard-summary.md"
        evidence_id = ""

    result = {
        "report": md,
        "filename": filename,
        "length": len(md),
        "reportType": report_type,
        "evidenceId": evidence_id or None,
    }

    if send_to_telegram and telegram_chat_id:
        try:
            tg = TelegramWebhook(core.settings)
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
        except Exception as exc:
            result["sentToTelegram"] = False
            result["telegramError"] = str(exc)

    return json_response(result, request=request)
