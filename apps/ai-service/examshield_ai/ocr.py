from __future__ import annotations

import logging
import os
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

TESSERACT_CMD = os.environ.get("TESSERACT_CMD", "tesseract")
SUPPORTED_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
}


def _split_csv(value: str, default: str) -> tuple[str, ...]:
    raw = (value or default).strip()
    return tuple(item.strip() for item in raw.split(",") if item.strip())


def _env_bool(name: str, default: str = "1") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


OCR_PSMS = _split_csv(os.environ.get("EXAMSHIELD_OCR_PSMS", ""), "6,4")
OCR_TIMEOUT_SECONDS = int(os.environ.get("EXAMSHIELD_OCR_TIMEOUT", "25"))
OCR_TOTAL_BUDGET_SECONDS = int(os.environ.get("EXAMSHIELD_OCR_TOTAL_BUDGET_SECONDS", "75"))
OCR_MAX_RETRIES = int(os.environ.get("EXAMSHIELD_OCR_MAX_RETRIES", "0"))
OCR_PSM_WORKERS = int(os.environ.get("EXAMSHIELD_OCR_PSM_WORKERS", str(len(OCR_PSMS))))
OCR_MODE = os.environ.get("EXAMSHIELD_OCR_MODE", "sequential").strip().lower()
OCR_MIN_QUALITY = int(os.environ.get("EXAMSHIELD_OCR_MIN_QUALITY", "25"))
OCR_FAST = _env_bool("EXAMSHIELD_OCR_FAST", "1")


def analyze_image(image_bytes: bytes, suffix: str) -> dict[str, Any]:
    started = time.perf_counter()
    deadline = started + OCR_TOTAL_BUDGET_SECONDS
    temp_path = write_temp_image(image_bytes, suffix)

    try:
        for attempt in range(OCR_MAX_RETRIES + 1):
            if time.perf_counter() >= deadline:
                logger.warning("OCR budget exhausted before attempt %s", attempt + 1)
                break

            candidates = read_ocr_candidates(temp_path, deadline=deadline)
            failed = [candidate for candidate in candidates if candidate["status"] == "failed"]
            passed = [candidate for candidate in candidates if candidate["status"] == "completed"]

            if passed:
                best = max(passed, key=lambda candidate: candidate["qualityScore"])
                raw_text = str(best["text"])
                confidence = int(best["confidence"])

                logger.info(
                    "OCR attempt %s succeeded with PSM %s in %sms",
                    attempt + 1,
                    best["psm"],
                    elapsed_ms(started),
                )
                return {
                    "status": "completed",
                    "confidence": confidence if raw_text else 0,
                    "text": raw_text,
                    "processingTimeMs": elapsed_ms(started),
                    "message": "Text extracted" if raw_text else "No Exam Content Detected",
                    "qualityScore": int(best["qualityScore"]),
                }

            if attempt < OCR_MAX_RETRIES:
                logger.warning(
                    "OCR attempt %s failed, retrying... Errors: %s",
                    attempt + 1,
                    [item.get("error") for item in failed],
                )

        error = failed[0].get("error") if failed else f"OCR exceeded {OCR_TOTAL_BUDGET_SECONDS}s budget."
        logger.error("OCR failed after %s attempts: %s", OCR_MAX_RETRIES + 1, error)
        return failed_result(str(error), started)
    except FileNotFoundError:
        return failed_result("Tesseract executable was not found.", started)
    except subprocess.TimeoutExpired:
        return failed_result("OCR timed out.", started)
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass


def write_temp_image(image_bytes: bytes, suffix: str) -> Path:
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        temp_file.write(image_bytes)
        return Path(temp_file.name)
    finally:
        temp_file.close()


def remaining_timeout(deadline: float | None, fallback: int = OCR_TIMEOUT_SECONDS) -> int:
    if deadline is None:
        return fallback
    remaining = deadline - time.perf_counter()
    if remaining <= 0:
        return 1
    return max(1, min(fallback, int(remaining)))


def run_tesseract(
    image_path: Path,
    args: list[str],
    *,
    timeout: int | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [TESSERACT_CMD, str(image_path), *args],
        capture_output=True,
        text=True,
        timeout=timeout or OCR_TIMEOUT_SECONDS,
    )


def read_ocr_candidates(image_path: Path, *, deadline: float | None = None) -> list[dict[str, Any]]:
    if OCR_MODE == "parallel":
        return read_ocr_candidates_parallel(image_path, deadline=deadline)
    return read_ocr_candidates_sequential(image_path, deadline=deadline)


def read_ocr_candidates_sequential(
    image_path: Path,
    *,
    deadline: float | None = None,
) -> list[dict[str, Any]]:
    """Try PSM modes fastest-first and stop once quality is acceptable."""
    candidates: list[dict[str, Any]] = []
    for psm in OCR_PSMS:
        if deadline and time.perf_counter() >= deadline:
            candidates.append({
                "status": "failed",
                "psm": psm,
                "text": "",
                "confidence": 0,
                "qualityScore": 0,
                "error": f"OCR budget exceeded ({OCR_TOTAL_BUDGET_SECONDS}s)",
            })
            break

        timeout = remaining_timeout(deadline)
        try:
            candidate = read_ocr_candidate(image_path, psm, timeout=timeout)
        except subprocess.TimeoutExpired:
            candidate = {
                "status": "failed",
                "psm": psm,
                "text": "",
                "confidence": 0,
                "qualityScore": 0,
                "error": f"PSM {psm} timed out after {timeout}s",
            }
        except Exception as exc:
            candidate = {
                "status": "failed",
                "psm": psm,
                "text": "",
                "confidence": 0,
                "qualityScore": 0,
                "error": f"PSM {psm} error: {exc}",
            }

        candidates.append(candidate)
        if (
            candidate.get("status") == "completed"
            and candidate.get("text")
            and int(candidate.get("qualityScore") or 0) >= OCR_MIN_QUALITY
        ):
            return candidates
    return candidates


def read_ocr_candidates_parallel(
    image_path: Path,
    *,
    deadline: float | None = None,
) -> list[dict[str, Any]]:
    """Run all configured PSM modes concurrently and return every candidate."""
    workers = max(1, min(OCR_PSM_WORKERS, len(OCR_PSMS)))
    candidates: list[dict[str, Any]] = []
    timeout = remaining_timeout(deadline)

    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="ocr-psm") as executor:
        futures = {
            executor.submit(read_ocr_candidate, image_path, psm, timeout=timeout): psm
            for psm in OCR_PSMS
        }
        for future in as_completed(futures):
            psm = futures[future]
            try:
                candidates.append(future.result())
            except subprocess.TimeoutExpired:
                candidates.append({
                    "status": "failed",
                    "psm": psm,
                    "text": "",
                    "confidence": 0,
                    "qualityScore": 0,
                    "error": f"PSM {psm} timed out after {timeout}s",
                })
            except Exception as exc:
                candidates.append({
                    "status": "failed",
                    "psm": psm,
                    "text": "",
                    "confidence": 0,
                    "qualityScore": 0,
                    "error": f"PSM {psm} error: {exc}",
                })
    return candidates


def read_ocr_candidate(
    image_path: Path,
    psm: str,
    *,
    timeout: int | None = None,
) -> dict[str, Any]:
    call_timeout = timeout or OCR_TIMEOUT_SECONDS
    text_run = run_tesseract(
        image_path,
        ["stdout", "-l", "eng", "--oem", "1", "--psm", psm],
        timeout=call_timeout,
    )
    if text_run.returncode != 0:
        return {
            "status": "failed",
            "psm": psm,
            "text": "",
            "confidence": 0,
            "qualityScore": 0,
            "error": text_run.stderr.strip(),
        }

    raw_text = normalize_text(text_run.stdout)
    if not raw_text:
        return {
            "status": "completed",
            "psm": psm,
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
    if OCR_FAST:
        confidence = estimate_confidence_from_text(raw_text, words)
        quality_report = score_ocr_quality(raw_text, confidence, words)
        return {
            "status": "completed",
            "psm": psm,
            "text": raw_text,
            "confidence": confidence,
            **quality_report,
        }

    word_confidences, tsv_words = read_word_confidences(image_path, psm, timeout=call_timeout)
    merged_words = tsv_words or words
    confidence = round(sum(word_confidences) / len(word_confidences)) if word_confidences else estimate_confidence_from_text(raw_text, merged_words)
    quality_report = score_ocr_quality(raw_text, confidence, merged_words)

    return {
        "status": "completed",
        "psm": psm,
        "text": raw_text,
        "confidence": confidence,
        **quality_report,
    }


def estimate_confidence_from_text(raw_text: str, words: list[str]) -> int:
    if not raw_text:
        return 0
    provisional = score_ocr_quality(raw_text, 70, words)
    return max(30, min(92, int(provisional["qualityScore"])))


def read_word_confidences(
    image_path: Path,
    psm: str,
    *,
    timeout: int | None = None,
) -> tuple[list[float], list[str]]:
    tsv_run = run_tesseract(
        image_path,
        ["stdout", "-l", "eng", "--oem", "1", "--psm", psm, "tsv"],
        timeout=timeout or OCR_TIMEOUT_SECONDS,
    )
    if tsv_run.returncode != 0:
        return [], []

    values: list[float] = []
    words: list[str] = []
    lines = [line for line in tsv_run.stdout.splitlines() if line.strip()]
    if not lines:
        return values, words

    headers = lines[0].split("\t")
    try:
        conf_index = headers.index("conf")
        text_index = headers.index("text")
    except ValueError:
        return values, words

    for line in lines[1:]:
        columns = line.split("\t")
        if conf_index >= len(columns):
            continue
        word = columns[text_index].strip() if text_index < len(columns) else ""
        try:
            value = float(columns[conf_index])
        except ValueError:
            continue
        if value >= 0 and word:
            values.append(value)
            words.append(word)

    return values, words


def score_ocr_quality(text: str, confidence: int, words: list[str]) -> dict[str, Any]:
    normalized_words = [normalize_token(word) for word in words]
    meaningful_words = [
        word
        for word in normalized_words
        if len(word) >= 3 and has_vowel(word) and not is_keyboard_noise(word)
    ]
    lines = [line for line in text.splitlines() if line.strip()]
    printable_chars = [char for char in text if not char.isspace()]
    clean_chars = [char for char in printable_chars if char.isalnum() or char in ".,:;!?()[]+-/%'\""]
    clean_ratio = len(clean_chars) / len(printable_chars) if printable_chars else 0
    alpha_count = sum(1 for char in text if char.isalpha())
    punctuation_count = sum(1 for char in printable_chars if not char.isalnum())
    punctuation_ratio = punctuation_count / len(printable_chars) if printable_chars else 0
    short_line_ratio = sum(1 for line in lines if len(line.strip()) <= 4) / len(lines) if lines else 1
    word_count = len([word for word in normalized_words if word])
    meaningful_ratio = len(meaningful_words) / word_count if word_count else 0
    language_score = min(100, meaningful_ratio * 100)
    structure_score = min(100, len(lines) * 12 + word_count * 4)
    cleanliness_score = max(0, min(100, clean_ratio * 100 - punctuation_ratio * 45))
    penalties = 0

    if short_line_ratio > 0.55:
        penalties += 18
    if alpha_count < 12:
        penalties += 25
    if word_count < 4:
        penalties += 22
    if confidence < 35:
        penalties += 18

    quality_score = round(
        confidence * 0.44
        + language_score * 0.26
        + structure_score * 0.18
        + cleanliness_score * 0.12
        - penalties
    )
    return {
        "qualityScore": max(0, min(100, quality_score)),
        "quality": {
            "wordCount": word_count,
            "meaningfulWordCount": len(meaningful_words),
            "cleanRatio": round(clean_ratio, 2),
            "punctuationRatio": round(punctuation_ratio, 2),
            "shortLineRatio": round(short_line_ratio, 2),
        },
    }


def normalize_token(value: str) -> str:
    return "".join(char for char in value.lower() if char.isalnum())


def has_vowel(value: str) -> bool:
    return any(char in "aeiou" for char in value)


def is_keyboard_noise(value: str) -> bool:
    if len(value) <= 2:
        return True
    unique = len(set(value))
    if unique <= 2 and len(value) >= 4:
        return True
    consonants = set("bcdfghjklmnpqrstvwxyz")
    return len(value) >= 4 and all(char in consonants for char in value.lower())


def normalize_text(value: str) -> str:
    lines = [" ".join(line.strip().split()) for line in value.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def failed_result(error: str, started: float) -> dict[str, Any]:
    return {
        "status": "failed",
        "confidence": 0,
        "text": "",
        "processingTimeMs": elapsed_ms(started),
        "error": error or "OCR failed.",
    }


def elapsed_ms(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)
