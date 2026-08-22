from __future__ import annotations

from types import SimpleNamespace

from examshield_ai.budget import TokenBudget
from examshield_ai.chat import ChatSession


class FakeRegistry:
    def schemas(self):
        return [{"type": "function", "function": {"name": "listEvidence", "parameters": {"type": "object"}}}]

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
    """Emits one tool call, then answers with canned tokens."""

    def __init__(self, *, configured: bool = True, final_answer: str = "ok") -> None:
        self.configured = configured
        self.final_answer = final_answer
        self.calls = 0
        self.messages_seen: list[list[dict]] = []
        self.settings = SimpleNamespace(model="test-model", chat_max_tokens=64)

    def stream_chat(self, **kwargs):
        self.calls += 1
        self.messages_seen.append(list(kwargs["messages"]))
        if self.calls == 1 and kwargs.get("tools"):
            kwargs["on_tool_call"](0, "call_0", "listEvidence")
            kwargs["on_tool_delta"](0, "{}")
            return True
        kwargs["on_token"](self.final_answer)
        return True


def make_session(client, **session_kwargs):
    events = []
    session = ChatSession(client=client, registry=FakeRegistry(), write=events.append, **session_kwargs)
    return session, events


def test_budget_denial_degrades_to_local_fallback_without_llm_call():
    client = FakeClient(final_answer="should not run")
    budget = TokenBudget(per_request_limit=10, per_session_limit=10)
    budget.record("s-1", 10)
    session, events = make_session(client, budget=budget, session_id="s-1")

    session.run("show evidence uploaded today", [], None)

    assert client.calls == 0
    assert any(event.get("provider") == "local-fallback" for event in events)
    assert any(event["type"] == "token" and "budget" in event["token"].lower() for event in events)
    assert events[-1]["type"] == "done"


def test_under_budget_session_streams_and_records_usage():
    client = FakeClient()
    budget = TokenBudget(per_request_limit=1_000, per_session_limit=5_000)
    session, events = make_session(client, budget=budget, session_id="s-2")

    session.run("hello there", [], None)

    usage = budget.usage("s-2")
    assert usage["requests"] == 1
    assert usage["usedTokens"] > 0
    assert any(event["type"] == "token" for event in events)
    assert not any(event["type"] == "grounding" for event in events)


def test_grounded_answer_after_tool_call_emits_grounding_event():
    # Answer repeats only what the tool returned — fully grounded.
    client = FakeClient(final_answer="No evidence was uploaded today.")
    session, events = make_session(client)

    session.run("show evidence uploaded today", [], None)

    grounding = next(event for event in events if event["type"] == "grounding")
    assert grounding["verdict"] == "grounded"
    assert grounding["groundedRatio"] == 1.0


def test_fabricated_figures_are_flagged_against_tool_context():
    client = FakeClient(final_answer="Exactly 42 alerts were open across 7 centers.")
    session, events = make_session(client)

    session.run("list threats", [], None)

    grounding = next(event for event in events if event["type"] == "grounding")
    assert grounding["verdict"] in {"partial", "ungrounded"}
    missing = grounding["checks"][0]["missingEvidence"]
    assert "42" in missing
    assert "7" in missing


def test_grounding_system_message_injected_for_post_tool_answer():
    client = FakeClient()
    session, _events = make_session(client)

    session.run("show evidence uploaded today", [], None)

    assert client.calls == 2
    follow_up_messages = client.messages_seen[1]
    system_contents = [m["content"] for m in follow_up_messages if m["role"] == "system"]
    assert any("Use ONLY that data" in content for content in system_contents)


def test_plain_conversation_skips_grounding_checks():
    client = FakeClient(final_answer="Hello! Great to see you.")
    session, events = make_session(client)

    session.run("hello!", [], None)

    assert client.calls == 1
    assert not any(event["type"] == "grounding" for event in events)
