from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from examshield_ai.detect import scan_text
from examshield_ai.telegram import TelegramWebhook, _should_send_alert
from tests.conftest import make_image_upload


def _mock_ocr_runner(_data: bytes, _suffix: str) -> dict:
    return {
        "status": "completed",
        "text": "NEET 2026 question paper WMK-001",
        "confidence": 91,
        "processingTimeMs": 20,
    }


class TestShouldSendAlert:
    def test_investigation_complete_triggers_alert(self):
        analysis = {"forensicReport": {"status": "investigation-complete"}}
        assert _should_send_alert(analysis, {"score": 0})

    def test_suspicious_detection_triggers_alert(self):
        detection = scan_text("leaked neet paper pdf")
        assert _should_send_alert({}, detection)

    def test_benign_content_no_alert(self):
        assert not _should_send_alert({}, scan_text("hello team"))


class TestTelegramWebhook:
    def test_ignores_unmonitored_group(self, telegram: TelegramWebhook, store, pipeline):
        update = {
            "message": {
                "message_id": 1,
                "chat": {"id": "-999"},
                "text": "leaked paper",
                "date": 1_700_000_000,
            }
        }
        result = telegram.process_update(update, store, _mock_ocr_runner, pipeline=pipeline)
        assert result["processed"] is False
        assert result["message"] == "Group not monitored"

    def test_text_only_suspicious_sends_alert(self, telegram: TelegramWebhook, store, pipeline):
        with patch.object(telegram, "_send_alert", return_value={"status": "ok"}) as alert:
            update = {
                "message": {
                    "message_id": 2,
                    "chat": {"id": "-100123"},
                    "text": "leaked neet question paper pdf",
                    "date": 1_700_000_000,
                }
            }
            result = telegram.process_update(update, store, _mock_ocr_runner, pipeline=pipeline)

        assert result["processed"] is True
        assert result["alertSent"] is True
        alert.assert_called_once()

    def test_media_message_queues_async_ocr(self, telegram: TelegramWebhook, store, pipeline, workers):
        with patch.object(telegram, "_download_media", return_value=make_image_upload()), patch.object(
            telegram, "_send_alert", return_value={"status": "ok"}
        ):
            update = {
                "message": {
                    "message_id": 3,
                    "chat": {"id": "-100123"},
                    "caption": "check this",
                    "date": 1_700_000_000,
                    "photo": [{"file_id": "abc", "width": 100, "height": 100}],
                }
            }
            result = telegram.process_update(update, store, _mock_ocr_runner, pipeline=pipeline)

        assert result["processed"] is True
        assert result["job"]["status"] == "queued"
        assert result["message"] == "Telegram evidence queued for analysis"

        deadline = time.time() + 5
        while time.time() < deadline:
            evidence = store.get_evidence_by_id(result["evidence"]["evidenceId"])
            stats = workers.stats()
            if evidence and evidence.get("ocrStatus") == "completed" and stats["completed"] >= 1:
                break
            time.sleep(0.1)
        else:
            pytest.fail("OCR job did not complete in worker pool")

        assert evidence["ocrText"]

    def test_duplicate_webhook_is_idempotent(self, telegram: TelegramWebhook, store, pipeline):
        with patch.object(telegram, "_download_media", return_value=make_image_upload("dup2.jpg")):
            update = {
                "message": {
                    "message_id": 4,
                    "chat": {"id": "-100123"},
                    "date": 1_700_000_000,
                    "photo": [{"file_id": "abc", "width": 100, "height": 100}],
                }
            }
            first = telegram.process_update(update, store, _mock_ocr_runner, pipeline=pipeline)
            second = telegram.process_update(update, store, _mock_ocr_runner, pipeline=pipeline)

        assert first["duplicate"] is False
        assert second["duplicate"] is True

    def test_webhook_secret_validation(self, telegram: TelegramWebhook):
        assert telegram.validate_secret("secret")
        assert not telegram.validate_secret("wrong")


class TestEvidencePipeline:
    def test_queue_media_analysis_cooperates_with_store(self, store, pipeline):
        created = store.create_evidence(make_image_upload("pipe.jpg"), source="telegram")
        detection = scan_text("possible leak")

        job = pipeline.queue_media_analysis(
            created=created,
            detection=detection,
            text="possible leak",
            chat_id="-100123",
            message={"message_id": 9},
            ocr_runner=_mock_ocr_runner,
        )

        assert job is not None
        assert job["status"] == "queued"

        deadline = time.time() + 5
        while time.time() < deadline:
            stored = store.get_evidence_by_id(created["evidence"]["evidenceId"])
            if stored and stored.get("status") == "completed":
                break
            time.sleep(0.1)
        else:
            pytest.fail("Pipeline did not complete OCR job")

        assert stored["ocrText"]
