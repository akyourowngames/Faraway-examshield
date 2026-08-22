from __future__ import annotations

from pathlib import Path

from examshield_ai.settings import _split_csv, load_settings


def _clear_env(monkeypatch, names):
    for name in names:
        monkeypatch.delenv(name, raising=False)


def test_load_settings_applies_defaults(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    _clear_env(
        monkeypatch,
        [
            "EXAMSHIELD_REPO_ROOT",
            "EXAMSHIELD_UPLOAD_ROOT",
            "EXAMSHIELD_REGISTRY_PATH",
            "PORT",
            "EXAMSHIELD_AI_PORT",
            "KILO_API_KEY",
            "NVIDIA_API_KEY",
        ],
    )

    settings = load_settings()

    assert settings.port == 8790
    assert settings.model == "tencent/hy3:free"
    assert settings.chat_max_tokens == 350
    # Guardrail constants stay sane across edits.
    assert settings.llm_retry_attempts >= 1
    assert 0 < settings.llm_retry_backoff_seconds <= 5
    assert 0 < settings.budget_per_request_tokens <= settings.budget_per_session_tokens


def test_load_settings_reads_env_overrides(monkeypatch, tmp_path: Path):
    _clear_env(monkeypatch, ["EXAMSHIELD_AI_MODEL", "KILO_MODEL", "EXAMSHIELD_CHAT_MODEL"])
    monkeypatch.setenv("EXAMSHIELD_AI_MODEL", "custom/model")
    monkeypatch.setenv("KILO_API_KEY", "key-123")
    monkeypatch.setenv("EXAMSHIELD_AI_BUDGET_PER_REQUEST_TOKENS", "250")
    monkeypatch.setenv("EXAMSHIELD_AI_LLM_RETRY_ATTEMPTS", "4")

    settings = load_settings()

    assert settings.model == "custom/model"
    assert settings.api_key == "key-123"
    assert settings.budget_per_request_tokens == 250
    assert settings.llm_retry_attempts == 4


def test_split_csv_trims_and_drops_empty_entries():
    assert _split_csv(" a , b,,c ") == ("a", "b", "c")
    assert _split_csv("") == ()
