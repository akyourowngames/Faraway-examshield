from __future__ import annotations

from types import SimpleNamespace

import pytest

from examshield_ai.fastapi_app.deps import body_size_guard
from examshield_ai.fastapi_app.responses import PayloadTooLarge


def _request(settings, content_length: str | None):
    app = SimpleNamespace(state=SimpleNamespace(settings=settings))
    headers = {} if content_length is None else {"Content-Length": content_length}
    return SimpleNamespace(app=app, headers=headers)


def test_body_size_guard_rejects_oversized_request():
    settings = SimpleNamespace(max_request_body_bytes=100)
    with pytest.raises(PayloadTooLarge):
        body_size_guard(_request(settings, "200"))


def test_body_size_guard_allows_under_cap():
    settings = SimpleNamespace(max_request_body_bytes=100)
    body_size_guard(_request(settings, "50"))


def test_body_size_guard_allows_missing_length():
    settings = SimpleNamespace(max_request_body_bytes=100)
    body_size_guard(_request(settings, None))


def test_body_size_guard_disabled_when_zero():
    settings = SimpleNamespace(max_request_body_bytes=0)
    body_size_guard(_request(settings, "999999999"))
