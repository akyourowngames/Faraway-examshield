from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from pathlib import Path
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)

OCR_SPACE_API_KEY = os.environ.get("OCR_SPACE_API_KEY", "").strip()
OCR_SPACE_API_URL = os.environ.get("OCR_SPACE_API_URL", "https://api.ocr.space/parse/image").strip()
OCR_SPACE_LANGUAGE = os.environ.get("OCR_SPACE_LANGUAGE", "eng").strip() or "eng"
OCR_SPACE_ENGINE = os.environ.get("OCR_SPACE_ENGINE", "2").strip() or "2"
OCR_SPACE_SCALE = os.environ.get("OCR_SPACE_SCALE", "1").strip().lower() in {"1", "true", "yes", "on"}
OCR_SPACE_DETECT_ORIENTATION = os.environ.get("OCR_SPACE_DETECT_ORIENTATION", "1").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
OCR_SPACE_TIMEOUT_SECONDS = int(os.environ.get("OCR_SPACE_TIMEOUT_SECONDS", "45"))


def ocrspace_configured() -> bool:
    return bool(OCR_SPACE_API_KEY)


def ocrspace_status() -> dict[str, Any]:
    return {
        "configured": ocrspace_configured(),
        "apiUrl": OCR_SPACE_API_URL,
        "language": OCR_SPACE_LANGUAGE,
        "engine": OCR_SPACE_ENGINE,
        "scale": OCR_SPACE_SCALE,
        "detectOrientation": OCR_SPACE_DETECT_ORIENTATION,
        "timeoutSeconds": OCR_SPACE_TIMEOUT_SECONDS,
    }


def run_ocrspace_ocr(image_path: Path, *, timeout: int | None = None) -> dict[str, Any]:
    """Run OCR through the OCR.space HTTP API."""
    from .ocr import estimate_confidence_from_text, normalize_text, score_ocr_quality

    if not ocrspace_configured():
        return _failed_candidate("OCR_SPACE_API_KEY is not configured.")

    call_timeout = timeout or OCR_SPACE_TIMEOUT_SECONDS
    try:
        payload = _call_ocrspace(image_path, timeout=call_timeout)
    except FuturesTimeoutError:
        return _failed_candidate(f"OCR.space timed out after {call_timeout}s")
    except urllib.error.HTTPError as exc:
        return _failed_candidate(f"OCR.space HTTP {exc.code}: {exc.reason}")
    except urllib.error.URLError as exc:
        return _failed_candidate(f"OCR.space network error: {exc.reason}")
    except Exception as exc:
        return _failed_candidate(f"OCR.space error: {type(exc).__name__}: {exc}")

    if payload.get("IsErroredOnProcessing"):
        message = _extract_error_message(payload)
        return _failed_candidate(message or "OCR.space processing failed.")

    exit_code = int(payload.get("OCRExitCode") or 0)
    if exit_code not in {1, 2}:
        message = _extract_error_message(payload) or f"OCR.space exit code {exit_code}"
        return _failed_candidate(message)

    raw_text = normalize_text(_extract_parsed_text(payload))
    if not raw_text:
        return {
            "status": "completed",
            "engine": "ocrspace",
            "psm": "ocrspace",
            "text": "",
            "confidence": 0,
            "qualityScore": 0,
            "quality": {
                "wordCount": 0,
                "meaningfulWordCount": 0,
                "cleanRatio": 0,
                "punctuationRatio": 0,
                "shortLineRatio": 1,
            },
        }

    words = [word for word in raw_text.split() if word.strip()]
    confidence = estimate_confidence_from_text(raw_text, words)
    quality_report = score_ocr_quality(raw_text, confidence, words)
    return {
        "status": "completed",
        "engine": "ocrspace",
        "psm": "ocrspace",
        "text": raw_text,
        "confidence": confidence,
        **quality_report,
    }


def _call_ocrspace(image_path: Path, *, timeout: int) -> dict[str, Any]:
    def _request() -> dict[str, Any]:
        image_bytes = image_path.read_bytes()
        suffix = image_path.suffix.lower().lstrip(".") or "jpg"
        filetype = "PNG" if suffix == "png" else "JPG"
        content_type = "image/png" if filetype == "PNG" else "image/jpeg"
        fields = {
            "apikey": OCR_SPACE_API_KEY,
            "language": OCR_SPACE_LANGUAGE,
            "OCREngine": OCR_SPACE_ENGINE,
            "filetype": filetype,
            "scale": "true" if OCR_SPACE_SCALE else "false",
            "detectOrientation": "true" if OCR_SPACE_DETECT_ORIENTATION else "false",
            "isOverlayRequired": "false",
        }
        body, content_type_header = _encode_multipart(
            fields,
            {
                "file": (
                    image_path.name or f"evidence.{suffix}",
                    image_bytes,
                    content_type,
                )
            },
        )
        request = urllib.request.Request(
            OCR_SPACE_API_URL,
            data=body,
            headers={"Content-Type": content_type_header},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
        return json.loads(raw)

    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="ocrspace") as executor:
        future = executor.submit(_request)
        return future.result(timeout=timeout)


def _encode_multipart(
    fields: dict[str, str],
    files: dict[str, tuple[str, bytes, str]],
) -> tuple[bytes, str]:
    boundary = f"----examshield{uuid4().hex}"
    body = bytearray()
    for name, value in fields.items():
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        body.extend(value.encode())
        body.extend(b"\r\n")
    for name, (filename, data, content_type) in files.items():
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(
            f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode()
        )
        body.extend(f"Content-Type: {content_type}\r\n\r\n".encode())
        body.extend(data)
        body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode())
    return bytes(body), f"multipart/form-data; boundary={boundary}"


def _extract_parsed_text(payload: dict[str, Any]) -> str:
    parsed_results = payload.get("ParsedResults") or []
    chunks: list[str] = []
    for item in parsed_results:
        if not isinstance(item, dict):
            continue
        text = str(item.get("ParsedText") or "").strip()
        if text:
            chunks.append(text)
    return "\n".join(chunks)


def _extract_error_message(payload: dict[str, Any]) -> str:
    for key in ("ErrorMessage", "ErrorDetails"):
        value = payload.get(key)
        if isinstance(value, list):
            joined = "; ".join(str(item).strip() for item in value if str(item).strip())
            if joined:
                return joined
        if value:
            return str(value).strip()
    parsed_results = payload.get("ParsedResults") or []
    for item in parsed_results:
        if isinstance(item, dict) and item.get("ErrorMessage"):
            return str(item["ErrorMessage"]).strip()
    return ""


def _failed_candidate(error: str) -> dict[str, Any]:
    return {
        "status": "failed",
        "engine": "ocrspace",
        "psm": "ocrspace",
        "text": "",
        "confidence": 0,
        "qualityScore": 0,
        "error": error,
    }
