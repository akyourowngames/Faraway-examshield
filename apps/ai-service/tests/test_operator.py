from __future__ import annotations

import json
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

from examshield_ai.chat import ChatSession
from examshield_ai.operator import resolve_operator
from examshield_ai.responses import conversation_messages
from examshield_ai.tools import ExamshieldToolRegistry


class _CapturingClient:
    def __init__(self) -> None:
        self.configured = True
        self.settings = SimpleNamespace(model="test-model", chat_max_tokens=64)
        self.last_call: dict | None = None

    def stream_chat(self, **kwargs):
        self.last_call = kwargs
        kwargs["on_token"]("ok")
        return True


class _FakeResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *exc: object) -> bool:
        return False

    def read(self) -> bytes:
        return self._body


def _supabase_settings(settings, url="https://x.supabase.co", key="svc-key"):
    return replace(
        settings,
        supabase_url=url,
        supabase_service_role_key=key,
        supabase_timeout_seconds=5.0,
    )


def test_body_operator_preferred_and_no_jwt_call(tmp_settings):
    """Client-sent operator wins and must NOT trigger a Supabase call."""
    with patch("urllib.request.urlopen") as mock_urlopen:
        op = resolve_operator(
            {"operator": {"name": "Jane Doe", "email": "jane@x.io"}},
            "Bearer jwt-token",
            tmp_settings,
        )
    assert op == {"name": "Jane Doe", "email": "jane@x.io", "role": "Operator"}
    mock_urlopen.assert_not_called()


def test_jwt_fallback_resolves_user(tmp_settings):
    """With no body operator but a forwarded JWT + configured Supabase, the
    user is resolved server-side from /auth/v1/user."""
    settings = _supabase_settings(tmp_settings)
    payload = {
        "user": {
            "id": "u1",
            "email": "jane@x.io",
            "user_metadata": {"full_name": "Jane Doe"},
        }
    }
    with patch(
        "urllib.request.urlopen",
        return_value=_FakeResponse(json.dumps(payload).encode()),
    ) as mock_urlopen:
        op = resolve_operator({}, "Bearer jwt-token", settings)
    assert op == {"name": "Jane Doe", "email": "jane@x.io", "role": "Operator"}
    # It really called the Supabase user endpoint with the forwarded token.
    assert mock_urlopen.called
    request = mock_urlopen.call_args.args[0]
    assert str(request.full_url).endswith("/auth/v1/user")
    assert request.headers["Authorization"] == "Bearer jwt-token"


def test_no_operator_without_source(tmp_settings):
    """No body operator and no usable identity source -> None."""
    # Auth header present but Supabase not configured -> cannot fall back.
    assert resolve_operator({}, "Bearer jwt-token", tmp_settings) is None
    # No auth header at all.
    assert resolve_operator({}, None, tmp_settings) is None
    # Empty payload entirely.
    assert resolve_operator({}, "", tmp_settings) is None


def test_conversation_messages_includes_operator(tmp_settings):
    with_op = conversation_messages(
        "hi", [], {"name": "Jane Doe", "email": "jane@x.io", "role": "Operator"}
    )
    sys_op = with_op[0]["content"]
    assert "Jane Doe" in sys_op
    assert "speaking with" in sys_op

    without_op = conversation_messages("hi", [])
    assert "speaking with" not in without_op[0]["content"]


def test_get_user_profile_tool(tmp_settings, store):
    registry = ExamshieldToolRegistry(store)
    registry.operator = {"name": "Jane Doe", "email": "jane@x.io", "role": "Operator"}

    names = [t["function"]["name"] for t in registry.schemas()]
    assert "getUserProfile" in names

    execution = registry.execute("getUserProfile", {})
    assert execution.result["tool"] == "getUserProfile"
    metrics = {m["label"]: m["value"] for m in execution.result["metrics"]}
    assert metrics["Name"] == "Jane Doe"
    assert metrics["Email"] == "jane@x.io"
    assert metrics["Role"] == "Operator"


def test_get_user_profile_hidden_without_operator(tmp_settings, store):
    registry = ExamshieldToolRegistry(store)  # operator defaults to None

    names = [t["function"]["name"] for t in registry.schemas()]
    assert "getUserProfile" not in names

    execution = registry.execute("getUserProfile", {})
    assert execution.result["title"] == "NO OPERATOR CONTEXT"


def test_chat_session_wires_operator_end_to_end(tmp_settings, store):
    """Operator identity must reach both the tool schemas (so getUserProfile is
    offered) and the system prompt (so the model can use the name)."""
    events: list[dict] = []
    client = _CapturingClient()
    registry = ExamshieldToolRegistry(store)
    session = ChatSession(client=client, registry=registry, write=events.append)

    session.run(
        "hi Jane",
        [],
        None,
        {"name": "Jane Doe", "email": "jane@x.io", "role": "Operator"},
    )

    assert client.last_call is not None
    tool_names = [t["function"]["name"] for t in client.last_call.get("tools", [])]
    assert "getUserProfile" in tool_names

    system_content = client.last_call["messages"][0]["content"]
    assert "Jane Doe" in system_content
