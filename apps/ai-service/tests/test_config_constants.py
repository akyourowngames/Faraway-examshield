"""Tests for audit §6.1 — named config constants in ocr.py / detect.py.

Verifies the previously-scattered magic numbers are now single named constants with
documented defaults, that OCR behavior still respects them, and that the remaining
audit-named tunables (detect_threshold, port, chat tokens, max_upload_bytes) are
read from environment via settings.py.
"""
from __future__ import annotations

import pytest

from examshield_ai import detect, ocr
from examshield_ai.settings import load_settings


# ── ocr.py named constants keep their documented defaults ──
def test_ocr_adaptive_threshold_constants():
    assert ocr.OCR_ADAPTIVE_BLOCK_SIZE == 11
    assert ocr.OCR_ADAPTIVE_C == 10


def test_ocr_deskew_constants():
    assert ocr.OCR_DESKEW_MIN_COORDS == 25
    assert ocr.OCR_DESKEW_ANGLE_FLOOR == 0.5
    assert ocr.OCR_DESKEW_ANGLE_CEIL == 15.0


def test_ocr_quality_clamp_constants():
    assert ocr.OCR_QUALITY_CLAMP_MIN == 30
    assert ocr.OCR_QUALITY_CLAMP_MAX == 92


def test_ocr_quality_length_penalty_constants():
    assert ocr.OCR_QUALITY_MIN_WORD_LEN == 3
    assert ocr.OCR_QUALITY_KEYBOARD_PENALTY == 25
    assert ocr.OCR_QUALITY_MIN_UNIQUE_CHARS == 2
    assert ocr.OCR_QUALITY_MIN_TOKEN_LEN == 4
    assert ocr.OCR_QUALITY_SHORT_LINE_MAX_LEN == 4


# ── detect.py named constants keep their documented defaults ──
def test_detect_pattern_weight_constants():
    assert detect.DETECTION_PATTERN_WEIGHT == 7
    assert detect.TELEGRAM_MESSAGE_WEIGHT == 7
    assert detect.GENERIC_MESSAGE_WEIGHT == 8


def test_detect_url_prefix_constants():
    assert detect.DETECTION_HTTP_PREFIX_LEN == 7
    assert detect.DETECTION_HTTPS_PREFIX_LEN == 8


# ── OCR quality scoring respects the named length/penalty constants ──
def test_score_ocr_quality_respects_min_word_len(monkeypatch):
    text = "NEET 2026 question paper section A answer all questions"
    words = text.split()
    monkeypatch.setattr(ocr, "OCR_QUALITY_MIN_WORD_LEN", 10)
    low = ocr.score_ocr_quality(text, 80, words)["qualityScore"]
    monkeypatch.setattr(ocr, "OCR_QUALITY_MIN_WORD_LEN", 3)
    high = ocr.score_ocr_quality(text, 80, words)["qualityScore"]
    assert low < high


def test_score_ocr_quality_respects_keyboard_penalty(monkeypatch):
    # The penalty only fires when there are fewer than 12 alphabetic chars; use a
    # text that triggers it so the constant actually changes the score.
    words = ["NEET", "2026", "paper"]
    monkeypatch.setattr(ocr, "OCR_QUALITY_KEYBOARD_PENALTY", 0)
    no_penalty = ocr.score_ocr_quality("NEET 2026 paper", 80, words)["qualityScore"]
    monkeypatch.setattr(ocr, "OCR_QUALITY_KEYBOARD_PENALTY", 40)
    big_penalty = ocr.score_ocr_quality("NEET 2026 paper", 80, words)["qualityScore"]
    assert big_penalty < no_penalty


def test_estimate_confidence_from_text_respects_clamp_max(monkeypatch):
    words = ["NEET", "2026", "question", "paper", "section"]
    monkeypatch.setattr(ocr, "OCR_QUALITY_CLAMP_MAX", 50)
    assert ocr.estimate_confidence_from_text("NEET 2026 question paper section", words) <= 50
    monkeypatch.setattr(ocr, "OCR_QUALITY_CLAMP_MAX", 92)
    assert ocr.estimate_confidence_from_text("NEET 2026 question paper section", words) <= 92


def test_is_keyboard_noise_respects_min_token_len(monkeypatch):
    # "bcdf" is all consonants; raising the min token length flips it from noise to valid.
    monkeypatch.setattr(ocr, "OCR_QUALITY_MIN_TOKEN_LEN", 4)
    assert ocr.is_keyboard_noise("bcdf") is True
    monkeypatch.setattr(ocr, "OCR_QUALITY_MIN_TOKEN_LEN", 6)
    assert ocr.is_keyboard_noise("bcdf") is False


# ── preprocess actually threads the adaptive block size / C constant through ──
def test_preprocess_passes_adaptive_constants(monkeypatch):
    cv2 = pytest.importorskip("cv2")
    import numpy as np

    captured = {}
    monkeypatch.setattr(ocr, "OCR_ADAPTIVE_BLOCK_SIZE", 13)
    monkeypatch.setattr(ocr, "OCR_ADAPTIVE_C", 9)

    def fake_adaptive(*args, **kwargs):
        captured["blockSize"] = args[4] if len(args) > 4 else kwargs.get("blockSize")
        captured["C"] = args[5] if len(args) > 5 else kwargs.get("C")
        return args[0]

    monkeypatch.setattr(cv2, "adaptiveThreshold", fake_adaptive)
    frame = np.full((200, 400, 3), 255, dtype=np.uint8)
    ocr._preprocess_for_ocr(frame)
    assert captured.get("blockSize") == 13
    assert captured.get("C") == 9


# ── already-centralized settings tunables still come from the environment ──
def test_settings_read_tunables_from_env(monkeypatch):
    # detect_threshold / severity 25|15|7, chat tokens, max_upload_bytes, port are
    # wired through settings.py env vars (audit §6.1 named these specifically).
    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.setenv("EXAMSHIELD_DETECT_THRESHOLD", "3")
    monkeypatch.setenv("EXAMSHIELD_AI_PORT", "9001")
    monkeypatch.setenv("EXAMSHIELD_AI_CHAT_MAX_TOKENS", "512")
    monkeypatch.setenv("EXAMSHIELD_MAX_UPLOAD_BYTES", "1048576")
    settings = load_settings()
    assert settings.detect_threshold == 3.0
    assert settings.port == 9001
    assert settings.chat_max_tokens == 512
    assert settings.max_upload_bytes == 1048576
