from __future__ import annotations

from examshield_ai.store import final_confidence_score


def test_final_confidence_uses_paper_confidence_without_watermark():
    assert final_confidence_score(80, 72, 0) == 72
    assert final_confidence_score(80, None, 0) == 80


def test_empty_registry_is_reported_as_not_run(store):
    result = store.run_attribution_for_evidence(
        "EV-TEST",
        "HACKATHON SUBMISSION YOUR DATA YOUR CONTROL",
        80,
    )

    assert result["attribution"]["status"] == "no-match"
    assert result["forensicReport"]["status"] == "no-match"
    assert result["forensicReport"]["comparisonStatus"] == "not-run"
    assert result["forensicReport"]["referenceCount"] == 0
    assert result["forensicReport"]["finalConfidence"] == 0
