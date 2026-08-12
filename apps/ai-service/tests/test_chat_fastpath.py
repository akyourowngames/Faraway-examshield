from __future__ import annotations

from types import SimpleNamespace

from examshield_ai.chat import ChatSession


class FakeRegistry:
    def schemas(self):
        return [{"type": "function", "function": {"name": "listEvidence"}}]

    def execute(self, name, arguments):
        return SimpleNamespace(
            result={"tool": name, "summary": "No evidence today.", "metrics": []},
            model_context="{}",
        )


class CapturingClient:
    def __init__(self, configured: bool = True) -> None:
        self.configured = configured
        self.settings = SimpleNamespace(model="test-model", chat_max_tokens=64)
        self.last_call = None

    def stream_chat(self, **kwargs):
        self.last_call = kwargs
        kwargs["on_token"]("ok")
        return True


def test_greeting_skips_tool_schemas():
    """§5/§11.2: simple greetings must not pay for tool routing. The answer
    stream should be invoked with no tool schemas attached."""
    events: list[dict] = []
    client = CapturingClient()
    session = ChatSession(client=client, registry=FakeRegistry(), write=events.append)

    session.run("hi!", [], None)

    assert client.last_call is not None
    assert not client.last_call.get("tools"), "greeting should skip tool schemas"
    assert events[-1]["type"] == "done"


def test_live_data_request_attaches_tool_schemas():
    events: list[dict] = []
    client = CapturingClient()
    session = ChatSession(client=client, registry=FakeRegistry(), write=events.append)

    session.run("show me recent evidence", [], None)

    assert client.last_call is not None
    assert client.last_call.get("tools"), "live-data request should attach tool schemas"
