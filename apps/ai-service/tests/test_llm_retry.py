"""Tests for retryable-error classification + fallback behaviour (audit §11.2)."""
from __future__ import annotations

import dataclasses

import pytest

from examshield_ai.llm import GatewayError, KiloClient, _is_retryable
from examshield_ai.settings import Settings


def test_4xx_not_retryable():
    assert _is_retryable(GatewayError(400, "bad request")) is False
    assert _is_retryable(GatewayError(401, "unauth")) is False
    assert _is_retryable(GatewayError(403, "forbidden")) is False
    assert _is_retryable(GatewayError(422, "unprocessable")) is False


def test_429_is_retryable():
    # Rate-limit may clear on another model/region, so 429 falls through.
    assert _is_retryable(GatewayError(429, "rate limited")) is True


def test_5xx_and_network_retryable():
    assert _is_retryable(GatewayError(500, "boom")) is True
    assert _is_retryable(GatewayError(503, "unavailable")) is True
    assert _is_retryable(ConnectionError("down")) is True
    assert _is_retryable(TimeoutError("slow")) is True


def _client_with_fallbacks(tmp_settings: Settings, fallbacks: tuple[str, ...]) -> KiloClient:
    settings = dataclasses.replace(
        tmp_settings,
        fallback_models=fallbacks,
        llm_daily_token_budget=0,  # budget disabled for these tests
    )
    return KiloClient(settings)


def test_4xx_not_retried_across_models(tmp_settings: Settings):
    client = _client_with_fallbacks(tmp_settings, ("fallback-model",))
    calls: list[str] = []

    def fake_request_json(payload, timeout):
        calls.append(payload["model"])
        raise GatewayError(400, "malformed request")

    client._request_json = fake_request_json  # type: ignore[assignment]
    with pytest.raises(GatewayError) as excinfo:
        client.chat_json(model="primary-model", messages=[{"role": "user", "content": "hi"}])
    assert excinfo.value.status_code == 400
    # Primary only — the 4xx was not retried against the fallback.
    assert calls == ["primary-model"]


def test_5xx_retried_across_models(tmp_settings: Settings):
    client = _client_with_fallbacks(tmp_settings, ("fallback-model",))
    calls: list[str] = []

    def fake_request_json(payload, timeout):
        calls.append(payload["model"])
        raise GatewayError(503, "unavailable")

    client._request_json = fake_request_json  # type: ignore[assignment]
    with pytest.raises(RuntimeError):
        client.chat_json(model="primary-model", messages=[{"role": "user", "content": "hi"}])
    # Both primary and fallback attempted.
    assert calls == ["primary-model", "fallback-model"]


def test_budget_exceeded_raises(tmp_settings: Settings):
    from examshield_ai.budget import BudgetExceeded

    client = _client_with_fallbacks(tmp_settings, ())
    client._budget = __import__("examshield_ai.budget", fromlist=["TokenBudget"]).TokenBudget(daily_tokens=10)
    with pytest.raises(BudgetExceeded):
        # chat_max_tokens in tmp_settings is 220 > 10 budget
        client.chat_json(model="m", messages=[{"role": "user", "content": "hi"}], max_tokens=220)
