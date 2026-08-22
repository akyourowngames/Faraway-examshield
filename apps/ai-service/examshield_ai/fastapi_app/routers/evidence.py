"""Evidence, OCR, and threat-memory routes.

Mirrors the stdlib ``do_GET``/``do_POST`` routes, reusing the same cores from
``request.app.state.core``.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from examshield_ai.multipart_parse import parse_multipart
from examshield_ai.normalize import normalize_evidence_id
from examshield_ai.ocr import SUPPORTED_TYPES, analyze_image
from examshield_ai.response_cache import cached_get
from examshield_ai.store import UploadedFile
from examshield_ai.workers import AnalysisTask

from ..deps import (
    backend_secret,
    body_size_guard,
    rate_limit_ocr,
    rate_limit_upload,
    resolve_owner_id,
)
from ..responses import json_response

router = APIRouter()


async def _read_json(request: Request) -> dict:
    try:
        payload = await request.json()
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _core(request: Request):
    return request.app.state.core


def _validate_image_magic(data: bytes, content_type: str) -> str | None:
    if not data:
        return "Empty file payload."
    if content_type == "image/jpeg" and data[:2] != b"\xff\xd8":
        return "Content-Type says JPEG but file does not start with JPEG magic bytes."
    if content_type == "image/png" and data[:8] != b"\x89PNG\r\n\x1a\n":
        return "Content-Type says PNG but file does not start with PNG magic bytes."
    return None


@router.get("/evidence")
async def list_evidence(request: Request, _secret: None = Depends(backend_secret)) -> dict:
    core = _core(request)
    payload = cached_get(core.read_cache, request.url.path, core.store.list_evidence)
    return json_response(payload, request=request, cache=True)


@router.get("/evidence/{evidence_id}")
async def get_evidence(
    evidence_id: str,
    request: Request,
    _secret: None = Depends(backend_secret),
) -> dict:
    core = _core(request)
    bundle = core.store.get_bundle(evidence_id)
    if bundle:
        return json_response(bundle, request=request, cache=True)
    return json_response({"error": "Evidence not found."}, status=404, request=request, cache=True)


@router.get("/alerts")
async def list_alerts(request: Request, _secret: None = Depends(backend_secret)) -> dict:
    core = _core(request)
    payload = cached_get(
        core.read_cache,
        request.url.path,
        lambda: {"alerts": core.store.list_evidence()["alerts"]},
    )
    return json_response(payload, request=request, cache=True)


@router.get("/analysis/jobs/{job_id}")
async def analysis_job_snapshot(
    job_id: str,
    request: Request,
    _secret: None = Depends(backend_secret),
) -> dict:
    core = _core(request)
    try:
        return json_response(core.store.analysis_job_snapshot(job_id), request=request)
    except LookupError:
        return json_response({"error": "Not found."}, status=404, request=request)


@router.post("/ocr/analyze")
async def analyze_ocr(
    request: Request,
    _secret: None = Depends(backend_secret),
    _body: None = Depends(body_size_guard),
    _rate: None = Depends(rate_limit_ocr),
) -> dict:
    core = _core(request)
    content_type = (request.headers.get("Content-Type") or "").split(";")[0].lower()
    suffix = SUPPORTED_TYPES.get(content_type)
    if not suffix:
        return json_response(
            {
                "status": "failed",
                "error": "Only image/jpeg and image/png are supported by the unified OCR endpoint.",
            },
            status=200,
            request=request,
        )

    raw = await request.body()
    if not raw:
        return json_response({"status": "failed", "error": "Image payload is required."}, status=400, request=request)

    max_bytes = core.settings.max_upload_bytes
    if max_bytes > 0 and len(raw) > max_bytes:
        return json_response(
            {"status": "failed", "error": f"Image too large. Maximum is {max_bytes} bytes."},
            status=413,
            request=request,
        )

    magic_err = _validate_image_magic(raw, content_type)
    if magic_err:
        return json_response({"status": "failed", "error": magic_err}, status=400, request=request)

    return json_response(analyze_image(raw, suffix), request=request, cache=False)


@router.post("/analyze")
async def analyze_alias(
    request: Request,
    _secret: None = Depends(backend_secret),
    _body: None = Depends(body_size_guard),
    _rate: None = Depends(rate_limit_ocr),
) -> dict:
    return await analyze_ocr(request)


@router.post("/evidence/upload")
async def upload_evidence(
    request: Request,
    _secret: None = Depends(backend_secret),
    _body: None = Depends(body_size_guard),
    _rate: None = Depends(rate_limit_upload),
) -> dict:
    core = _core(request)
    try:
        raw = await request.body()
        content_type = request.headers.get("Content-Type") or ""
        fields = parse_multipart(raw, content_type)
        uploaded = fields.get("file")
        if not isinstance(uploaded, UploadedFile):
            raise ValueError("Evidence file is required.")
        created = core.store.create_evidence(uploaded, owner_id=resolve_owner_id(request))
        return json_response({"message": "Evidence Created", **created}, status=201, request=request)
    except Exception:
        return json_response({"error": "Evidence upload failed."}, status=400, request=request)


@router.post("/analysis/jobs")
async def create_analysis_job(
    request: Request,
    _secret: None = Depends(backend_secret),
    _body: None = Depends(body_size_guard),
) -> dict:
    core = _core(request)
    payload = await _read_json(request)
    evidence_id = normalize_evidence_id(payload)
    async_mode = bool(payload.get("async"))
    if not evidence_id:
        return json_response({"error": "evidenceId is required."}, status=400, request=request)
    try:
        evidence = core.store.get_evidence_by_id(evidence_id)
        if not evidence:
            raise LookupError("Evidence not found.")
        if evidence.get("fileType") == "text/plain":
            return json_response({"error": "Text-only evidence does not require OCR."}, status=400, request=request)

        existing_job = core.store.get_active_job_for_evidence(evidence_id)
        if existing_job:
            return json_response(
                {"message": "Analysis Already Queued", "evidence": evidence, "job": existing_job},
                request=request,
            )

        queued = core.store.create_analysis_job(evidence_id)
        job = queued["job"]
        if async_mode:
            submitted = core.pipeline.queue_media_analysis(
                created={"evidence": evidence, "activity": [queued["activity"]]},
                detection={"score": 0, "categories": []},
                text=None,
                chat_id=str(evidence.get("telegramChatId") or ""),
                message={},
                ocr_runner=analyze_image,
                job=job,
                owner_id=resolve_owner_id(request),
            )
            if not submitted:
                submitted = job
            return json_response(
                {
                    "message": "Analysis Queued",
                    "evidence": evidence,
                    "job": submitted,
                    "activity": [queued["activity"]],
                    "async": True,
                },
                status=202,
                request=request,
            )

        return json_response(
            {
                "message": "Analysis Queued",
                "evidence": evidence,
                "job": job,
                "activity": [queued["activity"]],
            },
            request=request,
        )
    except LookupError:
        return json_response({"error": "Not found."}, status=404, request=request)
    except Exception:
        return json_response({"error": "Analysis failed."}, status=400, request=request)


@router.post("/analysis/jobs/{job_id}/process")
async def process_analysis_job(
    job_id: str,
    request: Request,
    _secret: None = Depends(backend_secret),
    _body: None = Depends(body_size_guard),
) -> dict:
    core = _core(request)
    try:
        job = core.store.get_analysis_job(job_id)
        if not job:
            return json_response({"error": "Analysis job not found."}, status=404, request=request)
        if job.get("status") in ("completed", "failed"):
            return json_response(core.store.analysis_job_snapshot(job_id), request=request)
        if job.get("status") == "processing" or core.workers.is_job_active(job_id):
            snapshot = core.store.analysis_job_snapshot(job_id)
            snapshot["message"] = "Analysis In Progress"
            return json_response(snapshot, status=202, request=request)

        evidence_id = normalize_evidence_id(job)
        if core.workers.is_evidence_active(evidence_id):
            snapshot = core.store.analysis_job_snapshot(job_id)
            snapshot["message"] = "Analysis In Progress"
            return json_response(snapshot, status=202, request=request)

        owner_id = resolve_owner_id(request)

        def on_complete(_analysis: dict, error: Exception | None) -> None:
            if error:
                try:
                    core.store.fail_analysis_job(job_id, str(error) or "Background OCR failed")
                except Exception:
                    pass
                return
            try:
                core.memory.ingest_from_analysis(_analysis, notify=True, owner_id=owner_id)
            except Exception:
                pass

        core.workers.submit(
            core.store,
            AnalysisTask(job_id=job_id, evidence_id=evidence_id),
            analyze_image,
            on_complete=on_complete,
        )
        snapshot = core.store.analysis_job_snapshot(job_id)
        snapshot["message"] = "Analysis In Progress"
        return json_response(snapshot, status=202, request=request)
    except LookupError:
        return json_response({"error": "Not found."}, status=404, request=request)
    except Exception:
        return json_response({"error": "Analysis failed."}, status=400, request=request)


@router.post("/memory/ingest")
async def memory_ingest(request: Request, _secret: None = Depends(backend_secret)) -> dict:
    core = _core(request)
    try:
        result = core.memory.ingest_manual(await _read_json(request), owner_id=resolve_owner_id(request))
        return json_response(result, status=201, request=request)
    except LookupError:
        return json_response({"error": "Not found."}, status=404, request=request)
    except Exception:
        return json_response({"error": "Memory ingest failed."}, status=400, request=request)


@router.post("/memory/search")
async def memory_search(request: Request, _secret: None = Depends(backend_secret)) -> dict:
    core = _core(request)
    try:
        payload = await _read_json(request)
        query = str(payload.get("query") or payload.get("content") or "").strip()
        if not query:
            return json_response({"error": "query is required."}, status=400, request=request)
        threshold = float(payload.get("threshold") or payload.get("matchThreshold") or 0.76)
        match_count = int(payload.get("matchCount") or payload.get("limit") or 8)
        created_after = (
            str(payload.get("createdAfter") or payload.get("minCreatedAt") or payload.get("since") or "").strip()
            or None
        )
        result = core.memory.search(
            query,
            owner_id=resolve_owner_id(request),
            threshold=threshold,
            match_count=match_count,
            created_after=created_after,
        )
        return json_response(result, request=request)
    except Exception:
        return json_response({"error": "Memory search failed."}, status=400, request=request)


@router.post("/memory/correlate")
async def memory_correlate(request: Request, _secret: None = Depends(backend_secret)) -> dict:
    core = _core(request)
    try:
        payload = await _read_json(request)
        memory_id = str(payload.get("memoryId") or "").strip()
        evidence_id = normalize_evidence_id(payload)
        owner_id = resolve_owner_id(request)
        if memory_id:
            return json_response(core.memory.correlate_memory_id(memory_id, owner_id=owner_id), request=request)
        if evidence_id:
            result = core.memory.ingest_manual({"evidenceId": evidence_id}, owner_id=owner_id)
            return json_response(result.get("correlation") or {"correlated": False}, request=request)
        return json_response({"error": "memoryId or evidenceId is required."}, status=400, request=request)
    except LookupError:
        return json_response({"error": "Not found."}, status=404, request=request)
    except Exception:
        return json_response({"error": "Memory correlation failed."}, status=400, request=request)


@router.get("/memory/{memory_id}")
async def get_memory(
    memory_id: str,
    request: Request,
    _secret: None = Depends(backend_secret),
) -> dict:
    core = _core(request)
    try:
        result = core.memory.get_memory(memory_id, owner_id=resolve_owner_id(request))
        if result:
            return json_response(result, request=request, cache=True)
        return json_response({"error": "Memory item not found."}, status=404, request=request, cache=True)
    except Exception:
        return json_response({"error": "Memory lookup failed."}, status=400, request=request)
