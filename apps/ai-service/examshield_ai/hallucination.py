"""Lightweight grounding check for LLM answers against the source data they cite.

Audit §11.2 flags that tool results are injected with "don't fabricate"
instructions but the model still emits free text and **nothing verifies that
numbers it quotes actually appear in the source**. This module provides
:func:`verify_citations`, a heuristic that extracts numeric claims from a model
answer and checks each against the supplied context (the tool result / system
data). It is intentionally cheap and conservative — it flags *candidate*
ungrounded figures so the caller can warn the user, not to hard-block output.
"""

from __future__ import annotations

import re
from typing import Any

# Matches numbers with optional thousands separators, decimals, %, and units
# like "1,250", "12.5%", "₹3.2L", "42 papers". Captures the bare digits.
_NUMBER_RE = re.compile(r"(?<![\w.])([\d][\d,]*(?:\.\d+)?)\s*(%|percent|crore|lakh|l|k)?", re.IGNORECASE)

# Words that usually indicate a non-factual / rhetorical number we should ignore.
_IGNORE_CONTEXT_RE = re.compile(
    r"\b(thank|please|step \d|figure \d|example|approx|around|about|maybe|if|when|suppose)\b",
    re.IGNORECASE,
)


def _normalise(number: str) -> str:
    return "".join(ch for ch in number if ch.isdigit())


def _numbers_in(text: str) -> list[str]:
    """Return the digit-only normalisation of every numeric token in ``text``."""
    out: list[str] = []
    for match in _NUMBER_RE.finditer(text or ""):
        digits = _normalise(match.group(1))
        if len(digits) >= 2:  # ignore single digits (too noisy / common)
            out.append(digits)
    return out


def verify_citations(answer: str, context: str | None) -> dict[str, Any]:
    """Check numeric claims in ``answer`` against ``context``.

    Returns ``{"grounded": bool, "total": int, "unverified": list[str],
    "context_present": bool}``. ``grounded`` is ``True`` when either no context
    was supplied or every multi-digit number in the answer also appears in the
    context (as a substring of its digits).
    """
    if not answer:
        return {"grounded": True, "total": 0, "unverified": [], "context_present": bool(context)}

    claims = _numbers_in(answer)
    context_present = bool(context and context.strip())
    if not context_present:
        # Nothing to verify against; do not punish (caller decides policy).
        return {"grounded": True, "total": len(claims), "unverified": [], "context_present": False}

    ctx_digits = _numbers_in(context)
    # Build a set of normalised digit strings present in the context for fast lookup.
    ctx_set = {d for d in ctx_digits}
    # Also allow a claim to be "contained" in a longer context number
    # (e.g. answer "12" vs context "1,234" should not auto-match, but exact or
    #  prefix/suffix alignment is acceptable for short claims).
    unverified: list[str] = []
    for claim in claims:
        if claim not in ctx_set and not any(c.startswith(claim) or c.endswith(claim) for c in ctx_set if len(claim) >= 3):
            unverified.append(claim)

    total = len(claims)
    grounded = len(unverified) == 0
    return {
        "grounded": grounded,
        "total": total,
        "unverified": unverified,
        "context_present": True,
    }
