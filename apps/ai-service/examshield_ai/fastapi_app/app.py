"""FastAPI application factory for the ExamShield AI service.

Wires the shared cores via :func:`build_state`, starts the same background
threads as the stdlib ``main()``, and exposes routes through per-group routers.
"""
from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from examshield_ai.agent_telegram import AgentTelegramService
from examshield_ai.cors import allowed_cors_origins
from examshield_ai.fastapi_app import responses
from examshield_ai.fastapi_app.routers.agents import router as agents_router
from examshield_ai.fastapi_app.routers.chat import router as chat_router
from examshield_ai.fastapi_app.routers.evidence import router as evidence_router
from examshield_ai.fastapi_app.routers.health import router as health_router
from examshield_ai.fastapi_app.routers.realtime import router as realtime_router
from examshield_ai.fastapi_app.routers.registry import router as registry_router
from examshield_ai.fastapi_app.routers.reports import router as reports_router
from examshield_ai.fastapi_app.routers.telegram import router as telegram_router
from examshield_ai.fastapi_app.state import build_state
from examshield_ai.ocr import analyze_image
from examshield_ai.runtime import _start_stale_job_sweeper, configure_telegram_receiver
from examshield_ai.settings import Settings, load_settings

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    app = FastAPI(title="ExamShield AI", version="0.1")

    app.state.settings = settings
    app.state.core = build_state(settings)

    origins = allowed_cors_origins(settings.cors_origin)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-Examshield-Api-Key"],
    )

    responses.register_error_handlers(app)

    for router in (
        health_router,
        evidence_router,
        chat_router,
        telegram_router,
        registry_router,
        reports_router,
        agents_router,
        realtime_router,
    ):
        app.include_router(router)

    @app.get("/")
    async def root(request: Request):
        return responses.json_response({"error": "Not found"}, status=404, request=request)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        core = app.state.core
        adapter = core.as_handler_adapter()
        configure_telegram_receiver(adapter)
        try:
            cleaned = core.store.cleanup_stale_jobs(max_age_seconds=300)
            if cleaned:
                logger.info("Cleaned up %s stale analysis job(s) on startup", cleaned)
        except Exception as exc:  # noqa: BLE001
            logger.error("Stale job cleanup failed: %s", exc)
        try:
            core.store.warmup_cache()
            logger.info("Evidence cache warmed on startup")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Evidence cache warmup skipped: %s", exc)
        _start_stale_job_sweeper(core.store)
        threading.Thread(
            target=AgentTelegramService(core.agent_store, settings).start,
            daemon=True,
            name="agent-telegram-poll",
        ).start()
        try:
            recovered = core.pipeline.recover_interrupted_jobs(analyze_image)
            if recovered:
                logger.info("Re-queued %s interrupted OCR job(s) after restart", recovered)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Interrupted job recovery skipped: %s", exc)
        yield

    app.router.lifespan_context = lifespan
    return app


app = create_app(load_settings())
