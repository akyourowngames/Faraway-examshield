from __future__ import annotations

import inspect
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_paddle_engine: Any | None = None
_paddle_lock = threading.Lock()
_paddle_init_error: str | None = None

PADDLE_LANG = os.environ.get("EXAMSHIELD_PADDLE_LANG", "en").strip() or "en"
PADDLE_USE_ANGLE_CLS = os.environ.get("EXAMSHIELD_PADDLE_USE_ANGLE_CLS", "1").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
PADDLE_TIMEOUT_SECONDS = int(os.environ.get("EXAMSHIELD_PADDLE_TIMEOUT_SECONDS", "45"))


def paddle_importable() -> bool:
    try:
        import paddleocr  # noqa: F401

        return True
    except ImportError:
        return False


def paddle_available() -> bool:
    return _paddle_engine is not None and _paddle_init_error is None


def paddle_status() -> dict[str, Any]:
    return {
        "importable": paddle_importable(),
        "initialized": _paddle_engine is not None,
        "available": paddle_available(),
        "lang": PADDLE_LANG,
        "useAngleCls": PADDLE_USE_ANGLE_CLS,
        "timeoutSeconds": PADDLE_TIMEOUT_SECONDS,
        "initError": _paddle_init_error,
    }


def get_paddle_engine() -> Any:
    global _paddle_engine, _paddle_init_error
    if _paddle_engine is not None:
        return _paddle_engine
    if _paddle_init_error:
        raise RuntimeError(_paddle_init_error)

    with _paddle_lock:
        if _paddle_engine is not None:
            return _paddle_engine
        if _paddle_init_error:
            raise RuntimeError(_paddle_init_error)
        try:
            _paddle_engine = _create_paddle_engine()
            logger.info("PaddleOCR engine initialized (lang=%s)", PADDLE_LANG)
            return _paddle_engine
        except Exception as exc:
            _paddle_init_error = f"{type(exc).__name__}: {exc}"
            logger.warning("PaddleOCR unavailable: %s", _paddle_init_error)
            raise RuntimeError(_paddle_init_error) from exc


def _create_paddle_engine() -> Any:
    from paddleocr import PaddleOCR

    params = set(inspect.signature(PaddleOCR.__init__).parameters) - {"self"}
    attempts: list[dict[str, Any]] = []

    if "device" in params:
        attempt: dict[str, Any] = {"lang": PADDLE_LANG, "device": "cpu"}
        if "use_textline_orientation" in params:
            attempt["use_textline_orientation"] = PADDLE_USE_ANGLE_CLS
        attempts.append(attempt)

    if "use_gpu" in params:
        attempts.append(
            {
                "lang": PADDLE_LANG,
                "use_angle_cls": PADDLE_USE_ANGLE_CLS,
                "use_gpu": False,
                "show_log": False,
                "enable_mkldnn": False,
            }
        )

    attempts.append({"lang": PADDLE_LANG})

    errors: list[str] = []
    for attempt in attempts:
        filtered = {key: value for key, value in attempt.items() if key in params}
        try:
            engine = PaddleOCR(**filtered)
            logger.info("PaddleOCR init kwargs: %s", sorted(filtered))
            return engine
        except Exception as exc:
            errors.append(f"{filtered}: {type(exc).__name__}: {exc}")

    raise RuntimeError("PaddleOCR init failed: " + " | ".join(errors))


def run_paddle_ocr(image_path: Path, *, timeout: int | None = None) -> dict[str, Any]:
    """Run PaddleOCR and return a candidate-shaped result dict."""
    from .ocr import estimate_confidence_from_text, normalize_text, score_ocr_quality

    call_timeout = timeout or PADDLE_TIMEOUT_SECONDS
    try:
        raw_result = _invoke_paddle(image_path, timeout=call_timeout)
    except FuturesTimeoutError:
        return _failed_candidate(f"PaddleOCR timed out after {call_timeout}s")
    except RuntimeError as exc:
        return _failed_candidate(str(exc))
    except Exception as exc:
        return _failed_candidate(f"PaddleOCR error: {type(exc).__name__}: {exc}")

    lines, confidences = _extract_paddle_lines(raw_result)
    raw_text = normalize_text("\n".join(lines))
    if not raw_text:
        return {
            "status": "completed",
            "engine": "paddle",
            "psm": "paddle",
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
    confidence = (
        round(sum(confidences) / len(confidences))
        if confidences
        else estimate_confidence_from_text(raw_text, words)
    )
    quality_report = score_ocr_quality(raw_text, int(confidence), words)
    return {
        "status": "completed",
        "engine": "paddle",
        "psm": "paddle",
        "text": raw_text,
        "confidence": int(confidence),
        **quality_report,
    }


def _extract_paddle_lines(raw_result: Any) -> tuple[list[str], list[float]]:
    lines: list[str] = []
    confidences: list[float] = []

    if raw_result is None:
        return lines, confidences

    if isinstance(raw_result, dict):
        raw_result = [raw_result]

    if isinstance(raw_result, list) and raw_result and isinstance(raw_result[0], dict):
        for page in raw_result:
            texts = page.get("rec_texts") or page.get("texts") or []
            scores = page.get("rec_scores") or page.get("scores") or []
            for index, text in enumerate(texts):
                cleaned = str(text or "").strip()
                if not cleaned:
                    continue
                score = scores[index] if index < len(scores) else 0.75
                lines.append(cleaned)
                confidences.append(_normalize_confidence(score))
        return lines, confidences

    for block in raw_result:
        if not block:
            continue
        if isinstance(block, dict):
            nested_lines, nested_scores = _extract_paddle_lines(block)
            lines.extend(nested_lines)
            confidences.extend(nested_scores)
            continue
        for item in block:
            if not item or len(item) < 2:
                continue
            text_conf = item[1]
            if not isinstance(text_conf, (list, tuple)) or len(text_conf) < 2:
                continue
            text = str(text_conf[0] or "").strip()
            if not text:
                continue
            lines.append(text)
            confidences.append(_normalize_confidence(text_conf[1]))

    return lines, confidences


def _normalize_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0
    return confidence * 100 if confidence <= 1 else confidence


def _invoke_paddle(image_path: Path, *, timeout: int) -> Any:
    def _call() -> Any:
        engine = get_paddle_engine()
        path = str(image_path)
        if hasattr(engine, "predict"):
            try:
                return engine.predict(path)
            except TypeError:
                return engine.predict(input=path)
        if hasattr(engine, "ocr"):
            try:
                return engine.ocr(path, cls=PADDLE_USE_ANGLE_CLS)
            except TypeError:
                return engine.ocr(path)
        raise RuntimeError("PaddleOCR engine has no predict() or ocr() method.")

    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="paddle-ocr") as executor:
        future = executor.submit(_call)
        return future.result(timeout=timeout)


def _failed_candidate(error: str) -> dict[str, Any]:
    return {
        "status": "failed",
        "engine": "paddle",
        "psm": "paddle",
        "text": "",
        "confidence": 0,
        "qualityScore": 0,
        "error": error,
    }
