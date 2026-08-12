"""Per-key LLM token budgeting to stop a single client exhausting the provider quota.

The backend has no tenant model (§2.2 — unauthenticated API), so "per tenant"
here means "per request origin". The server passes the client IP (or operator id
when known) as the budget key, giving each origin its own daily token allowance.

Disabled by default (`daily_tokens == 0`) so existing deployments keep working;
enable with ``EXAMSHIELD_LLM_DAILY_TOKEN_BUDGET``.
"""

from __future__ import annotations

import threading
import time

from .settings import Settings


class BudgetExceeded(RuntimeError):
    """Raised when a key has exhausted its daily token allowance."""


def estimate_tokens(text_or_chars: int | str) -> int:
    """Rough token estimate (~4 chars/token) — deliberately conservative."""
    if isinstance(text_or_chars, str):
        return max(1, len(text_or_chars) // 4)
    return max(1, int(text_or_chars) // 4)


class TokenBudget:
    """Thread-safe per-key daily token budget with a sliding window reset."""

    def __init__(self, daily_tokens: int = 0, window_seconds: int = 86_400) -> None:
        self.daily_tokens = int(daily_tokens)
        self.window_seconds = int(window_seconds)
        self._lock = threading.Lock()
        self._used: dict[str, int] = {}
        self._window_start: float = time.monotonic()

    @property
    def enabled(self) -> bool:
        return self.daily_tokens > 0

    def spend(self, key: str, tokens: int) -> tuple[bool, dict[str, int]]:
        """Attempt to reserve ``tokens`` for ``key``.

        Returns ``(allowed, info)`` where ``info`` carries ``remaining``
        (``-1`` when the budget is disabled). Always allows when disabled.
        """
        if not self.enabled:
            return True, {"remaining": -1}
        key = key or "global"
        tokens = max(0, int(tokens))
        with self._lock:
            self._maybe_reset_locked()
            used = self._used.get(key, 0)
            remaining = self.daily_tokens - used
            if tokens > remaining:
                return False, {"remaining": remaining}
            self._used[key] = used + tokens
            return True, {"remaining": self.daily_tokens - self._used[key]}

    def reset(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._used.clear()
            else:
                self._used.pop(key, None)

    def _maybe_reset_locked(self) -> None:
        if time.monotonic() - self._window_start >= self.window_seconds:
            self._used.clear()
            self._window_start = time.monotonic()


def make_token_budget(settings: Settings) -> TokenBudget:
    daily = int(getattr(settings, "llm_daily_token_budget", 0) or 0)
    window = int(getattr(settings, "llm_budget_window_seconds", 86_400) or 86_400)
    return TokenBudget(daily_tokens=daily, window_seconds=window)
