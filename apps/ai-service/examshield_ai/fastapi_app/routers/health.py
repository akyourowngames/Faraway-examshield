"""Health and introspection routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from examshield_ai.ocr import SUPPORTED_TYPES, ocr_runtime_status

from ..deps import backend_secret, get_core
from ..responses import json_response

router = APIRouter()


@router.get("/health")
async def health(request: Request, _secret: None = Depends(backend_secret)) -> dict:
    core = get_core(request)
    settings = core.settings
    return json_response(
        {
            "status": "ok",
            "service": "examshield-ai",
            "model": settings.model,
            "nimConfigured": core.client.configured,
            "kiloConfigured": core.client.configured,
            "tools": core.registry.names(),
            "ocr": {
                "endpoint": "/ocr/analyze",
                "supportedTypes": sorted(SUPPORTED_TYPES.keys()),
                "runtime": ocr_runtime_status(),
                "workers": core.workers.stats(),
            },
            "uploadRoot": str(settings.upload_root),
            "registryPath": str(settings.registry_path),
            "storage": "supabase" if core.store.supabase_enabled else "local-json",
            "memory": core.memory.status(),
            "telegram": {
                "webhookConfigured": core.telegram.configured,
                "botTokenSet": bool(settings.telegram_bot_token),
                "publicUrl": settings.public_url or "NOT SET",
                "chatId": settings.telegram_chat_id or "NOT SET",
                "adminChatId": settings.telegram_admin_chat_id or "NOT SET",
            },
            "ocrWorkers": core.workers.stats(),
        },
        request=request,
        cache=False,
    )


@router.get("/tools")
async def tools(request: Request, _secret: None = Depends(backend_secret)) -> dict:
    core = get_core(request)
    return json_response({"tools": core.registry.schemas()}, request=request)
