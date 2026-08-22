from __future__ import annotations

import pytest
from examshield_ai.budget import (
    BudgetDecision,
    BudgetExceededError,
    TokenBudget,
    estimate_tokens,
)


def test_estimate_tokens_scales_with_text_length():
    assert estimate_tokens("") == 0
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("a" * 400) == 100


def test_under_budget_request_is_allowed():
    budget = TokenBudget(per_request_limit=100, per_session_limit=500)

    decision = budget.evaluate("session-1", 80)

    assert decision.allowed
    assert decision.remaining_session_tokens == 420
    assert bool(decision) is True


def test_request_over_per_request_limit_is_denied():
    budget = TokenBudget(per_request_limit=100, per_session_limit=10_000)

    decision = budget.evaluate("session-1", 150)

    assert not decision.allowed
    assert "per-request budget" in decision.reason


def test_session_usage_accumulates_and_eventually_blocks():
    budget = TokenBudget(per_request_limit=600, per_session_limit=1_000)

    assert budget.record("s", 700).allowed
    denied = budget.evaluate("s", 400)
    assert not denied.allowed
    assert "remaining" in denied.reason
    assert denied.remaining_session_tokens == 300


def test_record_returns_degraded_decision_when_budget_spent():
    budget = TokenBudget(per_request_limit=500, per_session_limit=800)

    final = budget.record("s", 900)

    assert isinstance(final, BudgetDecision)
    assert not final.allowed
    assert final.reason == ""
    assert budget.usage("s")["usedTokens"] == 900


def test_require_raises_budget_exceeded_error():
    budget = TokenBudget(per_request_limit=100, per_session_limit=200)

    with pytest.raises(BudgetExceededError):
        budget.require("s", 300)

    # Under-budget calls pass through and return a truthy decision.
    assert budget.require("s", 50).allowed


def test_sessions_are_ledgered_independently():
    budget = TokenBudget(per_request_limit=500, per_session_limit=500)

    budget.record("a", 500)
    other = budget.evaluate("b", 100)

    assert other.allowed
    assert budget.usage("a")["remainingTokens"] == 0
    assert budget.usage("b")["usedTokens"] == 0


def test_none_session_falls_back_to_anonymous_scope():
    budget = TokenBudget(per_request_limit=100, per_session_limit=100)

    budget.record(None, 60)
    budget.record(None, 20)

    usage = budget.usage(None)
    assert usage["requests"] == 2
    assert usage["usedTokens"] == 80


def test_reset_clears_one_session_or_all():
    budget = TokenBudget(per_request_limit=100, per_session_limit=100)
    budget.record("a", 50)
    budget.record("b", 50)

    budget.reset("a")
    assert budget.usage("a")["usedTokens"] == 0
    assert budget.usage("b")["usedTokens"] == 50

    budget.reset()
    assert budget.usage("b")["usedTokens"] == 0


def test_invalid_limits_are_rejected():
    with pytest.raises(ValueError):
        TokenBudget(per_request_limit=0, per_session_limit=100)
    with pytest.raises(ValueError):
        TokenBudget(per_request_limit=200, per_session_limit=100)


def test_usage_snapshot_reports_limits():
    budget = TokenBudget(per_request_limit=250, per_session_limit=2_000)

    usage = budget.usage("s")

    assert usage == {
        "usedTokens": 0,
        "requests": 0,
        "remainingTokens": 2_000,
        "perRequestLimit": 250,
        "perSessionLimit": 2_000,
    }
