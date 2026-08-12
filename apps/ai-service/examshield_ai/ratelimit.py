"""Thread-safe sliding-window rate limiter for sensitive endpoints.

Audit §4.2 / S9+S13: ``/ocr/analyze`` and ``/evidence/upload`` trigger paid
external calls with no abuse protection.  This module provides a lightweight,
in-memory, per-key rate limiter backed by ``collections.deque`` and
``threading.Lock``.

Configuration (all default to 0 = disabled for backward compatibility):

    EXAMSHIELD_RATE_LIMIT_OCR_REQUESTS    – max requests per window (0=off)
    EXAMSHIELD_RATE_LIMIT_OCR_WINDOW      – window in seconds (default 60)
    EXAMSHIELD_RATE_LIMIT_OCR_DAILY       – daily cap per key (0=off)
    EXAMSHIELD_RATE_LIMIT_UPLOAD_REQUESTS – max requests per window (0=off)
    EXAMSHIELD_RATE_LIMIT_UPLOAD_WINDOW   – window in seconds (default 60)
    EXAMSHIELD_RATE_LIMIT_UPLOAD_DAILY    – daily cap per key (0=off)
"""
from __future__ import annotations

import os
import threading
import time
from collections import deque
from typing import Any


class RateLimiter:
    """Sliding-window rate limiter keyed by an arbitrary string (e.g. client IP).

    Parameters
    ----------
    max_requests:
        Maximum requests allowed within ``window_seconds``.  **0 disables**
        the limiter (all requests are allowed).
    window_seconds:
        Length of the sliding window in seconds.
    max_daily:
        Hard cap on requests per key per UTC day.  **0 disables** the daily
        cap.
    """

    def __init__(
        self,
        max_requests: int = 0,
        window_seconds: float = 60.0,
        max_daily: int = 0,
    ) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.max_daily = max_daily
        # Per-key deque of timestamps (float, from time.monotonic).
        self._windows: dict[str, deque[float]] = {}
        # Per-key daily counter {key: (utc_day, count)}.
        self._daily: dict[str, tuple[str, int]] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def allow(self, key: str) -> tuple[bool, dict[str, Any]]:
        """Check whether *key* is allowed under the current window.

        Returns
        -------
        ``(allowed, info)`` where *info* contains:
            ``remaining`` – requests left in the current window.
            ``retry_after`` – seconds until the oldest request expires (0 if allowed).
            ``daily_remaining`` – daily cap remaining (``-1`` if disabled).
        """
        if self.max_requests <= 0:
            return True, {"remaining": -1, "retry_after": 0, "daily_remaining": -1}

        now = time.monotonic()
        utc_day = self._utc_day()

        with self._lock:
            # --- Sliding window ---
            dq = self._windows.setdefault(key, deque())
            cutoff = now - self.window_seconds
            # Evict expired entries.
            while dq and dq[0] <= cutoff:
                dq.popleft()

            if len(dq) >= self.max_requests:
                retry_after = dq[0] + self.window_seconds - now
                return False, {
                    "remaining": 0,
                    "retry_after": max(retry_after, 0),
                    "daily_remaining": self._daily_remaining(key, utc_day),
                }

            # --- Daily cap ---
            if self.max_daily > 0:
                day, count = self._daily.get(key, ("", 0))
                if day != utc_day:
                    self._daily[key] = (utc_day, 1)
                elif count >= self.max_daily:
                    return False, {
                        "remaining": self.max_requests - len(dq) - 1,
                        "retry_after": 0,
                        "daily_remaining": 0,
                    }
                else:
                    self._daily[key] = (utc_day, count + 1)

            # --- Allow and record ---
            dq.append(now)
            return True, {
                "remaining": self.max_requests - len(dq),
                "retry_after": 0,
                "daily_remaining": self._daily_remaining(key, utc_day),
            }

    def reset(self, key: str) -> None:
        """Clear all state for *key* (useful in tests and admin resets)."""
        with self._lock:
            self._windows.pop(key, None)
            self._daily.pop(key, None)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _daily_remaining(self, key: str, utc_day: str) -> int:
        if self.max_daily <= 0:
            return -1
        day, count = self._daily.get(key, ("", 0))
        if day != utc_day:
            return self.max_daily
        return max(self.max_daily - count, 0)

    @staticmethod
    def _utc_day() -> str:
        """Return today's UTC date as ``YYYY-MM-DD``."""
        return time.strftime("%Y-%m-%d", time.gmtime())


# ---------------------------------------------------------------------------
# Factory helpers – create limiters from env vars
# ---------------------------------------------------------------------------

def make_ocr_limiter() -> RateLimiter:
    return RateLimiter(
        max_requests=int(os.environ.get("EXAMSHIELD_RATE_LIMIT_OCR_REQUESTS", "0")),
        window_seconds=float(os.environ.get("EXAMSHIELD_RATE_LIMIT_OCR_WINDOW", "60")),
        max_daily=int(os.environ.get("EXAMSHIELD_RATE_LIMIT_OCR_DAILY", "0")),
    )


def make_upload_limiter() -> RateLimiter:
    return RateLimiter(
        max_requests=int(os.environ.get("EXAMSHIELD_RATE_LIMIT_UPLOAD_REQUESTS", "0")),
        window_seconds=float(os.environ.get("EXAMSHIELD_RATE_LIMIT_UPLOAD_WINDOW", "60")),
        max_daily=int(os.environ.get("EXAMSHIELD_RATE_LIMIT_UPLOAD_DAILY", "0")),
    )
