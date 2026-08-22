from __future__ import annotations

from examshield_ai.hallucination import (
    extract_checkable_tokens,
    split_claims,
    verify_answer,
    verify_claim,
)


def test_split_claims_breaks_on_sentence_boundaries_and_newlines():
    claims = split_claims("Found 3 alerts. Risk is high!\nSecond line here")

    assert claims == ["Found 3 alerts.", "Risk is high!", "Second line here"]


def test_extract_checkable_tokens_finds_ids_numbers_and_percentages():
    tokens = extract_checkable_tokens("Evidence EV-001 scored 87.5% against paper NEET-2024-DEL-014.")

    lowered = [token.lower() for token in tokens]
    assert "ev-001" in lowered
    assert "neet-2024-del-014" in lowered
    assert any(token.endswith("%") for token in tokens)


def test_prose_only_claims_are_supported_by_default():
    check = verify_claim("The investigation is ongoing and requires review.", "")

    assert check.supported
    assert check.missing_evidence == ()


def test_number_present_in_context_is_supported():
    check = verify_claim("There are 12 open alerts.", "Open alerts: 12 across 2 centers")

    assert check.supported


def test_fabricated_percentage_is_flagged():
    check = verify_claim("Confidence is 95%.", "OCR confidence was 61 percent on this document.")

    assert not check.supported
    assert "95%" in check.missing_evidence


def test_percentages_match_bare_numbers_in_context():
    check = verify_claim("Match rate is 40%.", "similarity: 40")

    assert check.supported


def test_fabricated_evidence_id_is_flagged():
    check = verify_claim("Evidence EV-999 confirms the leak.", "Evidence EV-001 was uploaded today.")

    assert not check.supported
    assert "EV-999" in check.missing_evidence


def test_empty_context_flags_any_numeric_claim():
    report = verify_answer("Total evidence is 7 items.", [])

    assert report.verdict == "ungrounded"
    assert report.unsupported[0].missing_evidence == ("7",)


def test_mixed_answer_yields_partial_verdict_and_ratio():
    answer = "There are 5 open alerts. The paper NEET-2024-DEL-014 is compromised."
    contexts = ["Alerts open: 5"]

    report = verify_answer(answer, contexts)

    assert report.verdict == "partial"
    assert len(report.supported) == 1
    assert len(report.unsupported) == 1
    assert report.grounded_ratio == 0.5
    assert "NEET-2024-DEL-014" in report.unsupported[0].missing_evidence


def test_unsupported_majority_yields_ungrounded_verdict():
    answer = "Score is 99%. Center count is 42. Evidence EV-777 exists."
    contexts = ["No relevant data."]

    report = verify_answer(answer, contexts)

    assert report.verdict == "ungrounded"
    assert len(report.unsupported) == 3
    assert report.grounded_ratio == 0.0


def test_grounded_answer_passes_cleanly():
    answer = "Two papers were flagged, and 30% of uploads came from Telegram."
    contexts = ["flagged papers: 2", "telegram share: 30%"]

    report = verify_answer(answer, contexts)

    assert report.verdict == "grounded"
    assert report.as_dict()["verdict"] == "grounded"


def test_empty_answer_is_treated_as_grounded():
    report = verify_answer("", ["context"])

    assert report.checks == ()
    assert report.grounded_ratio == 1.0
    assert report.verdict == "grounded"


def test_as_dict_shape_is_stable_for_api_use():
    report = verify_answer("Count is 9.", ["count: 9"])

    payload = report.as_dict()

    assert set(payload) == {"verdict", "groundedRatio", "checks"}
    assert set(payload["checks"][0]) == {"claim", "supported", "missingEvidence"}
