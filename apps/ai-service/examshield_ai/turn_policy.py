"""Cheap, synchronous turn-intent classification for EXAMSHIELD AI.

Adapted from Ares ``turn_policy.classify_turn_intent``. The classifier is
intentionally tiny and runs with **zero** LLM calls.

Routing philosophy (borrowed from Ares "MODEL_ROUTED"):

* Pure small-talk (hi / thanks / bye / …) returns ``CONVERSATION`` so we skip
  tool schemas entirely and the model answers directly and cheaply.
* **Everything else defaults to ``TOOL_REQUEST``** — we attach the full tool
  schema set and let the model decide, via function calling, whether a live
  EXAMSHIELD tool applies. This is what makes vague requests like "run a live
  check for me" actually fire a tool, instead of being treated as plain chat
  just because they don't contain a hard-coded keyword.

We deliberately do NOT keyword-gate tool routing the way an earlier version
did: keyword overlap is not authority, and gating on keywords meant natural
language silently lost access to tools. EXAMSHIELD's tool set is read-only
(list / get / attribution / search / report), so letting the model choose is
safe — there is no destructive action to guard.
"""

from __future__ import annotations

import re
from enum import Enum
from functools import lru_cache
from typing import Final


class TurnIntent(str, Enum):
    CONVERSATION = "conversation"
    TOOL_REQUEST = "tool_request"


# Casual, non-task chatter. Ares treats these as pure conversation; we send them
# to the LLM with NO tool schemas attached so greetings stay fast.
_CASUAL_RE: Final[re.Pattern[str]] = re.compile(
    r"^\s*(?:hi|hello|hey|hiya|yo|sup|thanks|thank\s+you|thx|okay|ok|cool|nice|"
    r"great|got\s+it|sounds\s+good|alright|bye|goodbye|welcome|sure|np|no\s+problem)"
    r"[!.?,\s]*$",
    re.IGNORECASE,
)


@lru_cache(maxsize=2048)
def classify_turn_intent(text: str) -> TurnIntent:
    """Return whether this turn needs live EXAMSHIELD tools.

    Pure regex — no LLM, sub-millisecond. Returns ``CONVERSATION`` only for
    empty input or pure small-talk; every other message returns
    ``TOOL_REQUEST`` so the model can pick the right tool via function calling.

    Results are memoised so repeated prompts are not re-classified. Use
    ``clear_turn_intent_cache`` to reset it (e.g. in tests).
    """
    value = str(text or "").strip()
    if not value or _CASUAL_RE.fullmatch(value.casefold()):
        return TurnIntent.CONVERSATION
    # Default: model decides. Attach tool schemas and let the model choose the
    # right EXAMSHIELD tool via function calling (Ares "MODEL_ROUTED"). This is
    # what makes vague requests like "run a live check" actually fire a tool
    # instead of being treated as plain chat. Our tools are read-only, so no
    # extra safety gate is needed.
    return TurnIntent.TOOL_REQUEST


def clear_turn_intent_cache() -> None:
    """Reset the classification memoisation cache (primarily for tests)."""
    classify_turn_intent.cache_clear()


def is_casual_greeting(text: str) -> bool:
    """True for pure small-talk that never needs tools."""
    return bool(_CASUAL_RE.fullmatch(str(text or "").strip().casefold()))
