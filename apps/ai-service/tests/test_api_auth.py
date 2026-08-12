from __future__ import annotations

import threading
import urllib.error
import urllib.request
from dataclasses import replace
from http.server import ThreadingHTTPServer

from examshield_ai.server import (
    _UNAUTHORIZED_BODY,
    API_AUTH_HEADER,
    build_handler,
    is_authorized,
    is_path_exempt,
)
from examshield_ai.settings import Settings


def _headers(secret: str | None = None) -> dict[str, str]:
    if secret is None:
        return {}
    return {API_AUTH_HEADER: secret}


def test_exempt_paths_open_regardless_of_secret():
    for path in ["/health", "/", "/telegram/webhook", "/telegram/events"]:
        assert is_path_exempt(path) is True
        # Exempt even when a secret is configured.
        assert is_authorized(_headers("x"), "topsecret", path) is True
        # And when no secret is configured.
        assert is_authorized({}, "", path) is True


def test_disabled_when_secret_empty():
    # With no secret set, every route is authorized (offline/dev parity).
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


def _start_server(settings: Settings):
    handler_cls = build_handler(settings)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, handler_cls, server.server_address[1]


def test_live_server_enforces_auth(tmp_settings: Settings) -> None:
    settings = replace(tmp_settings, api_auth_secret="test-secret")
    server, handler_cls, port = _start_server(settings)
    base = f"http://127.0.0.1:{port}"
    try:
        handler_cls.store.ensure_storage()

        # /health is exempt -> 200 even without the key.
        with urllib.request.urlopen(f"{base}/health") as resp:
            assert resp.status == 200

        # A protected route without the key -> 401 with our exact body.
        try:
            urllib.request.urlopen(urllib.request.Request(f"{base}/evidence"))
            raise AssertionError("expected 401 without key")
        except urllib.error.HTTPError as exc:
            assert exc.code == 401
            assert exc.read() == _UNAUTHORIZED_BODY

        # The same route WITH the key is not rejected by the auth gate.
        with urllib.request.urlopen(
            urllib.request.Request(f"{base}/evidence", headers=_headers("test-secret"))
        ) as resp:
            assert resp.status != 401

        # Inbound Telegram paths are exempt from the backend secret, so they
        # must never return our auth 401 (their own validation still applies).
        req = urllib.request.Request(
            f"{base}/telegram/events",
            data=b"{}",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req) as resp:
                body = resp.read()
        except urllib.error.HTTPError as exc:
            body = exc.read()
        assert body != _UNAUTHORIZED_BODY
    finally:
        server.shutdown()
        server.server_close()
