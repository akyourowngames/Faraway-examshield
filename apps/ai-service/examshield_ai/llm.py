from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from collections.abc import Callable

from .settings import Settings
from .store import JsonObject

TokenWriter = Callable[[str], None]

# HTTP codes worth a quick retry — everything else fails fast to the next model.
_TRANSIENT_HTTP_CODES = {408, 409, 425, 429, 500, 502, 503, 504}


class _StreamFailure(Exception):
    """Candidate-stream failure tagged with whether it is safe to replay."""

    def __init__(self, message: str, *, transient: bool) -> None:
        super().__init__(message)
        self.transient = transient


def _is_transient(exc: Exception) -> bool:
    """True for timeouts/connection errors and retryable HTTP statuses."""
    if isinstance(exc, _StreamFailure):
        return exc.transient
    if isinstance(exc, (TimeoutError, urllib.error.URLError)):
        return True
    match = re.search(r"returned (\d{3})", str(exc))
    return bool(match and int(match.group(1)) in _TRANSIENT_HTTP_CODES)


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
            # Transient failures (timeouts, 429/5xx) get a bounded exponential
            # backoff — but only while nothing has been emitted, since tokens
            # already streamed to the client can never be replayed.
            for attempt in range(self.settings.llm_retry_attempts + 1):
                try:
                    emitted = self._stream_candidate(request, per_model_timeout, on_token, on_tool_call, on_tool_delta)
                except Exception as exc:
                    errors.append(f"{candidate}: {type(exc).__name__}: {exc}")
                    if attempt >= self.settings.llm_retry_attempts or not _is_transient(exc):
                        break
                    time.sleep(self._retry_delay(attempt))
                    continue
                if emitted:
                    self._unavailable_until = 0.0
                    return True
                # No `content` arrived — try the next model instead of retrying.
                errors.append(f"{candidate}: empty stream")
                break
        self._unavailable_until = time.monotonic() + 10.0
        raise RuntimeError("Kilo gateway stream failed for all models: " + " | ".join(errors))

    def _stream_candidate(
        self,
        request: urllib.request.Request,
        timeout: float,
        on_token: TokenWriter,
        on_tool_call: Callable[[int, str, str], None] | None,
        on_tool_delta: Callable[[int, str], None],
    ) -> bool:
        """Stream one candidate model. Returns True when output was emitted."""
        emitted = False
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                reasoning_buffer: list[str] = []
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
                    content_token = delta.get("content") or ""
                    reasoning_token = delta.get("reasoning") or delta.get("reasoning_content") or ""
                    if content_token:
                        emitted = True
                        on_token(str(content_token))
                    elif reasoning_token:
                        reasoning_buffer.append(reasoning_token)
                    for tc in delta.get("tool_calls") or []:
                        emitted = True
                        index = int(tc.get("index", 0))
                        fn = tc.get("function", {})
                        if on_tool_call is not None and (tc.get("id") or fn.get("name")):
                            on_tool_call(index, str(tc.get("id") or ""), str(fn.get("name") or ""))
                        if on_tool_delta is not None and fn.get("arguments"):
                            on_tool_delta(index, str(fn.get("arguments")))
                if not emitted and reasoning_buffer:
                    # Reasoning models may never emit `content`; surface the
                    # buffered reasoning so the user still sees an answer.
                    on_token("".join(reasoning_buffer))
                    emitted = True
                return emitted
        except Exception as exc:
            # Once tokens reached the client a retry would replay them, so only
            # failures before any output are safe to treat as transient.
            raise _StreamFailure(f"{type(exc).__name__}: {exc}", transient=not emitted) from exc

    def _retry_delay(self, attempt: int) -> float:
        """Exponential backoff with a small cap so retries stay bounded."""
        return min(self.settings.llm_retry_backoff_seconds * (2**attempt), 4.0)

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
            for attempt in range(self.settings.llm_retry_attempts + 1):
                try:
                    response = self._request_json(candidate_payload, per_model_timeout)
                    self._unavailable_until = 0.0
                    return response
                except Exception as exc:
                    errors.append(f"{candidate}: {type(exc).__name__}: {exc}")
                    if attempt >= self.settings.llm_retry_attempts or not _is_transient(exc):
                        break
                    time.sleep(self._retry_delay(attempt))
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
