"""Tests that ChatSession surfaces an unverified-numbers warning (audit §11.2)."""
from __future__ import annotations

from examshield_ai.chat import ChatSession
from examshield_ai.settings import Settings
from examshield_ai.tools import ExamshieldToolRegistry


def _fake_session(tmp_settings: Settings) -> tuple[ChatSession, list[dict]]:
    events: list[dict] = []

    class _FakeClient:
        def __init__(self, settings: Settings) -> None:
            self.settings = settings

        @property
        def configured(self) -> bool:
            return True

    client = _FakeClient(tmp_settings)
    registry = ExamshieldToolRegistry.__new__(ExamshieldToolRegistry)
    session = ChatSession(client=client, registry=registry, write=events.append)
    return session, events


def test_warning_emitted_when_unverified(tmp_settings: Settings):
    session, events = _fake_session(tmp_settings)
    session._maybe_warn_unverified(
        "The leak involved 9,999 papers.",
        "Summary: 42 papers linked to 1,250 students.",
    )
    warnings = [e for e in events if e.get("type") == "warning"]
    assert warnings, "expected a warning event"
    assert "9999" in warnings[0]["message"]


def test_no_warning_when_grounded(tmp_settings: Settings):
    session, events = _fake_session(tmp_settings)
    session._maybe_warn_unverified(
        "We found 42 papers.",
        "Summary: 42 papers linked to 1,250 students.",
    )
    assert not [e for e in events if e.get("type") == "warning"]


def test_no_warning_without_context(tmp_settings: Settings):
    session, events = _fake_session(tmp_settings)
    session._maybe_warn_unverified("There are 50 cases.", "")
    assert not [e for e in events if e.get("type") == "warning"]
