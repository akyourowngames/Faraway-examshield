from __future__ import annotations

import threading
import time
from collections.abc import Callable
from concurrent.futures import Future
from unittest.mock import MagicMock

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


def _make_blocking_runner(gate: threading.Event) -> Callable[[bytes, str], dict]:
    def _runner(_data: bytes, _suffix: str) -> dict:
        assert gate.wait(timeout=5), "blocking OCR runner was not released in time"
        return {
            "status": "completed",
            "text": "blocked ocr",
            "confidence": 88,
            "processingTimeMs": 1,
        }

    return _runner


class TestWorkerPoolSaturation:
    def test_load_sheds_when_outstanding_reaches_cap(self, store: EvidenceStore):
        # cap = max_workers(1) + max_pending(0) = 1 outstanding job allowed.
        pool = AnalysisWorkerPool(max_workers=1, max_pending=0)
        gate = threading.Event()

        ev1 = store.create_evidence(make_image_upload("sat1.jpg"))
        j1 = store.create_analysis_job(ev1["evidence"]["evidenceId"])
        fut1 = pool.submit(
            store,
            AnalysisTask(job_id=j1["job"]["jobId"], evidence_id=ev1["evidence"]["evidenceId"]),
            _make_blocking_runner(gate),
        )
        assert fut1 is not None

        # Second job should be load-shed (pool already at cap, no queue room).
        ev2 = store.create_evidence(make_image_upload("sat2.jpg"))
        j2 = store.create_analysis_job(ev2["evidence"]["evidenceId"])
        fut2 = pool.submit(
            store,
            AnalysisTask(job_id=j2["job"]["jobId"], evidence_id=ev2["evidence"]["evidenceId"]),
            _make_blocking_runner(gate),
        )
        assert fut2 is None

        gate.set()
        assert fut1.result(timeout=5)["message"] == "Analysis Complete"
        pool.shutdown(wait=True)

    def test_allows_queued_jobs_up_to_max_pending(self, store: EvidenceStore):
        # cap = max_workers(1) + max_pending(1) = 2 outstanding jobs allowed.
        pool = AnalysisWorkerPool(max_workers=1, max_pending=1)
        gate = threading.Event()

        def _submit() -> Future[dict] | None:
            ev = store.create_evidence(make_image_upload())
            job = store.create_analysis_job(ev["evidence"]["evidenceId"])
            return pool.submit(
                store,
                AnalysisTask(job_id=job["job"]["jobId"], evidence_id=ev["evidence"]["evidenceId"]),
                _make_blocking_runner(gate),
            )

        fut1 = _submit()
        fut2 = _submit()
        fut3 = _submit()  # beyond cap -> shed
        assert fut1 is not None
        assert fut2 is not None
        assert fut3 is None
        assert pool.stats()["outstanding"] == 2

        gate.set()
        assert fut1.result(timeout=5)["message"] == "Analysis Complete"
        assert fut2.result(timeout=5)["message"] == "Analysis Complete"
        pool.shutdown(wait=True)

    def test_stats_reports_pending_config(self):
        pool = AnalysisWorkerPool(max_workers=3, max_pending=7)
        stats = pool.stats()
        assert stats["maxWorkers"] == 3
        assert stats["maxPending"] == 7
        assert stats["outstanding"] == 0
        pool.shutdown(wait=True)
