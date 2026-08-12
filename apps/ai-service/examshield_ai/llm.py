from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

from .settings import Settings
from .store import JsonObject


TokenWriter = Callable[[str], None]


class KiloClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._unavailable_until = 0.0

    @property
    def configured(self) -> bool:
        return bool(self.settings.api_key)

    def chat_json(
        self,
        *,
        model: str,
        messages: list[JsonObject],
        tools: list[JsonObject] | None = None,
        max_tokens: int = 240,
        timeout: float | None = None,
    ) -> JsonObject:
        payload: JsonObject = {
            "model": model,
            "temperature": 0,
            "top_p": 0.7,
            "max_tokens": max_tokens,
            "messages": messages,
            # Kilo gateway streams internally; keep it off for JSON tool calls.
            "stream": False,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        return self._request_json_with_fallbacks(payload, model, timeout or self.settings.stream_timeout_seconds)

    def stream_chat(
        self,
        *,
        model: str,
        messages: list[JsonObject],
        on_token: TokenWriter,
        max_tokens: int | None = None,
        timeout: float | None = None,
        tools: list[JsonObject] | None = None,
        on_tool_call: Callable[[int, str, str], None] | None = None,
        on_tool_delta: Callable[[int, str], None] | None = None,
    ) -> bool:
        """Stream a chat completion, emitting text tokens and inline tool calls.

        When ``tools`` is provided the request is sent with ``tool_choice:
        "auto"`` so the model decides conversation vs. tool use in the same
        request (Ares-style inline routing — no separate planning pass). Tool
        call fragments are forwarded to ``on_tool_call`` (index/id/name) and
        ``on_tool_delta`` (streaming argument JSON) as they arrive.
        """
        if time.monotonic() < self._unavailable_until:
            raise RuntimeError("Kilo gateway is in a short retry cooldown after a failed request.")
        errors: list[str] = []
        token_limit = max_tokens if max_tokens is not None else self.settings.chat_max_tokens
        per_model_timeout = timeout or self.settings.stream_timeout_seconds
        for candidate in self._candidate_models(model):
            payload: JsonObject = {
                "model": candidate,
                "temperature": 0,
                "top_p": 0.7,
                "max_tokens": token_limit,
                "stream": True,
                "messages": messages,
            }
            if tools:
                payload["tools"] = tools
                payload["tool_choice"] = "auto"
            request = self._request(payload)
            try:
                with urllib.request.urlopen(request, timeout=per_model_timeout) as response:
                    emitted = False
                    for raw_line in response:
                        line = raw_line.decode("utf-8", errors="replace").strip()
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if not data or data == "[DONE]":
                            continue
                        try:
                            parsed = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        choice = parsed.get("choices", [{}])[0]
                        delta = choice.get("delta", {})
                        # Only `content` is ever shown to the user. Reasoning
                        # models (e.g. tencent/hy3 via Kilo) stream their internal
                        # monologue in `reasoning`/`reasoning_content`; we
                        # deliberately ignore it so the model's thinking never
                        # leaks into the chat transcript. Prefer a non-reasoning
                        # model (see Settings) to avoid the thinking-phase latency
                        # entirely — reasoning tokens here would just be wasted.
                        content_token = delta.get("content") or ""
                        if content_token:
                            emitted = True
                            on_token(str(content_token))
                        for tc in delta.get("tool_calls") or []:
                            emitted = True
                            index = int(tc.get("index", 0))
                            fn = tc.get("function", {})
                            if on_tool_call is not None and (tc.get("id") or fn.get("name")):
                                on_tool_call(index, str(tc.get("id") or ""), str(fn.get("name") or ""))
                            if on_tool_delta is not None and fn.get("arguments"):
                                on_tool_delta(index, str(fn.get("arguments")))
                    if emitted:
                        self._unavailable_until = 0.0
                        return True
                    errors.append(f"{candidate}: empty stream")
            except Exception as exc:
                errors.append(f"{candidate}: {type(exc).__name__}: {exc}")
        self._unavailable_until = time.monotonic() + 10.0
        raise RuntimeError("Kilo gateway stream failed for all models: " + " | ".join(errors))

    def chat_text(
        self,
        *,
        model: str,
        messages: list[JsonObject],
        max_tokens: int = 260,
        timeout: float | None = None,
    ) -> str:
        payload = self.chat_json(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            timeout=timeout or self.settings.stream_timeout_seconds,
        )
        return str(payload.get("choices", [{}])[0].get("message", {}).get("content") or "").strip()

    def _request_json(self, payload: JsonObject, timeout: float) -> JsonObject:
        request = self._request(payload)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")[:240]
            raise RuntimeError(f"Kilo gateway returned {exc.code}: {details}") from exc
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}

    def _request_json_with_fallbacks(self, payload: JsonObject, model: str, timeout: float) -> JsonObject:
        if time.monotonic() < self._unavailable_until:
            raise RuntimeError("Kilo gateway is in a short retry cooldown after a failed request.")
        errors: list[str] = []
        per_model_timeout = timeout
        for candidate in self._candidate_models(model):
            candidate_payload = dict(payload)
            candidate_payload["model"] = candidate
            try:
                response = self._request_json(candidate_payload, per_model_timeout)
                self._unavailable_until = 0.0
                return response
            except Exception as exc:
                errors.append(f"{candidate}: {type(exc).__name__}: {exc}")
        self._unavailable_until = time.monotonic() + 10.0
        raise RuntimeError("Kilo gateway chat request failed for all configured models: " + " | ".join(errors))

    def _candidate_models(self, primary: str) -> tuple[str, ...]:
        models: list[str] = []
        for model in (primary, *self.settings.fallback_models):
            cleaned = str(model or "").strip()
            if cleaned and cleaned not in models:
                models.append(cleaned)
        return tuple(models)

    def _request(self, payload: JsonObject) -> urllib.request.Request:
        return urllib.request.Request(
            f"{self.settings.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.settings.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )


# Backwards-compatible alias so any stragglers importing NvidiaClient still work.
NvidiaClient = KiloClient
