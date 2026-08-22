from __future__ import annotations

import logging

from examshield_ai.secrets_crypto import (
    decrypt_secret,
    encrypt_secret,
    generate_master_key,
)


def test_roundtrip_with_explicit_key():
    key = generate_master_key()
    secret = "sk-SUPER-SECRET-12345"
    token = encrypt_secret(secret, key)
    assert token != secret
    assert decrypt_secret(token, key) == secret


def test_roundtrip_with_passphrase_key():
    token = encrypt_secret("hello-world", "my-passphrase")
    assert token != "hello-world"
    assert decrypt_secret(token, "my-passphrase") == "hello-world"


def test_wrong_key_returns_token_unchanged():
    token = encrypt_secret("secret-value", "key-one")
    # Wrong key -> not our plaintext, returned as-is (no crash, no leak).
    assert decrypt_secret(token, "key-two") == token


def test_legacy_plaintext_passes_through():
    # Values written before encryption was introduced must still work.
    assert decrypt_secret("plain-not-a-token", "any-key") == "plain-not-a-token"


def test_empty_values():
    assert encrypt_secret("", "k") == ""
    assert decrypt_secret("", "k") == ""


def test_dev_fallback_key_logs_warning(caplog):
    with caplog.at_level(logging.WARNING, logger="examshield_ai.secrets_crypto"):
        token = encrypt_secret("dev-secret", None)
    assert token != "dev-secret"
    assert decrypt_secret(token, None) == "dev-secret"
    assert any("EXAMSHIELD_AI_MASTER_KEY" in rec.message for rec in caplog.records)


def test_store_encrypts_llm_key_at_rest_and_decrypts_on_read(tmp_settings, store):
    from examshield_ai.store import AgentStore

    agent_store = AgentStore(store)
    agent = agent_store.create_agent({"name": "Enc Test"})

    saved = agent_store.upsert_llm_config(
        agent["id"], {"provider": "openai", "model": "gpt-4o", "apiKey": "sk-AT-REST-SECRET"}
    )
    # The persisted record must not contain the plaintext key.
    raw = store._read_json_dir("agent-llm-configs")
    assert raw[0]["apiKeyEncrypted"] != "sk-AT-REST-SECRET"
    assert saved["apiKeyEncrypted"] != "sk-AT-REST-SECRET"

    # Internal reads (provider calls) get the decrypted plaintext.
    got = agent_store.get_llm_config(agent["id"])
    assert got["apiKeyEncrypted"] == "sk-AT-REST-SECRET"


def test_upsert_without_key_keeps_existing(tmp_settings, store):
    from examshield_ai.store import AgentStore

    agent_store = AgentStore(store)
    agent = agent_store.create_agent({"name": "Keep Test"})
    agent_store.upsert_llm_config(agent["id"], {"apiKey": "first-secret"})

    # Update model only — existing key (encrypted) must be preserved.
    agent_store.upsert_llm_config(agent["id"], {"model": "gpt-4o-mini"})
    got = agent_store.get_llm_config(agent["id"])
    assert got["apiKeyEncrypted"] == "first-secret"
