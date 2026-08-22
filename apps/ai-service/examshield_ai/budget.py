"""Token-budget guardrails for EXAMSHIELD AI.

Every LLM call costs tokens. Without a ceiling, one chatty session (or one
runaway tool loop) can burn the whole provider quota and take the chat route
down for everyone else. This module keeps that bounded:

* ``per_request_limit``  — max tokens a single request may spend.
* ``per_session_limit``  — max tokens a conversation session may spend overall.

A tiny in-memory ledger tracks usage per session. Callers ask
``evaluate()`` *before* an LLM call and report back with ``record()``
afterwards. The default posture is graceful degradation: callers get a
``BudgetDecision`` they can act on (shrink context, skip the LLM, fall back to
local answers) instead of an exception. ``require()`` is available for callers
that prefer fail-fast semantics.

The ledger is deliberately simple — process-local, no persistence. Restarting
the service resets budgets, which is acceptable for guardrails whose job is to
stop runaway spending within a single deployment's lifetime.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

DEFAULT_PER_REQUEST_LIMIT = 4_000
DEFAULT_PER_SESSION_LIMIT = 50_000


class BudgetExceededError(RuntimeError):
    """Raised by ``require()`` when a call would exceed its token budget."""


@dataclass(frozen=True)
class BudgetDecision:
    """Outcome of a budget check — truthy when the call may proceed."""

    allowed: bool
    reason: str = ""
    remaining_session_tokens: int = 0

    def __bool__(self) -> bool:
        return self.allowed


@dataclass
class LedgerEntry:
    used_tokens: int = 0
    requests: int = 0
    updated_at: str = field(default="")


def estimate_tokens(text: str) -> int:
    """Rough token estimate for a piece of text (~4 chars per token)."""
    if not text:
        return 0
    return max(1, len(text) // 4)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class TokenBudget:
    """Per-request / per-session token budgets backed by a small ledger."""

    def __init__(
        self,
        *,
        per_request_limit: int = DEFAULT_PER_REQUEST_LIMIT,
        per_session_limit: int = DEFAULT_PER_SESSION_LIMIT,
    ) -> None:
        if per_request_limit <= 0 or per_session_limit <= 0:
            raise ValueError("token budget limits must be positive")
        if per_request_limit > per_session_limit:
            raise ValueError("per_request_limit cannot exceed per_session_limit")
        self.per_request_limit = per_request_limit
        self.per_session_limit = per_session_limit
        self._ledger: dict[str, LedgerEntry] = {}

    def evaluate(self, session_id: str | None, requested_tokens: int) -> BudgetDecision:
        """Check whether spending ``requested_tokens`` is allowed right now."""
        entry = self._entry(session_id)

        if requested_tokens > self.per_request_limit:
            return BudgetDecision(
                allowed=False,
                reason=(
                    f"Request needs ~{requested_tokens} tokens but the "
                    f"per-request budget is {self.per_request_limit}."
                ),
                remaining_session_tokens=self._remaining(entry),
            )

        remaining = self._remaining(entry)
        if requested_tokens > remaining:
            return BudgetDecision(
                allowed=False,
                reason=(
                    f"Session budget nearly spent: ~{requested_tokens} tokens "
                    f"requested, {remaining} remaining of {self.per_session_limit}."
                ),
                remaining_session_tokens=remaining,
            )

        return BudgetDecision(allowed=True, remaining_session_tokens=remaining - requested_tokens)

    def require(self, session_id: str | None, requested_tokens: int) -> BudgetDecision:
        """Fail-fast variant of ``evaluate()`` for callers without a fallback."""
        decision = self.evaluate(session_id, requested_tokens)
        if not decision.allowed:
            raise BudgetExceededError(decision.reason)
        return decision

    def record(self, session_id: str | None, tokens_used: int) -> BudgetDecision:
        """Add actual usage to the ledger after a call completes."""
        entry = self._entry(session_id)
        entry.used_tokens += max(0, int(tokens_used))
        entry.requests += 1
        entry.updated_at = _utc_now_iso()
        return BudgetDecision(
            allowed=self._remaining(entry) > 0,
            remaining_session_tokens=self._remaining(entry),
        )

    def usage(self, session_id: str | None) -> dict[str, int]:
        """Current usage snapshot for a session."""
        entry = self._entry(session_id)
        return {
            "usedTokens": entry.used_tokens,
            "requests": entry.requests,
            "remainingTokens": self._remaining(entry),
            "perRequestLimit": self.per_request_limit,
            "perSessionLimit": self.per_session_limit,
        }

    def reset(self, session_id: str | None = None) -> None:
        """Clear one session's ledger entry, or everything when unspecified."""
        if session_id is None:
            self._ledger.clear()
        else:
            self._ledger.pop(session_id, None)

    def _remaining(self, entry: LedgerEntry) -> int:
        return max(0, self.per_session_limit - entry.used_tokens)

    def _entry(self, session_id: str | None) -> LedgerEntry:
        key = session_id or "anonymous"
        return self._ledger.setdefault(key, LedgerEntry())
