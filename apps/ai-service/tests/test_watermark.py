"""Tests for preventive watermark minting (steganography + store integration)."""

from __future__ import annotations

from examshield_ai.settings import Settings
from examshield_ai.store import EvidenceStore
from examshield_ai.watermark import (
    build_token,
    decode_watermark,
    embed,
    parse_token,
    strip_watermark,
)

PAPER_TEXT = (
    "NEET 2026 Paper A\n"
    "Section 1: Physics\n"
    "1. A body falls freely under gravity.\n"
    "2. Derive the lens formula relating object and image distance.\n"
)


def _offline_settings(tmp_path) -> Settings:
    return Settings(
        host="127.0.0.1",
        port=8790,
        repo_root=tmp_path,
        upload_root=tmp_path / "uploads",
        registry_path=tmp_path / "papers.json",
        copies_path=tmp_path / "watermark_copies.json",
        api_key="",
        model="test-model",
        fallback_models=(),
        planner_model="test-model",
        base_url="https://example.com/v1",
        planner_timeout_seconds=5.0,
        stream_timeout_seconds=20.0,
        chat_max_tokens=220,
        planner_max_tokens=120,
        list_cache_ttl_seconds=8.0,
        read_cache_ttl_seconds=5.0,
        cache_control_max_age=5,
        supabase_timeout_seconds=20.0,
        detect_threshold=7.0,
        cors_origin="*",
        max_upload_bytes=12 * 1024 * 1024,
        supabase_url="",
        supabase_service_role_key="",
        supabase_document_table="examshield_documents",
        supabase_storage_bucket="evidence-files",
        public_url="https://example.com",
        telegram_bot_token="",
        telegram_webhook_secret="",
        telegram_chat_id="",
        telegram_admin_chat_id="",
        master_key="",
    )


def test_build_token_shape_and_checksum():
    token = build_token("CPY-0001", "NEET2026A", "CENTER-KOL-12")
    parsed = parse_token(token)
    assert parsed is not None
    assert parsed["copyId"] == "CPY-0001"
    assert parsed["paperId"] == "NEET2026A"
    assert parsed["recipientRef"] == "CENTER-KOL-12"


def test_tampered_token_is_rejected():
    token = build_token("CPY-0001", "NEET2026A", "CENTER-KOL-12")
    body, _checksum = token.rsplit("|", 1)
    tampered = body + "|deadbeef"  # wrong checksum
    assert parse_token(tampered) is None


def test_embed_is_invisible_and_round_trips():
    token = build_token("CPY-0001", "NEET2026A", "CENTER-KOL-12")
    watermarked = embed(PAPER_TEXT, token)
    # Visible text is unchanged after stripping the watermark.
    assert strip_watermark(watermarked) == PAPER_TEXT
    # The watermark decodes back to the exact token.
    assert decode_watermark(watermarked) == [token]


def test_embed_survives_reflow_and_appended_chatter():
    token = build_token("CPY-0002", "JEE2026B", "CENTER-DEL-07")
    watermarked = embed(PAPER_TEXT, token)
    # Simulate a leak forwarded through Telegram: newlines collapsed to spaces
    # and a caption appended.
    leaked = watermarked.replace("\n", " ") + "\nSHARED ON TELEGRAM by anon — revoke now!"
    decoded = decode_watermark(leaked)
    assert decoded == [token]


def test_embed_survives_partial_leak_single_paragraph():
    token = build_token("CPY-0003", "UPSC2026", "CENTER-MUM-21")
    first_para = PAPER_TEXT.split("\n", 1)[0]
    watermarked = embed(first_para, token)
    assert decode_watermark(watermarked) == [token]


def test_mint_copies_then_extract_traces_recipient(tmp_path):
    store = EvidenceStore(_offline_settings(tmp_path))
    store.add_registry_paper({"paperId": "NEET2026A", "exam": "NEET", "year": 2026, "paperSet": "A"})

    recipients = [
        {"ref": "CENTER-KOL-12"},
        {"ref": "CENTER-DEL-07", "issuedTo": "student@example.com"},
    ]
    copies = store.mint_copies("NEET2026A", recipients, PAPER_TEXT)
    assert len(copies) == 2
    assert [c["recipientRef"] for c in copies] == ["CENTER-KOL-12", "CENTER-DEL-07"]
    assert all(c["watermarkedText"] for c in copies)

    # A leak of the first copy (reflowed) must attribute to that exact recipient.
    leaked = copies[0]["watermarkedText"].replace("\n", " ")
    result = store.extract_watermark(leaked)
    assert result["status"] == "detected"
    assert result["recipientRef"] == "CENTER-KOL-12"
    assert result["paperId"] == "NEET2026A"

    # Copy records persisted and queryable.
    assert store.find_copy_by_watermark("CPY-0001")["recipientRef"] == "CENTER-KOL-12"
    assert len(store.read_copies()) == 2


def test_mint_rejects_unknown_paper(tmp_path):
    store = EvidenceStore(_offline_settings(tmp_path))
    try:
        store.mint_copies("NOPE", [{"ref": "X"}], PAPER_TEXT)
        assert False, "expected LookupError"
    except LookupError:
        pass


def test_extract_watermark_legacy_papers_unaffected(tmp_path):
    store = EvidenceStore(_offline_settings(tmp_path))
    # Plain text with no watermark must stay "not-detected" (no false positives).
    result = store.extract_watermark("This is a clean exam paper with no watermark.")
    assert result["status"] == "not-detected"
