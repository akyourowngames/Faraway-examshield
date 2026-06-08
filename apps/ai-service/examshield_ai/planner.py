from __future__ import annotations

import json
from typing import Any

from .llm import NvidiaClient
from .store import JsonObject
from .tools import ExamshieldToolRegistry


ROUTER_PROMPT = """You are EXAMSHIELD AI's tool router. Your ONLY job is to decide if the investigator needs live EXAMSHIELD data.

Return a tool call ONLY when the investigator explicitly asks for live data:
- "show me evidence" → listEvidence
- "what threats are active" → listThreats
- "get details on EV-001" → getEvidence
- "generate a report" → generateReport
- "look up NEET-2026-A" → lookupPaper

Do NOT return a tool call for:
- Greetings ("hi", "hello", "hey")
- Questions about how the system works
- Opinions, explanations, or general conversation
- Follow-up questions that can be answered from previous context
- Questions like "what can you do" or "help"

If no tool is needed, return an empty tool_calls list. Do NOT answer the investigator — just route."""


class ToolPlanner:
    def __init__(self, client: NvidiaClient, registry: ExamshieldToolRegistry) -> None:
        self.client = client
        self.registry = registry

    def plan(
        self,
        prompt: str,
        current_evidence_id: str | None,
        history: list[JsonObject],
    ) -> JsonObject | None:
        context = self.registry.planner_context(current_evidence_id)
        payload = self.client.chat_json(
            model=self.client.settings.planner_model,
            messages=[
                {
                    "role": "system",
                    "content": ROUTER_PROMPT
                    + "\n\nLive EXAMSHIELD context:\n"
                    + json.dumps(context, indent=2, ensure_ascii=False),
                },
                *model_history(history),
                {"role": "user", "content": prompt},
            ],
            tools=self.registry.schemas(),
            max_tokens=160,
            timeout=self.client.settings.planner_timeout_seconds,
        )
        calls = payload.get("choices", [{}])[0].get("message", {}).get("tool_calls", [])
        if not calls:
            return None
        return normalize_tool_call(calls[0])


def model_history(history: list[JsonObject]) -> list[JsonObject]:
    messages: list[JsonObject] = []
    for item in history[-6:]:
        role = "user" if item.get("role") == "operator" else "assistant"
        content = str(item.get("content") or "")
        if content:
            messages.append({"role": role, "content": content})
    return messages


def normalize_tool_call(call: JsonObject) -> JsonObject | None:
    function = call.get("function") or {}
    name = str(function.get("name") or "")
    args = parse_arguments(function.get("arguments"))

    if name == "listEvidence":
        return {"tool": "listEvidence", "arguments": {"filter": "today" if args.get("filter") == "today" else "recent"}}
    if name == "getEvidence" and isinstance(args.get("evidenceId"), str):
        return {"tool": "getEvidence", "arguments": {"evidenceId": args["evidenceId"]}}
    if name == "getAttribution" and isinstance(args.get("evidenceId"), str):
        return {"tool": "getAttribution", "arguments": {"evidenceId": args["evidenceId"]}}
    if name == "lookupPaper" and isinstance(args.get("paperId"), str):
        return {"tool": "lookupPaper", "arguments": {"paperId": args["paperId"]}}
    if name == "listThreats":
        return {"tool": "listThreats", "arguments": {"variant": "compromised"} if args.get("variant") == "compromised" else {}}
    if name == "generateReport":
        return {"tool": "generateReport", "arguments": {}}
    return None


def parse_arguments(raw: Any) -> JsonObject:
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(str(raw))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}
