from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

PROVIDER_REGISTRY: dict[str, dict[str, Any]] = {
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
        "key_prefix": "sk-",
        "validate_url": "https://api.openai.com/v1/models",
        "validate_method": "GET",
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
        "key_prefix": "sk-ant-",
        "validate_url": "https://api.anthropic.com/v1/messages",
        "validate_method": "POST",
    },
    "grok": {
        "name": "Grok (xAI)",
        "base_url": "https://api.x.ai/v1",
        "models": [
            "grok-3",
            "grok-3-mini",
            "grok-2",
        ],
        "requires_key": True,
        "requires_endpoint": False,
        "key_prefix": "xai-",
        "validate_url": "https://api.x.ai/v1/models",
        "validate_method": "GET",
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
        "key_prefix": "gsk_",
        "validate_url": "https://api.groq.com/openai/v1/models",
        "validate_method": "GET",
    },
    "opencode": {
        "name": "OpenCode Zen",
        "base_url": "https://opencode.ai/zen/v1",
        "models": {
            "Free Models": [
                "big-pickle",
                "deepseek-v4-flash-free",
                "mimo-v2.5-free",
                "north-mini-code-free",
                "nemotron-3-ultra-free",
            ],
            "DeepSeek": [
                "deepseek-v4-flash",
                "deepseek-v4-pro",
            ],
            "MiniMax": [
                "minimax-m2.5",
                "minimax-m2.7",
            ],
            "GLM": [
                "glm-5",
                "glm-5.1",
            ],
            "Kimi": [
                "kimi-k2.5",
                "kimi-k2.6",
            ],
            "Grok": [
                "grok-build-0.1",
            ],
            "Qwen": [
                "qwen3.5-plus",
                "qwen3.6-plus",
                "qwen3.7-plus",
                "qwen3.7-max",
            ],
            "Claude": [
                "claude-haiku-4-5",
                "claude-sonnet-4",
                "claude-sonnet-4-5",
                "claude-sonnet-4-6",
                "claude-opus-4-1",
                "claude-opus-4-5",
                "claude-opus-4-6",
                "claude-opus-4-7",
                "claude-opus-4-8",
                "claude-fable-5",
            ],
            "GPT": [
                "gpt-5",
                "gpt-5-nano",
                "gpt-5.1",
                "gpt-5.1-codex",
                "gpt-5.1-codex-max",
                "gpt-5.1-codex-mini",
                "gpt-5.2",
                "gpt-5.2-codex",
                "gpt-5.3-codex",
                "gpt-5.3-codex-spark",
                "gpt-5.4",
                "gpt-5.4-mini",
                "gpt-5.4-nano",
                "gpt-5.4-pro",
                "gpt-5.5",
                "gpt-5.5-pro",
            ],
            "Gemini": [
                "gemini-3-flash",
                "gemini-3.1-pro",
                "gemini-3.5-flash",
            ],
        },
        "requires_key": True,
        "requires_endpoint": False,
        "key_prefix": "sk-",
        "validate_url": "https://opencode.ai/zen/v1/chat/completions",
        "validate_method": "POST",
        "validate_model": "big-pickle",
    },
    "kilo": {
        "name": "Kilo Gateway",
        "base_url": "https://api.kilo.ai/api/gateway",
        "models": [
            "tencent/hy3:free",
            "tencent/hy3",
            "tencent/hy3-preview",
            "stepfun/step-3.7-flash:free",
            "kilo-auto/free",
            "kilo-auto/balanced",
            "kilo-auto/efficient",
            "kilo-auto/frontier",
            "anthropic/claude-sonnet-5",
        ],
        "requires_key": True,
        "requires_endpoint": False,
        "key_prefix": "",
        "validate_url": "https://api.kilo.ai/api/gateway/chat/completions",
        "validate_method": "POST",
        "validate_model": "tencent/hy3:free",
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
        models = info["models"]
        # Handle grouped models (dict) vs flat list
        if isinstance(models, dict):
            flat_models = []
            for group_models in models.values():
                flat_models.extend(group_models)
            result.append({
                "id": key,
                "name": info["name"],
                "models": flat_models,
                "groupedModels": models,
                "requiresKey": info["requires_key"],
                "requiresEndpoint": info["requires_endpoint"],
            })
        else:
            result.append({
                "id": key,
                "name": info["name"],
                "models": models,
                "groupedModels": None,
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
    provider_info = PROVIDER_REGISTRY.get(config.provider, {})
    validate_url = provider_info.get("validate_url")
    validate_method = provider_info.get("validate_method", "GET")

    if not validate_url:
        return {"valid": False, "error": f"Provider '{config.provider}' not supported for validation."}

    # For OpenCode Zen, try a simpler validation approach
    if config.provider == "opencode":
        return _validate_opencode_key(config, provider_info)

    if config.provider == "anthropic":
        headers = {
            "x-api-key": config.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = json.dumps({
            "model": config.model or "claude-3-haiku-20240307",
            "max_tokens": 10,
            "messages": [{"role": "user", "content": "Say ok"}],
        }).encode("utf-8")
    elif config.provider == "kilo":
        validate_model = provider_info.get("validate_model", "tencent/hy3:free")
        headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        }
        payload = json.dumps({
            "model": validate_model,
            "max_tokens": 5,
            "messages": [{"role": "user", "content": "hi"}],
        }).encode("utf-8")
    else:
        headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        }
        payload = None

    req = urllib.request.Request(validate_url, data=payload, headers=headers, method=validate_method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
            model = config.model
            if not model and config.provider not in ("anthropic", "kilo"):
                models = data.get("data", [])
                if models and isinstance(models, list):
                    model = models[0].get("id", config.model)
            if not model and config.provider == "kilo":
                model = provider_info.get("validate_model", config.model)
            return {"valid": True, "model": model, "provider": config.provider}
    except urllib.error.HTTPError as exc:
        error_body = ""
        try:
            error_body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        if exc.code == 401:
            return {"valid": False, "error": "Invalid API key."}
        elif exc.code == 403:
            return {"valid": False, "error": "API key does not have access to this resource."}
        elif exc.code == 429:
            return {"valid": True, "model": config.model, "provider": config.provider}
        else:
            return {"valid": False, "error": f"Validation failed (HTTP {exc.code}): {error_body[:200]}"}
    except urllib.error.URLError:
        return {"valid": False, "error": "Network error reaching provider API."}
    except Exception as exc:
        return {"valid": False, "error": str(exc) or "Validation failed."}


def _validate_opencode_key(config: ProviderConfig, provider_info: dict[str, Any]) -> dict[str, Any]:
    """Special validation for OpenCode Zen.

    Strategy: try a real API call with a free model. If the API confirms the key
    works, great. If we get 401, the key is definitely bad. For any other error
    (403, 500, network timeout, DNS failure, etc.) we accept the key with a
    warning rather than blocking the user — the actual agent test will catch
    real problems.
    """
    validate_url = provider_info.get("validate_url", "https://opencode.ai/zen/v1/chat/completions")

    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json",
    }

    # Quick format check first
    if not config.api_key.startswith("sk-"):
        return {"valid": False, "error": "Invalid key format. OpenCode Zen keys start with 'sk-'. Get one from https://opencode.ai/auth"}

    # Try a free model to confirm the key works
    models_to_try = ["big-pickle", "deepseek-v4-flash-free", "mimo-v2.5-free"]

    for model in models_to_try:
        payload = json.dumps({
            "model": model,
            "max_tokens": 5,
            "messages": [{"role": "user", "content": "hi"}],
        }).encode("utf-8")

        req = urllib.request.Request(validate_url, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                resp.read()
                return {"valid": True, "model": model, "provider": config.provider}
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                return {"valid": False, "error": "Invalid API key. Get a Zen key from https://opencode.ai/auth (not the CLI key)."}
            if exc.code == 429:
                return {"valid": True, "model": model, "provider": config.provider}
            # 403, 500, etc — try next model, don't reject yet
            continue
        except Exception:
            # Network/DNS/timeout — try next model
            continue

    # All models failed but key format is correct. Don't block the user — the
    # API may be temporarily unreachable or the specific models may be
    # unavailable. The agent test will catch real credential problems.
    return {
        "valid": True,
        "model": config.model or "big-pickle",
        "provider": config.provider,
        "warning": "Could not verify the key against OpenCode Zen (service may be temporarily unavailable). The key format looks correct — proceed and test your agent to confirm.",
    }
