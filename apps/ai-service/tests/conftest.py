from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from examshield_ai.pipeline import EvidencePipeline
from examshield_ai.settings import Settings
from examshield_ai.store import EvidenceStore, UploadedFile
from examshield_ai.telegram import TelegramWebhook
from examshield_ai.workers import AnalysisWorkerPool


@pytest.fixture
def tmp_settings(tmp_path: Path) -> Settings:
    upload_root = tmp_path / "uploads"
    registry_path = tmp_path / "papers.json"
    return Settings(
        host="127.0.0.1",
        port=8790,
        repo_root=tmp_path,
        upload_root=upload_root,
        registry_path=registry_path,
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
        supabase_timeout_seconds=20.0,
        detect_threshold=7.0,
        cors_origin="*",
        max_upload_bytes=12 * 1024 * 1024,
        supabase_url="",
        supabase_service_role_key="",
        supabase_document_table="examshield_documents",
        supabase_storage_bucket="evidence-files",
        public_url="https://example.com",
        telegram_bot_token="test-token",
        telegram_webhook_secret="secret",
        telegram_chat_id="-100123",
        telegram_admin_chat_id="-100999",
    )


@pytest.fixture
def store(tmp_settings: Settings) -> EvidenceStore:
    evidence_store = EvidenceStore(tmp_settings)
    evidence_store.ensure_storage()
    evidence_store.add_monitored_group("-100123", name="Primary")
    return evidence_store


@pytest.fixture
def workers() -> AnalysisWorkerPool:
    pool = AnalysisWorkerPool(max_workers=2)
    yield pool
    pool.shutdown(wait=True)


@pytest.fixture
def telegram(tmp_settings: Settings) -> TelegramWebhook:
    return TelegramWebhook(tmp_settings)


@pytest.fixture
def pipeline(store: EvidenceStore, telegram: TelegramWebhook, workers: AnalysisWorkerPool) -> EvidencePipeline:
    return EvidencePipeline(store, telegram, workers)


def make_image_upload(name: str = "leak.jpg") -> UploadedFile:
    # Minimal valid JPEG header bytes for storage tests
    data = bytes([0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01])
    return UploadedFile(filename=name, content_type="image/jpeg", data=data)
