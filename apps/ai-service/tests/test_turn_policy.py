from __future__ import annotations

from examshield_ai.turn_policy import (
    TurnIntent,
    classify_turn_intent,
    is_casual_greeting,
)


def test_greetings_route_to_conversation():
    # Pure small-talk skips tool schemas so greetings stay fast. Looser greetings
    # (e.g. "hello there") now route to TOOL_REQUEST and the model decides — it
    # simply answers conversationally without calling a tool.
    assert classify_turn_intent("hi!") is TurnIntent.CONVERSATION
    assert classify_turn_intent("hello") is TurnIntent.CONVERSATION


def test_live_data_requests_route_to_tool_request():
    assert classify_turn_intent("show me recent evidence") is TurnIntent.TOOL_REQUEST
    assert classify_turn_intent("generate a report") is TurnIntent.TOOL_REQUEST


def test_vague_request_routes_to_tool_request():
    """Regression for the 'hardcoded routing' complaint: vague natural language
    like "run a live check for me" must still attach tool schemas so the model
    can fire a live EXAMSHIELD tool — not just prompts containing keywords."""
    assert classify_turn_intent("run a live check for me") is TurnIntent.TOOL_REQUEST
    assert classify_turn_intent("check things for me") is TurnIntent.TOOL_REQUEST
    assert classify_turn_intent("what's going on with the leaks") is TurnIntent.TOOL_REQUEST



def test_classification_results_are_cached():
    """§5/§11.2: 'no caching of no-tool-needed decisions'. The classifier must
    cache results so repeated prompts (e.g. the same greeting) do not re-run."""
    classify_turn_intent("show me recent evidence")
    before = classify_turn_intent.cache_info()
    classify_turn_intent("show me recent evidence")
    assert classify_turn_intent.cache_info().hits > before.hits


def test_is_casual_greeting_detects_small_talk():
    assert is_casual_greeting("hey!")
    assert not is_casual_greeting("show evidence")
