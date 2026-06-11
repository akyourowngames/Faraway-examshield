from __future__ import annotations

import logging
import os
import threading
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass, field
from typing import Any, Callable

from .store import EvidenceStore, JsonObject

logger = logging.getLogger(__name__)

OcrRunner = Callable[[bytes, str], JsonObject]
OnComplete = Callable[[JsonObject, Exception | None], None]

DEFAULT_MAX_WORKERS = int(os.environ.get("EXAMSHIELD_OCR_WORKERS", "2"))
ANALYSIS_JOB_TIMEOUT_SECONDS = int(os.environ.get("EXAMSHIELD_ANALYSIS_JOB_TIMEOUT_SECONDS", "120"))


@dataclass
class AnalysisTask:
    job_id: str
    evidence_id: str
    context: JsonObject = field(default_factory=dict)


class AnalysisWorkerPool:
    """Bounded thread pool that runs OCR analysis jobs in parallel.

    Telegram webhooks and REST ingestion both submit jobs here so OCR work
    never blocks HTTP responses and duplicate jobs are rejected.
    """

    def __init__(self, max_workers: int = DEFAULT_MAX_WORKERS) -> None:
        self._max_workers = max(1, max_workers)
        self._executor = ThreadPoolExecutor(
            max_workers=self._max_workers,
            thread_name_prefix="examshield-ocr",
        )
        self._lock = threading.Lock()
        self._active_jobs: set[str] = set()
        self._active_evidence: set[str] = set()
        self._submitted = 0
        self._completed = 0
        self._failed = 0

    @property
    def max_workers(self) -> int:
        return self._max_workers

    def stats(self) -> JsonObject:
        with self._lock:
            return {
                "maxWorkers": self._max_workers,
                "activeJobs": len(self._active_jobs),
                "activeEvidence": len(self._active_evidence),
                "submitted": self._submitted,
                "completed": self._completed,
                "failed": self._failed,
            }

    def is_job_active(self, job_id: str) -> bool:
        with self._lock:
            return job_id in self._active_jobs

    def is_evidence_active(self, evidence_id: str) -> bool:
        with self._lock:
            return evidence_id in self._active_evidence

    def submit(
        self,
        store: EvidenceStore,
        task: AnalysisTask,
        ocr_runner: OcrRunner,
        on_complete: OnComplete | None = None,
    ) -> Future[JsonObject] | None:
        """Queue an OCR analysis job. Returns None if already queued/running."""
        with self._lock:
            if task.job_id in self._active_jobs or task.evidence_id in self._active_evidence:
                logger.info(
                    "Skipping duplicate OCR submission for evidence %s job %s",
                    task.evidence_id,
                    task.job_id,
                )
                return None
            self._active_jobs.add(task.job_id)
            self._active_evidence.add(task.evidence_id)
            self._submitted += 1

        def _run() -> JsonObject:
            try:
                logger.info(
                    "Worker starting OCR for evidence %s job %s",
                    task.evidence_id,
                    task.job_id,
                )
                with ThreadPoolExecutor(max_workers=1, thread_name_prefix="analysis-job") as runner:
                    future = runner.submit(store.run_analysis_job, task.job_id, ocr_runner)
                    try:
                        result = future.result(timeout=ANALYSIS_JOB_TIMEOUT_SECONDS)
                    except FuturesTimeoutError as exc:
                        message = f"Analysis timed out after {ANALYSIS_JOB_TIMEOUT_SECONDS}s"
                        logger.error(
                            "Worker OCR timed out for evidence %s job %s",
                            task.evidence_id,
                            task.job_id,
                        )
                        try:
                            store.fail_analysis_job(task.job_id, message)
                        except Exception as fail_exc:
                            logger.error("Failed to mark timed-out job %s failed: %s", task.job_id, fail_exc)
                        raise RuntimeError(message) from exc

                if result.get("message") == "Analysis Failed":
                    raise RuntimeError(
                        str(result.get("job", {}).get("error") or "Analysis failed.")
                    )
                return result
            except Exception as exc:
                logger.error(
                    "Worker OCR failed for evidence %s job %s: %s",
                    task.evidence_id,
                    task.job_id,
                    exc,
                )
                with self._lock:
                    self._failed += 1
                if on_complete:
                    on_complete({}, exc)
                raise
            finally:
                with self._lock:
                    self._active_jobs.discard(task.job_id)
                    self._active_evidence.discard(task.evidence_id)

        future = self._executor.submit(_run)

        def _done(fut: Future[JsonObject]) -> None:
            with self._lock:
                self._completed += 1
            if not on_complete:
                return
            try:
                on_complete(fut.result(), None)
            except Exception as exc:
                on_complete({}, exc)

        future.add_done_callback(_done)
        return future

    def shutdown(self, wait: bool = True) -> None:
        self._executor.shutdown(wait=wait, cancel_futures=False)
