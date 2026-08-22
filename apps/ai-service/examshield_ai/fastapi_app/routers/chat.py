"""Conversational chat + tool-planning endpoints.

Ports ``ExamshieldAiHandler._run_chat`` and ``_run_plan`` to FastAPI. The
actual LLM logic stays in ``examshield_ai.chat.ChatSession`` and
``examshield_ai.planner.ToolPlanner``.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request

from examshield_ai.chat import ChatSession
from examshield_ai.normalize import normalize_current_evidence_id
from examshield_ai.operator import resolve_operator
from examshield_ai.planner import ToolPlanner
from examshield_ai.tools import ExamshieldToolRegistry

from ..deps import backend_secret, body_size_guard, client_ip, resolve_owner_id
from ..responses import json_response
from ..sse import sse_from_chat_session

router = APIRouter()


@router.post("/chat")
async def chat(
    request: Request,
    _secret: None = Depends(backend_secret),
    _body: None = Depends(body_size_guard),
) -> Any:
    core = request.app.state.core

    try:
        payload = await request.json()
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}

    prompt = str(payload.get("prompt") or "").strip()
    if not prompt:
        return json_response({"error": "Prompt is required."}, status=400, request=request)

    history = payload.get("messages") if isinstance(payload.get("messages"), list) else []
    current_evidence_id = normalize_current_evidence_id(payload)
    current_evidence_id = str(current_evidence_id) if current_evidence_id else None

    operator = resolve_operator(payload, request.headers.get("Authorization"), core.settings)
    registry = ExamshieldToolRegistry(core.store)
    registry.operator = operator
    registry.owner_id = resolve_owner_id(request)

    def run_session(write_event):
        session = ChatSession(client=core.client, registry=registry, write=write_event)
        session.run(prompt, history, current_evidence_id, operator, tenant=client_ip(request))

    return sse_from_chat_session(run_session)


@router.post("/plan")
async def plan(
    request: Request,
    _secret: None = Depends(backend_secret),
    _body: None = Depends(body_size_guard),
) -> Any:
    core = request.app.state.core

    try:
        payload = await request.json()
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}

    prompt = str(payload.get("prompt") or "").strip()
    if not prompt:
        return json_response({"error": "Prompt is required."}, status=400, request=request)

    history = payload.get("messages") if isinstance(payload.get("messages"), list) else []
    current_evidence_id = normalize_current_evidence_id(payload)
    current_evidence_id = str(current_evidence_id) if current_evidence_id else None

    if not core.client.configured:
        return json_response({"tool": None, "error": "KILO_API_KEY is not configured."}, request=request)

    core.registry.owner_id = resolve_owner_id(request)

    try:
        command = ToolPlanner(core.client, core.registry).plan(prompt, current_evidence_id, history)
    except Exception as exc:
        return json_response(
            {"tool": None, "error": f"Tool planner unavailable: {type(exc).__name__}."},
            request=request,
        )

    if not command:
        return json_response({"tool": None}, request=request)

    execution = core.registry.execute(command["tool"], command.get("arguments") or {})
    return json_response(
        {
            "tool": execution.result["tool"],
            "result": execution.result,
            "model_context": execution.model_context,
        },
        request=request,
    )
