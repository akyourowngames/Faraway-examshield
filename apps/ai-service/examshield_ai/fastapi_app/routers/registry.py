"""Question paper registry, matching, and watermark routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from examshield_ai.normalize import normalize_evidence_id
from examshield_ai.response_cache import cached_get
from examshield_ai.watermark import decode_watermark, parse_token

from ..deps import backend_secret, body_size_guard
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


@router.get("/registry")
async def list_registry(request: Request, _secret: None = Depends(backend_secret)) -> dict:
    core = _core(request)
    papers = cached_get(core.read_cache, request.url.path, core.store.read_registry)
    return json_response({"papers": papers, "total": len(papers)}, request=request, cache=True)


@router.get("/registry/stats")
async def registry_stats(request: Request, _secret: None = Depends(backend_secret)) -> dict:
    core = _core(request)
    papers = cached_get(core.read_cache, request.url.path, core.store.read_registry)
    total = len(papers)
    protected = sum(1 for p in papers if p.get("protected", True))
    compromised = sum(1 for p in papers if p.get("status") == "compromised")
    investigating = sum(1 for p in papers if p.get("status") == "investigating")
    by_exam: dict[str, int] = {}
    for p in papers:
        exam = p.get("exam", "Unknown")
        by_exam[exam] = by_exam.get(exam, 0) + 1
    return json_response(
        {
            "totalPapers": total,
            "protectedPapers": protected,
            "compromisedPapers": compromised,
            "investigatingPapers": investigating,
            "byExam": by_exam,
        },
        request=request,
        cache=True,
    )


@router.get("/registry/{paper_id}")
async def get_registry_paper(
    paper_id: str,
    request: Request,
    _secret: None = Depends(backend_secret),
) -> dict:
    core = _core(request)
    paper = core.store.get_registry_paper(paper_id)
    if not paper:
        return json_response({"error": "Paper not found."}, status=404, request=request)
    return json_response({"paper": paper}, request=request)


@router.post("/demo/reset")
async def demo_reset(request: Request, _secret: None = Depends(backend_secret)) -> dict:
    core = _core(request)
    return json_response(core.store.reset_demo_environment(), request=request)


@router.post("/registry")
async def create_registry_paper(
    request: Request,
    _secret: None = Depends(backend_secret),
    _body: None = Depends(body_size_guard),
) -> dict:
    core = _core(request)
    data = await _read_json(request)
    paper_id = str(data.get("paperId", "")).strip()
    if not paper_id:
        return json_response({"error": "paperId is required."}, status=400, request=request)
    if core.store.get_registry_paper(paper_id):
        return json_response({"error": f"Paper {paper_id} already exists."}, status=409, request=request)
    paper = core.store.add_registry_paper(data)
    return json_response({"paper": paper, "message": "Paper registered."}, status=201, request=request)


@router.post("/registry/reset")
async def reset_registry(request: Request, _secret: None = Depends(backend_secret)) -> dict:
    core = _core(request)
    core.store._write_registry([])
    return json_response({"message": "Registry cleared.", "total": 0}, request=request)


@router.post("/registry/match")
async def match_registry(request: Request, _secret: None = Depends(backend_secret)) -> dict:
    core = _core(request)
    data = await _read_json(request)
    ocr_text = str(data.get("ocrText", "")).strip()
    evidence_id = normalize_evidence_id(data)
    if not ocr_text:
        return json_response({"error": "ocrText is required."}, status=400, request=request)
    matches = core.store.match_evidence_against_registry(ocr_text)
    if matches and evidence_id:
        best = matches[0]
        if best.get("similarityScore", 0) > 70:
            core.store.record_activity({
                "type": "paper-matched",
                "title": "Paper Matched",
                "evidenceId": evidence_id,
                "detail": f"Matched {best.get('matchedExam')} ({best.get('matchedSet')}) at {best.get('similarityScore')}%",
            })
    return json_response({"matches": matches, "total": len(matches)}, request=request)


@router.put("/registry/{paper_id}")
async def update_registry_paper(
    paper_id: str,
    request: Request,
    _secret: None = Depends(backend_secret),
    _body: None = Depends(body_size_guard),
) -> dict:
    core = _core(request)
    data = await _read_json(request)
    try:
        paper = core.store.update_registry_paper(paper_id, data)
        return json_response({"paper": paper}, request=request)
    except LookupError:
        return json_response({"error": "Not found."}, status=404, request=request)
    except Exception:
        return json_response({"error": "Request failed."}, status=400, request=request)


@router.delete("/registry/{paper_id}")
async def delete_registry_paper(
    paper_id: str,
    request: Request,
    _secret: None = Depends(backend_secret),
) -> dict:
    core = _core(request)
    if not core.store.delete_registry_paper(paper_id):
        return json_response({"error": "Paper not found."}, status=404, request=request)
    return json_response({"message": "Paper deleted."}, request=request)


@router.post("/watermark/mint")
async def mint_watermark(request: Request, _secret: None = Depends(backend_secret)) -> dict:
    core = _core(request)
    data = await _read_json(request)
    paper_id = str(data.get("paperId", "")).strip()
    source_text = str(data.get("sourceText", ""))
    recipients = [r for r in (data.get("recipients") or []) if isinstance(r, dict)]
    if not paper_id:
        return json_response({"error": "paperId is required."}, status=400, request=request)
    if not recipients:
        return json_response({"error": "recipients (list) is required."}, status=400, request=request)
    try:
        copies = core.store.mint_copies(paper_id, recipients, source_text)
        return json_response(
            {"paperId": paper_id, "copies": copies, "count": len(copies), "message": "Watermarked copies issued."},
            status=201,
            request=request,
        )
    except LookupError as exc:
        return json_response({"error": str(exc)}, status=404, request=request)
    except ValueError as exc:
        return json_response({"error": str(exc)}, status=400, request=request)
    except Exception:
        return json_response({"error": "Failed to mint watermark."}, status=400, request=request)


@router.post("/watermark/decode")
async def decode_watermark_route(request: Request, _secret: None = Depends(backend_secret)) -> dict:
    core = _core(request)
    data = await _read_json(request)
    text = str(data.get("text") or data.get("ocrText") or "")
    if not text.strip():
        return json_response({"error": "text is required."}, status=400, request=request)
    matches = []
    for token in decode_watermark(text):
        parsed = parse_token(token)
        if not parsed:
            continue
        copy = core.store.find_copy_by_watermark(parsed["copyId"])
        matches.append({
            "token": token,
            "copyId": parsed["copyId"],
            "paperId": parsed["paperId"],
            "recipientRef": parsed["recipientRef"],
            "copy": copy,
        })
    return json_response({"matches": matches, "total": len(matches), "detected": bool(matches)}, request=request)


@router.get("/watermark/copies")
async def list_watermark_copies(request: Request, _secret: None = Depends(backend_secret)) -> dict:
    core = _core(request)
    paper_id = request.query_params.get("paperId")
    copies = core.store.read_copies()
    if paper_id:
        copies = [c for c in copies if c.get("paperId") == paper_id]
    return json_response({"copies": copies, "total": len(copies)}, request=request)
