"""Shared application state for the FastAPI transport.

``build_state`` mirrors ``build_handler`` in ``examshield_ai.server``: it wires
the same singleton cores the threaded handler used, held once on ``app.state``.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from examshield_ai.llm import KiloClient
from examshield_ai.memory import MemoryManager
from examshield_ai.pipeline import EvidencePipeline
from examshield_ai.ratelimit import RateLimiter, make_ocr_limiter, make_upload_limiter
from examshield_ai.response_cache import ReadResponseCache
from examshield_ai.settings import Settings
from examshield_ai.store import AgentStore, EvidenceStore
from examshield_ai.telegram import TelegramWebhook
from examshield_ai.tools import ExamshieldToolRegistry
from examshield_ai.workers import AnalysisWorkerPool


@dataclass
class AppState:
    settings: Settings
    store: EvidenceStore
    client: KiloClient
    telegram: TelegramWebhook
    workers: AnalysisWorkerPool
    pipeline: EvidencePipeline
    memory: MemoryManager
    agent_store: AgentStore
    registry: ExamshieldToolRegistry
    read_cache: ReadResponseCache
    ocr_limiter: RateLimiter
    upload_limiter: RateLimiter

    def as_handler_adapter(self) -> Any:
        """Expose the attributes the stdlib background helpers read off a handler.

        Used by ``app.py`` so the FastAPI lifespan can call the same Telegram
        receiver setup and stale-job sweeper helpers without coupling to the
        ``BaseHTTPRequestHandler`` subclass.
        """
        return SimpleNamespace(
            settings=self.settings,
            store=self.store,
            agent_store=self.agent_store,
            telegram=self.telegram,
            pipeline=self.pipeline,
        )


def build_state(settings: Settings) -> AppState:
    """Construct the shared cores. Mirrors ``build_handler``."""
    store = EvidenceStore(settings)
    telegram = TelegramWebhook(settings)
    workers = AnalysisWorkerPool()
    pipeline = EvidencePipeline(store, telegram, workers)
    return AppState(
        settings=settings,
        store=store,
        client=KiloClient(settings),
        telegram=telegram,
        workers=workers,
        pipeline=pipeline,
        memory=pipeline.memory,
        agent_store=AgentStore(store),
        registry=ExamshieldToolRegistry(store),
        read_cache=ReadResponseCache(settings.read_cache_ttl_seconds),
        ocr_limiter=make_ocr_limiter(),
        upload_limiter=make_upload_limiter(),
    )
