"""Cheap, synchronous turn-intent classification for EXAMSHIELD AI.

Adapted from Ares ``turn_policy.classify_turn_intent``. The whole point is
speed: this runs with **zero** LLM calls so the chat route can decide whether
a message needs live EXAMSHIELD tools before it ever hits the model. Ares
proved that a pure-regex classifier is enough to pick conversation vs. tool
routing for the common cases, which is what removes the slow separate
planning pass.

The classifier is intentionally conservative: when in doubt it routes to the
model with tools attached rather than guessing. The model still does the final
tool-selection via function calling — this classifier only narrows the
decision so we avoid an extra round-trip and avoid sending every tool schema
on every turn.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Final


class TurnIntent(str, Enum):
    CONVERSATION = "conversation"
    TOOL_REQUEST = "tool_request"


# Casual, non-task chatter. Ares treats these as pure conversation; we still
# send them to the LLM (per product decision) but with NO tool schemas attached
# so the model answers directly and cheaply.
_CASUAL_RE: Final[re.Pattern[str]] = re.compile(
    r"^\s*(?:hi|hello|hey|hiya|yo|sup|thanks|thank\s+you|thx|okay|ok|cool|nice|"
    r"great|got\s+it|sounds\s+good|alright|bye|goodbye|welcome|sure|np|no\s+problem)"
    r"[!.?,\s]*$",
    re.IGNORECASE,
)

# Keywords that strongly imply the investigator wants live EXAMSHIELD data.
_TOOL_KEYWORDS: Final[tuple[str, ...]] = (
    "evidence",
    "upload",
    "ocr",
    "investigation",
    "investigate",
    "attribution",
    "watermark",
    "trace",
    "source",
    "threat",
    "alert",
    "compromised",
    "leak",
    "risk",
    "paper",
    "registry",
    "neet",
    "jee",
    "center",
    "report",
    "briefing",
    "summary",
    "memory",
    "correlation",
    "pattern",
    "match",
)

_TOOL_VERB_RE: Final[re.Pattern[str]] = re.compile(
    r"\b(?:show|list|get|find|search|look\s+up|generate|create|view|display|"
    r"what\s+are|what\s+is|how\s+many|tell\s+me\s+about|summar|analy[sz]e)\b",
    re.IGNORECASE,
)

# Specific tool-trigger phrases that should always pull live data even without
# an obvious verb.
_TOOL_PHRASE_RE: Final[re.Pattern[str]] = re.compile(
    r"\b(?:ev-\d+|generate\s+(?:a\s+)?report|daily\s+report|operational\s+summary|"
    r"command\s+briefing|compromised\s+papers?|active\s+threats?|threat\s+posture|"
    r"where\s+did|who\s+leaked|search\s+memory)\b",
    re.IGNORECASE,
)

_EVIDENCE_ID_RE: Final[re.Pattern[str]] = re.compile(r"\bev-\d+\b", re.IGNORECASE)
_PAPER_ID_RE: Final[re.Pattern[str]] = re.compile(r"\b[A-Z]{2,}-\d{4}-[A-Z0-9-]+\b")


def classify_turn_intent(text: str) -> TurnIntent:
    """Return whether this turn needs live EXAMSHIELD tools.

    Pure regex — no LLM, sub-millisecond. Returns ``TOOL_REQUEST`` whenever the
    message looks like it wants live data, otherwise ``CONVERSATION``.
    """
    value = str(text or "").strip()
    if not value:
        return TurnIntent.CONVERSATION
    lowered = value.casefold()
    if _TOOL_PHRASE_RE.search(value):
        return TurnIntent.TOOL_REQUEST
    if _EVIDENCE_ID_RE.search(value) or _PAPER_ID_RE.search(value):
        return TurnIntent.TOOL_REQUEST
    if any(keyword in lowered for keyword in _TOOL_KEYWORDS):
        return TurnIntent.TOOL_REQUEST
    if _TOOL_VERB_RE.search(value):
        # A verb alone is not enough — but combined with data nouns it is.
        if any(
            noun in lowered
            for noun in (
                "evidence", "threat", "alert", "paper", "report", "memory",
                "attribution", "compromised", "leak", "investigation", "center",
                "watermark", "registry", "upload",
            )
        ):
            return TurnIntent.TOOL_REQUEST
    return TurnIntent.CONVERSATION


def is_casual_greeting(text: str) -> bool:
    """True for pure small-talk that never needs tools."""
    return bool(_CASUAL_RE.fullmatch(str(text or "").strip()))
