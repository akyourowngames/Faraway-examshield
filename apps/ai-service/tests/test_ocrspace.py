from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from examshield_ai.ocrspace import run_ocrspace_ocr


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._raw = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def test_run_ocrspace_parses_success_response(tmp_path: Path):
    image_path = tmp_path / "exam.jpg"
    image_path.write_bytes(b"\xff\xd8\xff\xe0fakejpeg")

    payload = {
        "OCRExitCode": 1,
        "IsErroredOnProcessing": False,
        "ParsedResults": [{"ParsedText": "MATHEMATICS EXAM 2026"}],
    }

    with patch("examshield_ai.ocrspace.OCR_SPACE_API_KEY", "test-key"), patch(
        "examshield_ai.ocrspace.urllib.request.urlopen",
        return_value=_FakeResponse(payload),
    ):
        result = run_ocrspace_ocr(image_path)

    assert result["status"] == "completed"
    assert result["engine"] == "ocrspace"
    assert "MATHEMATICS" in result["text"]


def test_run_ocrspace_requires_api_key(tmp_path: Path):
    image_path = tmp_path / "exam.jpg"
    image_path.write_bytes(b"\xff\xd8\xff\xe0fakejpeg")

    with patch("examshield_ai.ocrspace.OCR_SPACE_API_KEY", ""):
        result = run_ocrspace_ocr(image_path)

    assert result["status"] == "failed"
    assert "OCR_SPACE_API_KEY" in result["error"]
