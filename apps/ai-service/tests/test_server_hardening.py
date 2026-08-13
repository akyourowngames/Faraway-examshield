from __future__ import annotations

from dataclasses import replace

from examshield_ai.server import build_handler


def _handler_class(settings):
    """Build the configured handler class exactly as the app does."""
    cls = build_handler(settings)
    # build_handler spins up a real worker pool; tear it down so the test
    # process does not leak threads.
    if getattr(cls, "workers", None) is not None:
        cls.workers.shutdown(wait=False)
    return cls


def test_server_body_cap_detects_oversized_request(tmp_settings) -> None:
    settings = replace(tmp_settings, max_request_body_bytes=100)
    cls = _handler_class(settings)
    handler = cls.__new__(cls)
    handler.settings = settings

    handler.headers = {"Content-Length": "200"}
    assert handler._body_exceeds_server_cap() is True

    handler.headers = {"Content-Length": "50"}
    assert handler._body_exceeds_server_cap() is False

    # Missing Content-Length is treated as zero -> never oversized.
    handler.headers = {}
    assert handler._body_exceeds_server_cap() is False


def test_server_body_cap_disabled_when_zero(tmp_settings) -> None:
    settings = replace(tmp_settings, max_request_body_bytes=0)
    cls = _handler_class(settings)
    handler = cls.__new__(cls)
    handler.settings = settings
    handler.headers = {"Content-Length": "999999999"}
    assert handler._body_exceeds_server_cap() is False


def test_handler_applies_slow_client_timeout(tmp_settings) -> None:
    settings = replace(tmp_settings, request_timeout_seconds=7.0)
    cls = _handler_class(settings)
    assert cls.timeout == 7.0


def test_handler_protocol_version_follows_keep_alive_setting(tmp_settings) -> None:
    settings = replace(tmp_settings, keep_alive_enabled=True)
    cls = _handler_class(settings)
    assert cls.protocol_version == "HTTP/1.1"

    settings_off = replace(tmp_settings, keep_alive_enabled=False)
    cls_off = _handler_class(settings_off)
    assert cls_off.protocol_version == "HTTP/1.0"
