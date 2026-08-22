from __future__ import annotations

import time
from typing import Any, Callable


class ReadResponseCache:
    """TTL cache for read-only HTTP GET responses.

    Several GET endpoints recompute their payload on every call (notably
    ``/telegram/status`` which hits the Telegram API, and the list endpoints that
    re-compose their JSON). Under repeated polling from the dashboard this is pure
    wasted work. A short-TTL in-memory cache keyed by request path+query lets
    identical requests within the window skip the recompute.
    """

    def __init__(self, ttl_seconds: float) -> None:
        self.ttl_seconds = float(ttl_seconds)
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        if self.ttl_seconds <= 0:
            return None
        item = self._store.get(key)
        if item is None:
            return None
        stamp, payload = item
        if (time.monotonic() - stamp) > self.ttl_seconds:
            self._store.pop(key, None)
            return None
        return payload

    def put(self, key: str, payload: Any) -> None:
        if self.ttl_seconds <= 0:
            return
        self._store[key] = (time.monotonic(), payload)

    def clear(self) -> None:
        self._store.clear()


def cached_get(cache: ReadResponseCache, key: str, producer: Callable[[], Any]) -> Any:
    """Return the cached payload for ``key`` or compute, cache, and return it.

    The producer is only invoked on a cache miss. Exceptions from the producer are
    *not* cached — they propagate so the caller can render an error response.
    """
    cached = cache.get(key)
    if cached is not None:
        return cached
    payload = producer()
    cache.put(key, payload)
    return payload
