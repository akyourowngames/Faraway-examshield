from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from typing import Any

from .llm import KiloClient
from .responses import conversation_messages
from .store import JsonObject
from .tools import ExamshieldToolRegistry
from .turn_policy import TurnIntent, classify_turn_intent

EventWriter = Callable[[dict[str, Any]], None]

# Ares keeps an execution loop bounded; we cap tool-augmented turns so a single
# request can never spin forever.
MAX_TOOL_ITERATIONS = 3

_EVIDENCE_ID_RE = re.compile(r"\bev-\d+\b", re.IGNORECASE)


class ChatSession:
    def __init__(
        self,
        *,
        client: KiloClient,
        registry: ExamshieldToolRegistry,
        write: EventWriter,
    ) -> None:
        self.client = client
        self.registry = registry
        self.write = write
        self.operator: JsonObject | None = None

    def run(
        self,
        prompt: str,
        history: list[JsonObject],
        current_evidence_id: str | None,
        operator: JsonObject | None = None,
    ) -> None:
        started = time.monotonic()
        self.operator = operator
        # The registry is request-scoped for /chat, so scoping operator here is
        # safe under the threaded server (no cross-request clobbering).
        self.registry.operator = operator
        self.write({"type": "stage", "message": "Connecting to EXAMSHIELD intelligence..."})

        if not self.client.configured:
            self._write_local_fallback(
                "EXAMSHIELD AI is online, but no language-model key is configured. "
                "Live evidence tools remain available from the dashboard.",
                started,
            )
            return

        # Ares-style cheap intent classification — zero LLM calls. This decides
        # whether we attach tool schemas at all. When the message is plain
        # conversation we stream directly with no tools (fast path). When it
        # looks like a live-data request we send the schemas in the SAME request
        # as the answer, so routing happens inline with generation — no separate
        # planning round-trip.
        intent = classify_turn_intent(prompt)
        use_tools = intent is TurnIntent.TOOL_REQUEST

        messages = list(conversation_messages(prompt, history, operator))
        tool_schemas = self.registry.schemas() if use_tools else []

        self._run_loop(prompt, messages, tool_schemas, current_evidence_id, started)

    def _run_loop(
        self,
        prompt: str,
        messages: list[JsonObject],
        tool_schemas: list[JsonObject],
        current_evidence_id: str | None,
        started: float,
    ) -> None:
        evidence_id = self._resolve_evidence_id(prompt, current_evidence_id)
        last_content = ""
        first_token_at: float | None = None

        for _iteration in range(MAX_TOOL_ITERATIONS):
            emitted_text = False
            tool_calls: dict[int, dict[str, str]] = {}

            def on_token(token: str) -> None:
                nonlocal emitted_text, first_token_at
                emitted_text = True
                if first_token_at is None:
                    first_token_at = time.monotonic()
                self.write({"type": "token", "token": token})

            def on_tool_call(index: int, call_id: str, name: str) -> None:
                entry = tool_calls.setdefault(index, {"id": "", "name": "", "arguments": ""})
                if call_id:
                    entry["id"] = call_id
                if name:
                    entry["name"] = name

            def on_tool_delta(index: int, arguments: str) -> None:
                entry = tool_calls.setdefault(index, {"id": "", "name": "", "arguments": ""})
                entry["arguments"] += arguments

            try:
                self.client.stream_chat(
                    model=self.client.settings.model,
                    messages=messages,
                    on_token=on_token,
                    on_tool_call=on_tool_call,
                    on_tool_delta=on_tool_delta,
                    tools=tool_schemas or None,
                    max_tokens=self.client.settings.chat_max_tokens,
                )
            except Exception as exc:
                self._handle_stream_error(exc, emitted_text, last_content, started, first_token_at)
                return

            # If the model selected a tool, execute it and continue the loop so
            # the model can answer from the real data (Ares execute-then-continue).
            if tool_calls:
                last_content = self._execute_tool_calls(tool_calls, messages, evidence_id)
                continue

            # No tool call — this is the final answer.
            self._write_meta(started, first_token_at)
            self.write({"type": "done", "latencyMs": self._latency_ms(started)})
            return

        # Exhausted iterations (tools kept firing) — emit a graceful close.
        self._write_meta(started, first_token_at)
        self.write({"type": "done", "latencyMs": self._latency_ms(started)})

    def _execute_tool_calls(
        self,
        tool_calls: dict[int, dict[str, str]],
        messages: list[JsonObject],
        evidence_id: str | None,
    ) -> str:
        assistant_tool_calls = []
        for index in sorted(tool_calls):
            call = tool_calls[index]
            assistant_tool_calls.append({
                "id": call["id"] or f"call_{index}",
                "type": "function",
                "function": {"name": call["name"], "arguments": call["arguments"]},
            })
        messages.append({"role": "assistant", "content": "", "tool_calls": assistant_tool_calls})

        last_summary = ""
        for call in assistant_tool_calls:
            name = str(call["function"]["name"] or "")
            raw_args = str(call["function"]["arguments"] or "")
            args = self._parse_arguments(raw_args)
            if evidence_id and name in ("getEvidence", "getAttribution") and not args.get("evidenceId"):
                args["evidenceId"] = evidence_id

            self.write({"type": "stage", "message": f"Using {name}() with live EXAMSHIELD data."})
            try:
                execution = self.registry.execute(name, args)
            except Exception as exc:
                self.write({"type": "stage", "message": f"{name}() failed: {exc}"})
                messages.append({
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": json.dumps({"tool": name, "error": str(exc)}, ensure_ascii=False),
                })
                continue

            result = execution.result
            self.write({"type": "tool", "tool": result.get("tool") or name, "result": result})
            last_summary = self._tool_fallback_text(result)
            messages.append({
                "role": "tool",
                "tool_call_id": call["id"],
                "content": json.dumps(result, ensure_ascii=False),
            })

        return last_summary

    def _handle_stream_error(
        self,
        exc: Exception,
        emitted_text: bool,
        last_content: str,
        started: float,
        first_token_at: float | None = None,
    ) -> None:
        error_name = type(exc).__name__
        if "timeout" in str(exc).lower() or "Timeout" in error_name:
            self.write({"type": "stage", "message": "Language model timed out — try again in a few seconds."})
        elif "cooldown" in str(exc).lower():
            self.write({"type": "stage", "message": "Language model cooling down from previous error — try again shortly."})
        else:
            self.write({"type": "stage", "message": f"Language model unavailable: {error_name}."})
        if not emitted_text:
            fallback = last_content or (
                "EXAMSHIELD AI is online, but the language model did not respond in time. "
                "You can retry, or use a direct command such as “show recent evidence”, "
                "“list threats”, or “generate a report”."
            )
            self._write_local_fallback(fallback, started)
        else:
            self._write_meta(started, first_token_at)
            self.write({"type": "done", "latencyMs": self._latency_ms(started)})

    def _write_local_fallback(self, text: str, started: float) -> None:
        self.write({"type": "meta", "model": "local-operational-fallback", "provider": "local-fallback"})
        self.write({"type": "token", "token": text})
        self.write({"type": "done", "latencyMs": self._latency_ms(started)})

    def _write_meta(self, started: float, first_token_at: float | None = None) -> None:
        meta: JsonObject = {
            "type": "meta",
            "model": self.client.settings.model,
            "provider": "kilo-gateway",
        }
        if first_token_at is not None:
            meta["ttftMs"] = int((first_token_at - started) * 1000)
        self.write(meta)

    @staticmethod
    def _resolve_evidence_id(prompt: str, current_evidence_id: str | None) -> str | None:
        match = _EVIDENCE_ID_RE.search(prompt)
        if match:
            return match.group(0).upper()
        return current_evidence_id

    @staticmethod
    def _parse_arguments(raw: str) -> JsonObject:
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _latency_ms(started: float) -> int:
        return int((time.monotonic() - started) * 1000)

    @staticmethod
    def _tool_fallback_text(result: JsonObject) -> str:
        summary = str(result.get("summary") or "The live EXAMSHIELD query completed.").strip()
        metrics = result.get("metrics") if isinstance(result.get("metrics"), list) else []
        details = []
        for metric in metrics[:4]:
            if isinstance(metric, dict):
                label = str(metric.get("label") or "").strip()
                value = str(metric.get("value") or "").strip()
                if label and value:
                    details.append(f"{label}: {value}")
        return summary + (" " + "; ".join(details) + "." if details else "")
