"""Tests for the citation-grounding check (audit §11.2 — unverified numbers)."""
from __future__ import annotations

from examshield_ai.hallucination import verify_citations


def test_grounded_numbers_present():
    answer = "We found 42 papers and 1,250 students affected."
    ctx = "Summary: 42 papers linked to 1,250 students across 3 states."
    report = verify_citations(answer, ctx)
    assert report["context_present"] is True
    assert report["grounded"] is True
    assert report["unverified"] == []


def test_unverified_numbers_flagged():
    answer = "The leak involved 9,999 papers."
    ctx = "Summary: 42 papers linked to 1,250 students."
    report = verify_citations(answer, ctx)
    assert report["grounded"] is False
    assert "9999" in report["unverified"]


def test_no_context_is_neutral():
    report = verify_citations("There are 50 cases.", None)
    assert report["context_present"] is False
    assert report["grounded"] is True  # can't verify, don't punish


def test_empty_answer_is_grounded():
    assert verify_citations("", "anything")["grounded"] is True


def test_single_digits_ignored():
    answer = "Step 1 of 2 is done."
    report = verify_citations(answer, "nothing here")
    # single-digit numbers should not be treated as unverified figures
    assert report["unverified"] == []


def test_short_claim_prefix_match():
    # answer "12" vs context "1,234" should NOT auto-match (too short/ambiguous)
    report = verify_citations("12 cases reported.", "1,234 cases reported total.")
    assert "12" in report["unverified"]


def test_verified_claim_in_longer_context_number():
    # answer "1234" substring of context "12345" -> not unverified (>=3 digit prefix match)
    report = verify_citations("1234 cases.", "There were 12345 cases last year.")
    assert "1234" not in report["unverified"]


def test_total_count_reported():
    report = verify_citations("99 and 88 and 77.", "77 only")
    assert report["total"] == 3
