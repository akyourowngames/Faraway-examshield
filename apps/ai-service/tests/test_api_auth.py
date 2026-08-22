from __future__ import annotations

from dataclasses import replace

from examshield_ai.auth import API_AUTH_HEADER, is_authorized, is_path_exempt
from examshield_ai.fastapi_app.app import create_app
from fastapi.testclient import TestClient


def _headers(secret: str | None = None) -> dict[str, str]:
    if secret is None:
        return {}
    return {API_AUTH_HEADER: secret}


def test_exempt_paths_open_regardless_of_secret():
    for path in ["/health", "/", "/telegram/webhook", "/telegram/events"]:
        assert is_path_exempt(path) is True
        assert is_authorized(_headers("x"), "topsecret", path) is True
        assert is_authorized({}, "", path) is True


def test_disabled_when_secret_empty():
    assert is_authorized({}, "", "/evidence") is True
    assert is_authorized(_headers("whatever"), "", "/agents") is True


def test_missing_header_rejected():
    assert is_authorized({}, "topsecret", "/evidence") is False


def test_wrong_header_rejected():
    assert is_authorized(_headers("wrong"), "topsecret", "/evidence") is False


def test_correct_header_authorized():
    assert is_authorized(_headers("topsecret"), "topsecret", "/evidence") is True


def test_bearer_header_accepted_and_rejected():
    assert is_authorized({"Authorization": "Bearer topsecret"}, "topsecret", "/evidence") is True
    assert is_authorized({"Authorization": "Bearer nope"}, "topsecret", "/evidence") is False


def test_protected_paths_rejected_without_key():
    assert is_authorized({}, "topsecret", "/agents") is False
    assert is_authorized({}, "topsecret", "/memory/search") is False
    assert is_authorized({}, "topsecret", "/chat") is False


def test_fastapi_live_auth_gate(tmp_settings):
    settings = replace(tmp_settings, api_auth_secret="test-secret")
    app = create_app(settings)
    client = TestClient(app)

    # /health is exempt -> 200 even without the key.
    assert client.get("/health").status_code == 200

    # A protected route without the key -> 401 with the exact body shape.
    unauthorized = client.get("/evidence")
    assert unauthorized.status_code == 401
    assert unauthorized.json() == {"error": "Unauthorized."}

    # The same route WITH the key is not rejected by the auth gate.
    authorized = client.get("/evidence", headers=_headers("test-secret"))
    assert authorized.status_code != 401

    # Inbound Telegram paths are exempt from the backend secret, so they must
    # not return the auth 401 body (their own validation still applies).
    inbound = client.post("/telegram/events", json={})
    assert inbound.json() != {"error": "Unauthorized."}
