from __future__ import annotations

import io
import urllib.error
from unittest.mock import patch

import pytest

from examshield_ai import documents


def _make_text_pdf(text: str) -> bytes:
    """Build a real PDF with an embedded text layer via PyMuPDF."""
    pymupdf = pytest.importorskip("pymupdf")
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=12)
    data = doc.tobytes()
    doc.close()
    return data


def _make_blank_pdf(pages: int = 2) -> bytes:
    """A PDF with no text layer at all (simulates a scanned document)."""
    pymupdf = pytest.importorskip("pymupdf")
    doc = pymupdf.open()
    for _ in range(pages):
        doc.new_page(width=612, height=792)
    data = doc.tobytes()
    doc.close()
    return data


class _FakeResponse(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_detect_mime_returns_tika_answer(monkeypatch):
    monkeypatch.setattr(
        documents.urllib.request,
        "urlopen",
        lambda req, timeout: _FakeResponse(b"application/pdf"),
    )
    assert documents.detect_mime(b"%PDF-1.4 fake") == "application/pdf"


def test_detect_mime_swallows_connection_errors(monkeypatch):
    def boom(req, timeout):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(documents.urllib.request, "urlopen", boom)
    assert documents.detect_mime(b"data") is None


def test_extract_text_plain_body(monkeypatch):
    monkeypatch.setattr(
        documents.urllib.request,
        "urlopen",
        lambda req, timeout: _FakeResponse(b"QUESTION 1. What is the capital of France?"),
    )
    assert "capital of France" in documents.extract_text(b"doc", "application/pdf")


def test_analyze_document_embedded_text_path(monkeypatch):
    pdf_bytes = b"%PDF-embedded"
    monkeypatch.setattr(documents, "detect_mime", lambda data: "application/pdf")
    monkeypatch.setattr(
        documents,
        "extract_text",
        lambda data, ctype: "Q1. Which of the following is correct? (1) A (2) B (3) C (4) D " * 10,
    )
    raster_calls = []
    monkeypatch.setattr(documents, "_rasterize_pdf", lambda data: raster_calls.append(data) or [])

    result = documents.analyze_document(pdf_bytes, "application/pdf")

    assert result["status"] == "completed"
    assert result["mode"] == "tika-embedded-text"
    assert result["confidence"] == 100
    assert not raster_calls


def test_analyze_document_short_office_doc_keeps_full_confidence(monkeypatch):
    """A short DOCX/XLSX is not a scan — its text is complete at any length."""
    monkeypatch.setattr(
        documents, "detect_mime", lambda data: "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    monkeypatch.setattr(documents, "extract_text", lambda data, ctype: "Q1. 2+2? A) 4")
    raster_calls = []
    monkeypatch.setattr(documents, "_rasterize_pdf", lambda data: raster_calls.append(data) or [])

    result = documents.analyze_document(b"docx-bytes", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")

    assert result["status"] == "completed"
    assert result["mode"] == "tika-embedded-text"
    assert result["confidence"] == 100
    assert not raster_calls


def test_analyze_document_scanned_pdf_falls_back_to_ocr(monkeypatch):
    pdf_bytes = b"%PDF-scanned"
    monkeypatch.setattr(documents, "detect_mime", lambda data: "application/pdf")
    monkeypatch.setattr(documents, "extract_text", lambda data, ctype: "")

    def fake_rasterize(data):
        return [b"page1png", b"page2png"]

    ocr_results = iter(
        [
            {"status": "completed", "text": "PAGE ONE TEXT", "confidence": 80},
            {"status": "completed", "text": "PAGE TWO TEXT", "confidence": 90},
        ]
    )

    import examshield_ai.ocr as ocr

    monkeypatch.setattr(documents, "_rasterize_pdf", fake_rasterize)
    monkeypatch.setattr(ocr, "analyze_image", lambda image_bytes, suffix: next(ocr_results))

    result = documents.analyze_document(pdf_bytes, "application/pdf")

    assert result["status"] == "completed"
    assert result["mode"] == "tika-rasterized-ocr"
    assert result["pages"] == 2
    assert "PAGE ONE TEXT" in result["text"]
    assert "PAGE TWO TEXT" in result["text"]
    assert result["confidence"] == 85


def test_analyze_document_pdf_ocr_failure_keeps_partial_text(monkeypatch):
    """If raster+OCR finds nothing, a small embedded text layer still survives."""
    monkeypatch.setattr(documents, "detect_mime", lambda data: "application/pdf")
    monkeypatch.setattr(documents, "extract_text", lambda data, ctype: "tiny")
    monkeypatch.setattr(documents, "_rasterize_pdf", lambda data: [b"page1png"])

    import examshield_ai.ocr as ocr

    monkeypatch.setattr(
        ocr, "analyze_image", lambda image_bytes, suffix: {"status": "failed", "text": "", "confidence": 0}
    )

    result = documents.analyze_document(b"%PDF-scan", "application/pdf")

    assert result["status"] == "completed"
    assert result["mode"] == "tika-partial-text"
    assert result["confidence"] == 60
    assert result["pages"] == 1


def test_analyze_document_routes_images_to_ocr(monkeypatch):
    import examshield_ai.ocr as ocr

    seen = {}

    def fake_analyze_image(image_bytes, suffix):
        seen["suffix"] = suffix
        return {"status": "completed", "text": "IMG TEXT", "confidence": 70}

    monkeypatch.setattr(documents, "detect_mime", lambda data: "image/png")
    monkeypatch.setattr(ocr, "analyze_image", fake_analyze_image)

    result = documents.analyze_document(b"\x89PNG fake", "image/png")

    assert result["mode"] == "ocr-image"
    assert seen["suffix"] == ".png"
    assert result["text"] == "IMG TEXT"


def test_analyze_document_disabled():
    with patch.object(documents, "TIKA_ENABLED", False):
        result = documents.analyze_document(b"data", "application/pdf")
    assert result["status"] == "failed"
    assert "disabled" in result["error"]


@pytest.mark.skipif(
    not documents.TIKA_ENABLED or not documents.tika_status()["reachable"],
    reason="local Tika server not reachable",
)
def test_integration_real_pdf_end_to_end():
    pdf_bytes = _make_text_pdf(
        "EXAMSHIELD INTEGRATION TEST. Question 1: What is 2 + 2? "
        "Option (1) 3 (2) 4 (3) 5 (4) 6. The answer is four. "
        "Question 2: Which of the following are prime numbers? "
        "(1) 7 (2) 9 (3) 11 (4) 15. Primes are seven and eleven. "
        "Question 3: Name the largest planet in our solar system "
        "among Mercury, Venus, Earth, Mars, Jupiter, Saturn."
    )
    result = documents.analyze_document(pdf_bytes, "application/pdf")
    assert result["status"] == "completed"
    assert result["mode"] in {"tika-embedded-text", "tika-rasterized-ocr"}
    assert "INTEGRATION TEST" in result["text"]
