from __future__ import annotations

import logging
import os
import time
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

TIKA_URL = os.environ.get("EXAMSHIELD_TIKA_URL", "http://localhost:9998").rstrip("/")
TIKA_ENABLED = os.environ.get("EXAMSHIELD_TIKA_ENABLED", "1").strip().lower() in {"1", "true", "yes", "on"}
TIKA_TIMEOUT_SECONDS = int(os.environ.get("EXAMSHIELD_TIKA_TIMEOUT", "90"))
TIKA_MIN_TEXT_CHARS = int(os.environ.get("EXAMSHIELD_TIKA_MIN_TEXT_CHARS", "200"))
PDF_MAX_PAGES = int(os.environ.get("EXAMSHIELD_PDF_MAX_PAGES", "20"))
RASTER_MAX_DIMENSION = int(os.environ.get("EXAMSHIELD_PDF_RASTER_MAX_DIM", "1920"))

# Document MIME types routed through Tika. Images stay on the direct OCR path.
DOCUMENT_TYPES: dict[str, set[str]] = {
    "application/pdf": {".pdf"},
    "application/msword": {".doc"},
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {".docx"},
    "application/rtf": {".rtf"},
    "text/rtf": {".rtf"},
    "application/vnd.ms-powerpoint": {".ppt"},
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": {".pptx"},
    "application/vnd.ms-excel": {".xls"},
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {".xlsx"},
    "application/vnd.oasis.opendocument.text": {".odt"},
}


def is_document_type(content_type: str) -> bool:
    return (content_type or "").split(";")[0].strip().lower() in DOCUMENT_TYPES


def tika_status() -> dict[str, Any]:
    reachable = False
    if TIKA_ENABLED and TIKA_URL:
        try:
            req = urllib.request.Request(f"{TIKA_URL}/version", method="GET")
            with urllib.request.urlopen(req, timeout=3) as response:
                reachable = response.status == 200
        except Exception:  # noqa: BLE001 - health probe must never raise
            reachable = False
    return {
        "enabled": TIKA_ENABLED,
        "url": TIKA_URL,
        "reachable": reachable,
        "minTextChars": TIKA_MIN_TEXT_CHARS,
        "maxPages": PDF_MAX_PAGES,
        "documentTypes": sorted(DOCUMENT_TYPES),
    }


def _tika_request(path: str, data: bytes, content_type: str, accept: str) -> bytes | None:
    req = urllib.request.Request(
        f"{TIKA_URL}{path}",
        data=data,
        method="PUT",
        headers={"Content-Type": content_type, "Accept": accept},
    )
    try:
        with urllib.request.urlopen(req, timeout=TIKA_TIMEOUT_SECONDS) as response:
            if response.status in (200, 204):
                return response.read()
            logger.warning("Tika %s returned HTTP %s", path, response.status)
            return None
    except urllib.error.HTTPError as exc:
        logger.warning("Tika %s rejected payload: HTTP %s", path, exc.code)
        return None
    except Exception as exc:  # noqa: BLE001 - extraction failures degrade to OCR
        logger.warning("Tika %s unreachable: %s", path, type(exc).__name__)
        return None


def detect_mime(data: bytes) -> str | None:
    body = _tika_request("/detect/stream", data, "application/octet-stream", "text/plain")
    if body:
        mime = body.decode("utf-8", errors="replace").strip()
        return mime or None
    return None


def extract_text(data: bytes, content_type: str) -> str | None:
    body = _tika_request("/tika", data, content_type, "text/plain")
    if body is None:
        return None
    return body.decode("utf-8", errors="replace")


def _result(engine: str, text: str, confidence: int, started: float, mode: str, pages: int = 1) -> dict[str, Any]:
    return {
        "status": "completed",
        "engine": engine,
        "mode": mode,
        "pages": pages,
        "confidence": confidence if text.strip() else 0,
        "text": text,
        "processingTimeMs": int((time.perf_counter() - started) * 1000),
        "message": "Text extracted" if text.strip() else "No Exam Content Detected",
        "qualityScore": 100 if mode == "tika-embedded-text" else confidence,
    }


def _failed(error: str, started: float) -> dict[str, Any]:
    return {
        "status": "failed",
        "engine": "tika",
        "confidence": 0,
        "text": "",
        "processingTimeMs": int((time.perf_counter() - started) * 1000),
        "error": error,
    }


def _rasterize_pdf(data: bytes) -> list[bytes]:
    """Render PDF pages to PNG bytes so they can reuse the image OCR chain."""
    try:
        import pymupdf
    except ImportError:  # pragma: no cover - PyMuPDF ships in requirements.txt
        import fitz as pymupdf  # type: ignore[no-redef]

    pages: list[bytes] = []
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        for page in doc.pages(0, min(doc.page_count, PDF_MAX_PAGES)):
            zoom = RASTER_MAX_DIMENSION / max(page.rect.width, page.rect.height, 1)
            pix = page.get_pixmap(matrix=pymupdf.Matrix(min(zoom, 4.0), min(zoom, 4.0)))
            pages.append(pix.tobytes("png"))
    if doc.page_count > PDF_MAX_PAGES:
        logger.warning("PDF has %s pages; rasterized first %s only", doc.page_count, PDF_MAX_PAGES)
    return pages


def analyze_document(data: bytes, declared_type: str, filename: str = "") -> dict[str, Any]:
    """Extract text from any supported document via local Apache Tika.

    Strategy:
      1. Detect the real MIME type with Tika (falls back to declared).
      2. Extract the embedded text layer (works for 1000+ formats).
      3. If the document carries little/no text (scanned PDF), rasterize its
         pages and run them through the existing image OCR chain instead.

    Returns the same shape as ocr.analyze_image so callers can treat both
    paths identically.
    """
    from .ocr import analyze_image

    started = time.perf_counter()
    if not TIKA_ENABLED:
        return _failed("Tika document ingestion is disabled (EXAMSHIELD_TIKA_ENABLED=0).", started)

    detected = detect_mime(data)
    mime = detected or declared_type.split(";")[0].strip().lower()
    logger.info("Tika detected %s (declared %s) for %s", mime, declared_type, filename or "<unnamed>")

    if mime.startswith("image/"):
        suffix = ".png" if "png" in mime else ".jpg"
        result = analyze_image(data, suffix)
        result["mode"] = "ocr-image"
        return result

    text = extract_text(data, mime)
    if text is None:
        return _failed("Tika text extraction failed.", started)
    stripped = text.strip()
    if not stripped:
        if mime != "application/pdf":
            return _failed("Document contains no extractable text.", started)
        logger.info("No embedded text in PDF; falling back to page rasterization + OCR")
    elif mime != "application/pdf" or len(stripped) >= TIKA_MIN_TEXT_CHARS:
        # Office formats carry their full text in-band regardless of length.
        return _result("tika", text, 100, started, mode="tika-embedded-text")

    # Scanned PDF suspicion: little/no embedded text — render pages and run
    # them through the image OCR chain instead.
    try:
        page_images = _rasterize_pdf(data)
    except Exception as exc:  # noqa: BLE001 - corrupt/encrypted PDFs land here
        return _failed(f"PDF rasterization failed: {type(exc).__name__}: {exc}", started)
    if not page_images:
        return _failed("PDF produced no renderable pages.", started)

    texts: list[str] = []
    confidences: list[int] = []
    for index, image_bytes in enumerate(page_images, start=1):
        page_result = analyze_image(image_bytes, ".png")
        if page_result.get("status") == "completed":
            texts.append(str(page_result.get("text") or ""))
            confidences.append(int(page_result.get("confidence") or 0))
        else:
            texts.append("")
            confidences.append(0)
        logger.info("Rasterized page %s/%s OCR confidence=%s", index, len(page_images), confidences[-1])

    combined = "\n\n".join(part for part in texts if part).strip()
    average_confidence = int(sum(confidences) / len(confidences)) if confidences else 0
    if not combined:
        if stripped:
            # Keep whatever small text layer existed rather than failing outright.
            return _result("tika", text, 60, started, mode="tika-partial-text", pages=len(page_images))
        return _failed("OCR found no readable text on any rendered page.", started)
    return _result(
        "tika+raster-ocr",
        combined,
        average_confidence,
        started,
        mode="tika-rasterized-ocr",
        pages=len(page_images),
    )
