from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

PROVIDER_REGISTRY: dict[str, dict[str, Any]] = {
    "openrouter": {
        "name": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "models": [
            "anthropic/claude-3.5-sonnet",
            "openai/gpt-4o",
            "openai/gpt-4o-mini",
            "meta-llama/llama-3.1-70b-instruct",
            "google/gemini-2.0-flash-001",
        ],
        "requires_key": True,
        "requires_endpoint": False,
    },
    "groq": {
        "name": "Groq",
        "base_url": "https://api.groq.com/openai/v1",
        "models": [
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "mixtral-8x7b-32768",
            "gemma2-9b-it",
        ],
        "requires_key": True,
        "requires_endpoint": False,
    },
    "google": {
        "name": "Google AI",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "models": [
            "gemini-2.0-flash",
            "gemini-1.5-pro",
            "gemini-1.5-flash",
        ],
        "requires_key": True,
        "requires_endpoint": False,
    },
    "openai": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "models": [
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "gpt-3.5-turbo",
        ],
        "requires_key": True,
        "requires_endpoint": False,
    },
    "anthropic": {
        "name": "Anthropic",
        "base_url": "https://api.anthropic.com/v1",
        "models": [
            "claude-sonnet-4-20250514",
            "claude-3-5-sonnet-20241022",
            "claude-3-haiku-20240307",
        ],
        "requires_key": True,
        "requires_endpoint": False,
    },
    "nvidia-nim": {
        "name": "NVIDIA NIM",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "models": [
            "meta/llama-4-maverick-17b-128e-instruct",
            "mistralai/ministral-14b-instruct-2512",
            "deepseek-ai/deepseek-v4-flash",
        ],
        "requires_key": True,
        "requires_endpoint": False,
    },
    "custom": {
        "name": "Custom Endpoint",
        "base_url": "",
        "models": [],
        "requires_key": True,
        "requires_endpoint": True,
    },
}


@dataclass
class ProviderConfig:
    provider: str
    api_key: str
    model: str
    endpoint_url: str = ""
    extra_headers: dict[str, str] = field(default_factory=dict)


def list_providers() -> list[dict[str, Any]]:
    result = []
    for key, info in PROVIDER_REGISTRY.items():
        result.append({
            "id": key,
            "name": info["name"],
            "models": info["models"],
            "requiresKey": info["requires_key"],
            "requiresEndpoint": info["requires_endpoint"],
        })
    return result


def _build_headers(config: ProviderConfig) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    headers.update(config.extra_headers)

    if config.provider == "anthropic":
        headers["x-api-key"] = config.api_key
        headers["anthropic-version"] = "2023-06-01"
    elif config.provider == "google":
        pass
    else:
        headers["Authorization"] = f"Bearer {config.api_key}"

    return headers


def _build_url(config: ProviderConfig) -> str:
    base = config.endpoint_url or PROVIDER_REGISTRY.get(config.provider, {}).get("base_url", "")

    if config.provider == "google":
        return f"{base}/models/{config.model}:generateContent?key={config.api_key}"

    if config.provider == "anthropic":
        return f"{base}/messages"

    return f"{base}/chat/completions"


def _build_openai_payload(config: ProviderConfig, messages: list[dict[str, str]], **kwargs: Any) -> dict[str, Any]:
    return {
        "model": config.model,
        "messages": messages,
        "max_tokens": kwargs.get("max_tokens", 1024),
        "temperature": kwargs.get("temperature", 0.7),
        "stream": kwargs.get("stream", False),
    }


def _build_anthropic_payload(config: ProviderConfig, messages: list[dict[str, str]], **kwargs: Any) -> dict[str, Any]:
    system_msg = ""
    user_messages = []
    for msg in messages:
        if msg.get("role") == "system":
            system_msg = msg.get("content", "")
        else:
            user_messages.append(msg)

    payload: dict[str, Any] = {
        "model": config.model,
        "messages": user_messages,
        "max_tokens": kwargs.get("max_tokens", 1024),
    }
    if system_msg:
        payload["system"] = system_msg
    return payload


def _build_google_payload(config: ProviderConfig, messages: list[dict[str, str]], **kwargs: Any) -> dict[str, Any]:
    contents = []
    for msg in messages:
        role = "user" if msg.get("role") != "system" else "user"
        contents.append({"role": role, "parts": [{"text": msg.get("content", "")}]})

    return {
        "contents": contents,
        "generationConfig": {
            "maxOutputTokens": kwargs.get("max_tokens", 1024),
            "temperature": kwargs.get("temperature", 0.7),
        },
    }


def _parse_openai_response(data: dict[str, Any]) -> dict[str, Any]:
    choices = data.get("choices", [])
    if not choices:
        return {"error": "No response from model", "content": ""}
    msg = choices[0].get("message", {})
    return {
        "content": msg.get("content", ""),
        "finish_reason": choices[0].get("finish_reason"),
        "usage": data.get("usage", {}),
    }


def _parse_anthropic_response(data: dict[str, Any]) -> dict[str, Any]:
    content_blocks = data.get("content", [])
    text = "".join(block.get("text", "") for block in content_blocks if block.get("type") == "text")
    return {
        "content": text,
        "finish_reason": data.get("stop_reason"),
        "usage": data.get("usage", {}),
    }


def _parse_google_response(data: dict[str, Any]) -> dict[str, Any]:
    candidates = data.get("candidates", [])
    if not candidates:
        return {"error": "No response from model", "content": ""}
    content = candidates[0].get("content", {})
    parts = content.get("parts", [])
    text = "".join(part.get("text", "") for part in parts)
    return {
        "content": text,
        "finish_reason": candidates[0].get("finishReason"),
        "usage": data.get("usageMetadata", {}),
    }


def chat_completion(config: ProviderConfig, messages: list[dict[str, str]], **kwargs: Any) -> dict[str, Any]:
    url = _build_url(config)
    headers = _build_headers(config)

    if config.provider == "anthropic":
        payload = _build_anthropic_payload(config, messages, **kwargs)
    elif config.provider == "google":
        payload = _build_google_payload(config, messages, **kwargs)
    else:
        payload = _build_openai_payload(config, messages, **kwargs)

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")

    timeout = kwargs.get("timeout", 30)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            data = json.loads(raw)
    except urllib.error.HTTPError as exc:
        error_body = ""
        try:
            error_body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        logger.error("LLM provider %s HTTP %d: %s", config.provider, exc.code, error_body[:500])
        return {"error": f"Provider returned HTTP {exc.code}", "content": "", "details": error_body[:500]}
    except Exception as exc:
        logger.error("LLM provider %s error: %s", config.provider, exc)
        return {"error": str(exc), "content": ""}

    if config.provider == "anthropic":
        return _parse_anthropic_response(data)
    elif config.provider == "google":
        return _parse_google_response(data)
    else:
        return _parse_openai_response(data)


def validate_api_key(config: ProviderConfig) -> dict[str, Any]:
    test_messages = [{"role": "user", "content": "Say 'ok' in one word."}]
    result = chat_completion(config, test_messages, max_tokens=10, timeout=15)
    if result.get("error"):
        return {"valid": False, "error": result["error"]}
    return {"valid": True, "model": config.model, "provider": config.provider}
