"""Server-Sent-Events bridge for ``POST /chat``.

``ChatSession.run`` is synchronous and may block for the full model stream. This
bridge runs it in a thread-pool executor and forwards each event it emits as an
SSE frame.
"""
from __future__ import annotations

import asyncio
import logging
import queue
from collections.abc import Callable
from typing import Any

from fastapi.responses import StreamingResponse

from examshield_ai.events import sse_bytes

logger = logging.getLogger(__name__)

_DONE = object()


def sse_from_chat_session(
    run_session: Callable[[Callable[[dict[str, Any]], None]], None],
) -> StreamingResponse:
    """Wrap a blocking chat runner as an SSE ``StreamingResponse``."""
    sync_q: "queue.Queue[Any]" = queue.Queue()

    def write_event(event: dict[str, Any]) -> None:
        sync_q.put(event)

    async def event_generator():
        loop = asyncio.get_running_loop()

        async def pump():
            try:
                await loop.run_in_executor(None, run_session, write_event)
            except Exception as exc:  # noqa: BLE001
                logger.error("Chat stream failed: %s", exc, exc_info=True)
                write_event({"type": "error", "message": str(exc) or "Chat failed."})
                write_event({"type": "done"})
            finally:
                write_event(_DONE)

        task = asyncio.create_task(pump())
        try:
            while True:
                item = await loop.run_in_executor(None, sync_q.get)
                if item is _DONE:
                    break
                yield sse_bytes(item)
        finally:
            await task

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
