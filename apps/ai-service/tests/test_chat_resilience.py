from __future__ import annotations

from types import SimpleNamespace

from examshield_ai.chat import ChatSession


class FakeRegistry:
    def schemas(self):
        return []

    def execute(self, name, arguments):
        return SimpleNamespace(
            result={
                "tool": name,
                "summary": "No evidence was uploaded today.",
                "metrics": [{"label": "Total Evidence", "value": 0}],
            },
            model_context="{}",
        )


class FakeClient:
    def __init__(self, *, configured: bool, fail_stream: bool = False, tool_call: bool = False) -> None:
        self.configured = configured
        self.fail_stream = fail_stream
        self.tool_call = tool_call
        self.calls = 0
        self.settings = SimpleNamespace(
            planner_timeout_seconds=0.1,
            model="test-model",
            chat_max_tokens=64,
        )

    def stream_chat(self, **kwargs):
        self.calls += 1
        if self.fail_stream:
            raise RuntimeError("provider timed out")
        if self.tool_call and self.calls == 1:
            kwargs["on_tool_call"](0, "call_0", "listEvidence")
            kwargs["on_tool_delta"](0, "{}")
            return True
        kwargs["on_token"]("ok")
        return True


def test_chat_without_provider_returns_visible_local_fallback():
    events = []
    session = ChatSession(client=FakeClient(configured=False), registry=FakeRegistry(), write=events.append)

    session.run("hello", [], None)

    assert any(event.get("provider") == "local-fallback" for event in events)
    assert any("online" in event.get("token", "") for event in events)
    assert events[-1]["type"] == "done"


def test_failed_stream_returns_visible_local_fallback():
    events = []
    session = ChatSession(client=FakeClient(configured=True, fail_stream=True), registry=FakeRegistry(), write=events.append)

    session.run("hello", [], None)

    assert any(event.get("provider") == "local-fallback" for event in events)
    assert any("did not respond" in event.get("token", "") for event in events)
    assert events[-1]["type"] == "done"


def test_live_data_commands_use_deterministic_tool_routing():
    events = []
    session = ChatSession(
        client=FakeClient(configured=True, tool_call=True),
        registry=FakeRegistry(),
        write=events.append,
    )

    session.run("show evidence uploaded today", [], None)

    tool_event = next(event for event in events if event["type"] == "tool")
    assert tool_event["tool"] == "listEvidence"
    assert "No evidence" in str(tool_event["result"].get("summary"))
    assert events[-1]["type"] == "done"
