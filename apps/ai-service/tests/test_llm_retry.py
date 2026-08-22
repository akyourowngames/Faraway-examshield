from __future__ import annotations

import urllib.error
from unittest.mock import patch

from examshield_ai.llm import KiloClient, _is_transient
from examshield_ai.settings import Settings


def make_settings(**overrides) -> Settings:
    values = dict(
        host="127.0.0.1",
        port=8790,
        repo_root=None,
        upload_root=None,
        registry_path=None,
        api_key="k",
        model="m1",
        fallback_models=("m2",),
        planner_model="m1",
        base_url="https://example.com/v1",
        planner_timeout_seconds=5.0,
        stream_timeout_seconds=20.0,
        chat_max_tokens=64,
        planner_max_tokens=64,
        list_cache_ttl_seconds=8.0,
        supabase_timeout_seconds=20.0,
        detect_threshold=7.0,
        cors_origin="*",
        max_upload_bytes=1024,
        supabase_url="",
        supabase_service_role_key="",
        supabase_document_table="t",
        supabase_storage_bucket="b",
        public_url="",
        telegram_bot_token="",
        telegram_webhook_secret="",
        telegram_chat_id="",
        telegram_admin_chat_id="",
    )
    values.update(overrides)
    return Settings(**values)


def test_is_transient_classifies_timeouts_and_retryable_statuses():
    assert _is_transient(TimeoutError("boom"))
    assert _is_transient(urllib.error.URLError("conn refused"))
    assert _is_transient(RuntimeError("Kilo gateway returned 429: slow down"))
    assert _is_transient(RuntimeError("Kilo gateway returned 503: unavailable"))
    assert not _is_transient(RuntimeError("Kilo gateway returned 401: bad key"))
    assert not _is_transient(ValueError("bad payload"))


def test_json_request_retries_then_succeeds():
    client = KiloClient(make_settings(llm_retry_attempts=2, llm_retry_backoff_seconds=0))
    attempts = {"count": 0}

    def flaky(payload, timeout):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("Kilo gateway returned 429: slow down")
        return {"ok": True}

    with patch.object(client, "_request_json", side_effect=flaky):
        result = client.chat_json(model="m1", messages=[{"role": "user", "content": "hi"}])

    assert result == {"ok": True}
    assert attempts["count"] == 2


def test_non_retryable_error_falls_through_to_next_model_immediately():
    client = KiloClient(make_settings(llm_retry_attempts=3, llm_retry_backoff_seconds=0))
    calls: list[str] = []

    def failing(payload, timeout):
        calls.append(payload["model"])
        raise RuntimeError(f"Kilo gateway returned 401 for {payload['model']}")

    with (
        patch.object(client, "_request_json", side_effect=failing),
        patch("examshield_ai.llm.time.sleep") as sleep_mock,
    ):
        try:
            client.chat_json(model="m1", messages=[])
        except RuntimeError as exc:
            assert "failed for all configured models" in str(exc)
        else:
            raise AssertionError("expected failure")

    # Both models tried exactly once each; no backoff sleeps for a 401.
    assert calls == ["m1", "m2"]
    assert sleep_mock.call_count == 0


def test_retries_exhausted_raises_after_backoff_sleeps():
    client = KiloClient(make_settings(llm_retry_attempts=2, llm_retry_backoff_seconds=0.25))

    def always_timeout(payload, timeout):
        raise TimeoutError("timed out")

    sleeps: list[float] = []
    with (
        patch.object(client, "_request_json", side_effect=always_timeout),
        patch("examshield_ai.llm.time.sleep", side_effect=sleeps.append),
    ):
        try:
            client.chat_json(model="m1", messages=[])
        except RuntimeError as exc:
            assert "failed for all configured models" in str(exc)
        else:
            raise AssertionError("expected failure")

    # Candidates m1 then m2; each gets initial attempt + 2 retries with
    # exponential backoff 0.25 then 0.5.
    assert sleeps == [0.25, 0.5, 0.25, 0.5]
