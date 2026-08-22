"""Tests for per-key LLM token budgeting (audit §11.2 — quota exhaustion)."""
from __future__ import annotations

import dataclasses

from examshield_ai.budget import BudgetExceeded, TokenBudget, estimate_tokens, make_token_budget
from examshield_ai.settings import Settings


def test_estimate_tokens_chars():
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("a" * 40) == 10
    assert estimate_tokens("") == 1  # never zero


def test_estimate_tokens_int():
    assert estimate_tokens(400) == 100


def test_disabled_always_allows():
    tb = TokenBudget(daily_tokens=0)
    assert tb.enabled is False
    allowed, info = tb.spend("ip-1", 999_999)
    assert allowed is True
    assert info["remaining"] == -1


def test_within_budget():
    tb = TokenBudget(daily_tokens=100)
    allowed, info = tb.spend("ip-1", 60)
    assert allowed is True
    assert info["remaining"] == 40


def test_over_budget_blocked():
    tb = TokenBudget(daily_tokens=100)
    assert tb.spend("ip-1", 60)[0] is True
    allowed, info = tb.spend("ip-1", 60)
    assert allowed is False
    assert info["remaining"] == 40  # not negative


def test_keys_isolated(tmp_settings: Settings):
    tb = TokenBudget(daily_tokens=50)
    assert tb.spend("ip-1", 50)[0] is True
    # different key still has full budget
    allowed, info = tb.spend("ip-2", 50)
    assert allowed is True
    assert info["remaining"] == 0


def test_reset_clears():
    tb = TokenBudget(daily_tokens=10)
    tb.spend("ip-1", 10)
    assert tb.spend("ip-1", 1)[0] is False
    tb.reset("ip-1")
    assert tb.spend("ip-1", 10)[0] is True


def test_make_token_budget_from_settings(tmp_settings: Settings):
    enabled = dataclasses.replace(tmp_settings, llm_daily_token_budget=500)
    tb = make_token_budget(enabled)
    assert tb.enabled is True
    assert tb.daily_tokens == 500

    disabled = dataclasses.replace(tmp_settings, llm_daily_token_budget=0)
    assert make_token_budget(disabled).enabled is False


def test_budget_exceeded_is_runtime_error():
    assert issubclass(BudgetExceeded, RuntimeError)
