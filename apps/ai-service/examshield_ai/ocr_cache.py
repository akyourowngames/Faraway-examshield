from __future__ import annotations

import hashlib
import time
from collections import OrderedDict
from typing import Any


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class OcrResultCache:
    """Bounded, TTL-aware cache of OCR results keyed by the image bytes.

    Re-running OCR (Tesseract subprocess / paid OCR.space calls) on an image we
    have already processed is pure waste — identical bytes are deterministic, so
    the result is identical. Caching completed results by content hash lets
    repeated uploads / retries of the same screenshot skip the expensive path
    entirely and stay well under the OCR time budget.

    Only *successful* results are cached; failures are never cached, because a
    failure may be transient (network/quota) rather than image-determined.
    """

    def __init__(self, max_entries: int = 256, ttl_seconds: float = 3600.0) -> None:
        self.max_entries = max(1, int(max_entries))
        self.ttl_seconds = float(ttl_seconds)
        self._store: "OrderedDict[str, tuple[float, dict[str, Any]]]" = OrderedDict()

    def get(self, image_bytes: bytes) -> dict[str, Any] | None:
        key = _hash_bytes(image_bytes)
        item = self._store.get(key)
        if item is None:
            return None
        stamp, payload = item
        if self.ttl_seconds > 0 and (time.monotonic() - stamp) > self.ttl_seconds:
            self._store.pop(key, None)
            return None
        self._store.move_to_end(key)
        return payload

    def put(self, image_bytes: bytes, payload: dict[str, Any]) -> None:
        key = _hash_bytes(image_bytes)
        self._store[key] = (time.monotonic(), payload)
        self._store.move_to_end(key)
        while len(self._store) > self.max_entries:
            self._store.popitem(last=False)

    def clear(self) -> None:
        self._store.clear()
