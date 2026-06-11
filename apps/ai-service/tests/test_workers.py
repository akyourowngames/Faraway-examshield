from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from examshield_ai.store import EvidenceStore
from examshield_ai.workers import AnalysisTask, AnalysisWorkerPool

from tests.conftest import make_image_upload


def _mock_ocr_runner(_data: bytes, _suffix: str) -> dict:
    return {
        "status": "completed",
        "text": "sample ocr",
        "confidence": 88,
        "processingTimeMs": 12,
    }


class TestAnalysisWorkerPool:
    def test_submit_runs_job_and_updates_stats(self, store: EvidenceStore, workers: AnalysisWorkerPool):
        created = store.create_evidence(make_image_upload())
        queued = store.create_analysis_job(created["evidence"]["evidenceId"])
        job_id = queued["job"]["jobId"]
        evidence_id = created["evidence"]["evidenceId"]

        future = workers.submit(
            store,
            AnalysisTask(job_id=job_id, evidence_id=evidence_id),
            _mock_ocr_runner,
        )
        assert future is not None
        result = future.result(timeout=5)
        assert result["message"] == "Analysis Complete"

        stats = workers.stats()
        assert stats["submitted"] == 1
        assert stats["completed"] == 1
        assert stats["activeJobs"] == 0

    def test_submit_rejects_duplicate_evidence(self, store: EvidenceStore, workers: AnalysisWorkerPool):
        created = store.create_evidence(make_image_upload("dup.jpg"))
        evidence_id = created["evidence"]["evidenceId"]
        first = store.create_analysis_job(evidence_id)
        second = store.create_analysis_job(evidence_id)

        fut1 = workers.submit(
            store,
            AnalysisTask(job_id=first["job"]["jobId"], evidence_id=evidence_id),
            lambda *_: {"status": "completed", "text": "x", "confidence": 1, "processingTimeMs": 1},
        )
        fut2 = workers.submit(
            store,
            AnalysisTask(job_id=second["job"]["jobId"], evidence_id=evidence_id),
            _mock_ocr_runner,
        )

        assert fut1 is not None
        assert fut2 is None

    def test_on_complete_called(self, store: EvidenceStore):
        pool = AnalysisWorkerPool(max_workers=1)
        created = store.create_evidence(make_image_upload("cb.jpg"))
        queued = store.create_analysis_job(created["evidence"]["evidenceId"])
        callback = MagicMock()

        pool.submit(
            store,
            AnalysisTask(
                job_id=queued["job"]["jobId"],
                evidence_id=created["evidence"]["evidenceId"],
            ),
            _mock_ocr_runner,
            on_complete=callback,
        )
        time.sleep(0.5)
        pool.shutdown(wait=True)

        assert callback.called
        analysis, error = callback.call_args[0]
        assert error is None
        assert analysis["message"] == "Analysis Complete"
