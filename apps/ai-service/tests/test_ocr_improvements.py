"""Deep tests for the §11.1 OCR improvements (languages, preprocess, chain, cache)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from examshield_ai import ocr


@pytest.fixture(autouse=True)
def _isolate_ocr_cache():
    ocr._OCR_RESULT_CACHE.clear()
    yield
    ocr._OCR_RESULT_CACHE.clear()


def test_default_chain_is_ocrspace_first():
    # Tesseract times out on large exam images (hiding real 100% leak matches),
    # so the paid OCR.space engine now leads and Tesseract fills the gaps.
    assert ocr.OCR_CHAIN[0] == "ocrspace"


def test_language_is_threaded_to_tesseract(tmp_path: Path):
    image_path = tmp_path / "img.jpg"
    image_path.write_bytes(b"fake")

    captured = {}

    def fake_run(*args, **kwargs):
        captured["args"] = args[1]  # the tesseract arg list
        raise RuntimeError("stop after capturing args")

    with patch("examshield_ai.ocr.run_tesseract", side_effect=fake_run):
        try:
            ocr.read_ocr_candidate(image_path, "6", languages="eng+hin")
        except RuntimeError:
            pass

    assert "-l" in captured["args"]
    idx = captured["args"].index("-l")
    assert captured["args"][idx + 1] == "eng+hin"


def test_default_language_is_eng():
    assert ocr.OCR_LANGUAGES == "eng"


def test_low_quality_rejected_when_threshold_high(tmp_path: Path):
    candidate = {
        "status": "completed",
        "engine": "tesseract",
        "psm": "6",
        "text": "some text",
        "confidence": 40,
        "qualityScore": 10,
    }
    with patch("examshield_ai.ocr.prepare_ocr_image", return_value=tmp_path / "x.jpg"), patch(
        "examshield_ai.ocr.OCR_CHAIN", ("tesseract",)
    ), patch("examshield_ai.ocr.run_tesseract_best_candidate", return_value=candidate), patch(
        "examshield_ai.ocr.OCR_MIN_QUALITY", 80
    ), patch("pathlib.Path.unlink"):
        result = ocr.analyze_image(b"img", ".jpg")

    assert result["status"] == "failed"


def test_identical_bytes_served_from_cache(tmp_path: Path):
    candidate = {
        "status": "completed",
        "engine": "tesseract",
        "psm": "6",
        "text": "cached result",
        "confidence": 90,
        "qualityScore": 90,
    }
    with patch("examshield_ai.ocr.prepare_ocr_image", return_value=tmp_path / "x.jpg"), patch(
        "examshield_ai.ocr.OCR_CHAIN", ("tesseract",)
    ), patch(
        "examshield_ai.ocr.run_tesseract_best_candidate", return_value=candidate
    ) as engine, patch("pathlib.Path.unlink"):
        first = ocr.analyze_image(b"same-bytes", ".jpg")
        second = ocr.analyze_image(b"same-bytes", ".jpg")

    # Engine only ran once; the second call hit the content-hash cache.
    assert engine.call_count == 1
    assert first["text"] == second["text"] == "cached result"


def test_tesseract_timeout_does_not_exceed_budget():
    # Audit §11.1 timeout concern: a hung engine must not consume the full budget.
    # remaining_timeout caps the per-call timeout to the remaining budget.
    import time

    deadline = time.perf_counter() + 5
    remaining = ocr.remaining_timeout(deadline, fallback=120)
    assert remaining <= 5


def test_preprocess_improves_image_shape():
    cv2 = pytest.importorskip("cv2")
    import numpy as np

    # Synthetic "scanned paper": white background, black text block, slight skew.
    frame = np.full((200, 400, 3), 255, dtype=np.uint8)
    cv2.putText(frame, "NEET 2026", (40, 100), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 0), 3)

    out = ocr._preprocess_for_ocr(frame)
    assert out is not None
    assert out.shape == frame.shape
    # Output should be a 3-channel BGR image.
    assert len(out.shape) == 3 and out.shape[2] == 3


def test_deskew_returns_image():
    cv2 = pytest.importorskip("cv2")
    import numpy as np

    frame = np.full((100, 200), 255, dtype=np.uint8)
    cv2.putText(frame, "text", (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)

    out = ocr._deskew(frame)
    assert out.shape == frame.shape
