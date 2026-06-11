from __future__ import annotations

import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Any

from .llm import NvidiaClient
from .planner import ToolPlanner
from .responses import conversation_messages, grounded_messages
from .store import JsonObject
from .tools import ExamshieldToolRegistry

EventWriter = Callable[[dict[str, Any]], None]


class ChatSession:
    def __init__(
        self,
        *,
        client: NvidiaClient,
        registry: ExamshieldToolRegistry,
        write: EventWriter,
    ) -> None:
        self.client = client
        self.registry = registry
        self.write = write
        self.planner = ToolPlanner(client, registry)

    def run(
        self,
        prompt: str,
        history: list[JsonObject],
        current_evidence_id: str | None,
    ) -> None:
        started = time.monotonic()
        self.write({"type": "stage", "message": "Connecting to EXAMSHIELD intelligence..."})

        if not self.client.configured:
            self.write({"type": "error", "message": "NVIDIA_API_KEY is not configured."})
            self.write({"type": "done"})
            return

        command: JsonObject | None = None
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                self.planner.plan,
                prompt,
                current_evidence_id,
                history,
            )
            try:
                command = future.result(timeout=self.client.settings.planner_timeout_seconds)
            except FuturesTimeoutError:
                self.write({"type": "stage", "message": "Routing timed out — responding directly."})
            except Exception as exc:
                self.write({"type": "stage", "message": f"Tool planner unavailable: {type(exc).__name__}."})

        if command:
            self._run_tool_path(prompt, history, command, started)
            return

        self._run_conversation_path(prompt, history, started)

    def _run_tool_path(
        self,
        prompt: str,
        history: list[JsonObject],
        command: JsonObject,
        started: float,
    ) -> None:
        tool_name = str(command.get("tool") or "")
        self.write({"type": "stage", "message": f"Using {tool_name}() with live EXAMSHIELD data."})
        execution = self.registry.execute(tool_name, command.get("arguments") or {})
        self.write({"type": "tool", "tool": execution.result["tool"], "result": execution.result})
        self.write({"type": "meta", "model": self.client.settings.model, "provider": "nvidia-nim"})
        messages = grounded_messages(prompt, history, execution.model_context)
        self._stream_tokens(messages, started)

    def _run_conversation_path(self, prompt: str, history: list[JsonObject], started: float) -> None:
        self.write({"type": "meta", "model": self.client.settings.model, "provider": "nvidia-nim"})
        messages = conversation_messages(prompt, history)
        self._stream_tokens(messages, started)

    def _stream_tokens(self, messages: list[JsonObject], started: float) -> None:
        def on_token(token: str) -> None:
            self.write({"type": "token", "token": token})

        self.client.stream_chat(
            model=self.client.settings.model,
            messages=messages,
            on_token=on_token,
            max_tokens=self.client.settings.chat_max_tokens,
        )
        latency_ms = int((time.monotonic() - started) * 1000)
        self.write({"type": "done", "latencyMs": latency_ms})
