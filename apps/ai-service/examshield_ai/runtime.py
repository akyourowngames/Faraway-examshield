from __future__ import annotations

import logging
import os
import threading
import time

from .ocr import analyze_image
from .store import EvidenceStore

logger = logging.getLogger(__name__)


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


def _start_global_telegram_poll(handler) -> None:
    """Start the global bot long-poll receiver unless a community agent owns the token.

    ``handler`` exposes ``settings``, ``store``, ``agent_store``, ``telegram``,
    and ``pipeline`` (both the FastAPI adapter and the old stdlib handler did).
    """
    global_token = handler.settings.telegram_bot_token or ""
    agent_owns_global = False
    if global_token:
        for agent in handler.agent_store.list_agents(status="active"):
            tg = handler.agent_store.get_telegram_config(str(agent.get("id") or ""))
            if not tg:
                continue
            if (
                str(tg.get("deploymentStatus", "")).lower() in ("connected", "deployed", "active")
                and str(tg.get("botToken") or "") == global_token
            ):
                agent_owns_global = True
                break

    if agent_owns_global:
        logger.info(
            "Global Telegram bot token is owned by a community agent — the agent poller "
            "will answer DMs as that agent; global assistant DM polling is skipped to avoid a getUpdates conflict."
        )
        return

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


def configure_telegram_receiver(handler) -> None:
    """Start the Telegram inbound receiver according to the configured bot.

    If ``TELEGRAM_BOT_TOKEN`` is unset this is a no-op that logs one clear
    warning instead of polling ``bot/getUpdates`` and emitting a 404 every
    cycle. With a token and ``PUBLIC_URL`` the webhook is used; otherwise the
    long-poll receiver starts (unless a community agent owns the same token).
    """
    if not handler.settings.telegram_bot_token:
        logger.warning("Telegram bot token not set — Telegram receiver disabled.")
        return

    try:
        handler.telegram.register()
        if handler.telegram.configured:
            logger.info(
                "Telegram webhook registered to %s/telegram/webhook",
                handler.settings.public_url,
            )
            return
        logger.warning(
            "Telegram webhook NOT registered (no EXAMSHIELD_PUBLIC_URL) — "
            "falling back to long-poll receiver."
        )
    except Exception as exc:
        logger.error("Telegram webhook registration failed: %s; falling back to long-poll.", exc)

    _start_global_telegram_poll(handler)
