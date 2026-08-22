from __future__ import annotations

from types import SimpleNamespace

from examshield_ai.chat import ChatSession


class FakeRegistry:
    def schemas(self):
        return [{"type": "function", "function": {"name": "listEvidence"}}]

    def execute(self, name, arguments):
        return SimpleNamespace(
            result={"tool": name, "summary": "No evidence was uploaded today.", "metrics": []},
            model_context="{}",
        )


class FakeClient:
    def __init__(self, *, configured: bool, fail_stream: bool = False) -> None:
        self.configured = configured
        self.fail_stream = fail_stream
        self.settings = SimpleNamespace(
            planner_timeout_seconds=0.1,
            model="test-model",
            chat_max_tokens=64,
        )

    def stream_chat(self, **kwargs):
        if self.fail_stream:
            raise RuntimeError("provider timed out")
        kwargs["on_token"]("ok")
        return True


class ToolEmittingClient:
    """Emits a `listEvidence` tool call on the first stream, then answers.

    This exercises the deterministic routing path: a live-data command attaches
    tool schemas and the model selects the tool inline (the behaviour that
    replaced the old separate `ToolPlanner.plan` round-trip).
    """

    def __init__(self, *, configured: bool = True) -> None:
        self.configured = configured
        self.settings = SimpleNamespace(model="test-model", chat_max_tokens=64)
        self.calls = 0

    def stream_chat(self, **kwargs):
        self.calls += 1
        if self.calls == 1 and kwargs.get("tools"):
            kwargs["on_tool_call"](0, "call_1", "listEvidence")
            kwargs["on_tool_delta"](0, '{"filter": "recent"}')
            return True
        kwargs["on_token"]("answer")
        return True


def test_chat_without_provider_returns_visible_local_fallback():
    events = []
    session = ChatSession(client=FakeClient(configured=False), registry=FakeRegistry(), write=events.append)

    session.run("hello", [], None)

    assert any(event.get("provider") == "local-fallback" for event in events)
    error_event = next(event for event in events if event["type"] == "error")
    assert "No language model is configured" in error_event["message"]
    assert events[-1]["type"] == "done"


def test_failed_stream_returns_visible_local_fallback():
    events = []
    session = ChatSession(client=FakeClient(configured=True, fail_stream=True), registry=FakeRegistry(), write=events.append)

    session.run("hello", [], None)

    assert any(event.get("provider") == "local-fallback" for event in events)
    error_event = next(event for event in events if event["type"] == "error")
    assert "did not respond" in error_event["message"]
    assert events[-1]["type"] == "done"


def test_live_data_commands_use_deterministic_tool_routing():
    events = []
    session = ChatSession(client=ToolEmittingClient(), registry=FakeRegistry(), write=events.append)

    session.run("show evidence uploaded today", [], None)

    tool_event = next(event for event in events if event["type"] == "tool")
    assert tool_event["tool"] == "listEvidence"
    assert "No evidence" in tool_event["result"].get("summary", "")
    assert events[-1]["type"] == "done"
