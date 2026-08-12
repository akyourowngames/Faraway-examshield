from __future__ import annotations

import dataclasses
import json
import urllib.request

import pytest
from examshield_ai.llm import KiloClient
from examshield_ai.settings import load_settings


class _FakeResponse:
    """Minimal stand-in for the SSE HTTP response."""

    def __init__(self, lines: list[str]) -> None:
        self._lines = [line.encode("utf-8") for line in lines]

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *exc: object) -> bool:
        return False

    def __iter__(self):
        return iter(self._lines)


def _sse(*objects: dict) -> list[str]:
    lines = [f"data: {json.dumps(obj)}" for obj in objects]
    lines.append("data: [DONE]")
    return lines


def _client() -> KiloClient:
    settings = dataclasses.replace(load_settings(), model="stepfun/step-3.7-flash:free", fallback_models=())
    return KiloClient(settings)


def test_reasoning_only_stream_still_surfaces_visible_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    """A stream that emits ONLY reasoning (no `content`) must not fail silently:
    the client buffers the reasoning and surfaces it as a last-resort answer so
    reasoning-only models still respond. Reasoning must never leak when real
    content exists — that is covered by ``test_reasoning_dropped_but_content_emitted``."""
    captured: list[str] = []
    client = _client()
    lines = _sse(
        {"choices": [{"delta": {"reasoning": "let me think about this step by step"}}]},
        {"choices": [{"delta": {"reasoning_content": "now I will reason further"}}]},
    )
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=0: _FakeResponse(lines))

    result = client.stream_chat(model="stepfun/step-3.7-flash:free", messages=[], on_token=captured.append)

    assert result is True
    assert captured, "reasoning-only stream should surface a visible answer"


def test_reasoning_dropped_but_content_emitted(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reasoning tokens before the answer must be ignored; only `content`
    reaches the user."""
    captured: list[str] = []
    client = _client()
    lines = _sse(
        {"choices": [{"delta": {"reasoning": "internal secret thought"}}]},
        {"choices": [{"delta": {"content": "Final answer"}}]},
    )
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=0: _FakeResponse(lines))

    result = client.stream_chat(
        model="stepfun/step-3.7-flash:free", messages=[], on_token=captured.append
    )

    assert result is True
    assert captured == ["Final answer"]
