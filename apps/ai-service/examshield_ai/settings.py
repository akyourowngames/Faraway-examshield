from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    repo_root: Path
    upload_root: Path
    registry_path: Path
    api_key: str
    model: str
    fallback_models: tuple[str, ...]
    planner_model: str
    base_url: str
    planner_timeout_seconds: float
    stream_timeout_seconds: float
    chat_max_tokens: int
    planner_max_tokens: int
    list_cache_ttl_seconds: float
    supabase_timeout_seconds: float
    detect_threshold: float
    cors_origin: str
    max_upload_bytes: int
    supabase_url: str
    supabase_service_role_key: str
    supabase_document_table: str
    supabase_storage_bucket: str
    public_url: str
    telegram_bot_token: str
    telegram_webhook_secret: str
    telegram_chat_id: str
    telegram_admin_chat_id: str
    api_auth_secret: str = ""
    llm_daily_token_budget: int = 0
    llm_budget_window_seconds: int = 86_400
    llm_retry_attempts: int = 2
    llm_retry_backoff_seconds: float = 0.5
    budget_per_request_tokens: int = 4_000
    budget_per_session_tokens: int = 50_000


def load_settings() -> Settings:
    repo_root = Path(os.environ.get("EXAMSHIELD_REPO_ROOT") or Path(__file__).resolve().parents[3]).resolve()
    upload_root = Path(
        os.environ.get("EXAMSHIELD_UPLOAD_ROOT")
        or repo_root / "apps" / "api" / "uploads" / "evidence"
    ).resolve()
    registry_path = Path(
        os.environ.get("EXAMSHIELD_REGISTRY_PATH")
        or repo_root / "apps" / "core" / "data" / "papers.json"
    ).resolve()
    model = (
        os.environ.get("EXAMSHIELD_AI_MODEL")
        or os.environ.get("EXAMSHIELD_CHAT_MODEL")
        or os.environ.get("KILO_MODEL")
        or os.environ.get("KILO_CHAT_MODEL")
        or os.environ.get("NVIDIA_MODEL")
        or os.environ.get("NVIDIA_NIM_MODEL")
        or os.environ.get("NIM_MODEL")
        or os.environ.get("EXAMSHIELD_AI_DEFAULT_MODEL")
        or "tencent/hy3:free"
    ).strip()
    fallback_models = _split_csv(
        os.environ.get("KILO_FALLBACK_MODELS")
        or os.environ.get("NVIDIA_NIM_FALLBACK_MODELS")
        or os.environ.get("NVIDIA_FALLBACK_MODELS")
        or os.environ.get("EXAMSHIELD_AI_FALLBACK_MODELS")
        or "tencent/hy3,kilo-auto/balanced,stepfun/step-3.7-flash:free"
    )
    planner_default = (
        os.environ.get("EXAMSHIELD_AI_PLANNER_DEFAULT_MODEL")
        or os.environ.get("KILO_PLANNER_MODEL")
        or "tencent/hy3:free"
    ).strip()

    return Settings(
        host=os.environ.get("EXAMSHIELD_AI_HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT") or os.environ.get("EXAMSHIELD_AI_PORT", "8790")),
        repo_root=repo_root,
        upload_root=upload_root,
        registry_path=registry_path,
        api_key=(
            os.environ.get("KILO_API_KEY")
            or os.environ.get("NVIDIA_API_KEY")
            or os.environ.get("NVIDIA_NIM_API_KEY")
            or os.environ.get("NIM_API_KEY")
            or ""
        ).strip(),
        model=model,
        fallback_models=fallback_models,
        planner_model=(
            os.environ.get("KILO_PLANNER_MODEL")
            or os.environ.get("NVIDIA_NIM_PLANNER_MODEL")
            or os.environ.get("EXAMSHIELD_AI_PLANNER_MODEL")
            or os.environ.get("NVIDIA_PLANNER_MODEL")
            or os.environ.get("NIM_PLANNER_MODEL")
            or planner_default
        ).strip(),
        base_url=(
            os.environ.get("KILO_BASE_URL")
            or os.environ.get("NVIDIA_NIM_BASE_URL")
            or os.environ.get("NVIDIA_BASE_URL")
            or os.environ.get("NIM_BASE_URL")
            or "https://api.kilo.ai/api/gateway"
        ).rstrip("/"),
        planner_timeout_seconds=float(os.environ.get("EXAMSHIELD_TOOL_PLANNER_TIMEOUT_SECONDS", "5")),
        stream_timeout_seconds=float(os.environ.get("EXAMSHIELD_AI_STREAM_TIMEOUT_SECONDS", "25")),
        chat_max_tokens=int(os.environ.get("EXAMSHIELD_AI_CHAT_MAX_TOKENS", "350")),
        planner_max_tokens=int(os.environ.get("EXAMSHIELD_AI_PLANNER_MAX_TOKENS", "120")),
        list_cache_ttl_seconds=float(os.environ.get("EXAMSHIELD_LIST_CACHE_TTL_SECONDS", "8")),
        supabase_timeout_seconds=float(os.environ.get("EXAMSHIELD_SUPABASE_TIMEOUT_SECONDS", "20")),
        detect_threshold=float(os.environ.get("EXAMSHIELD_DETECT_THRESHOLD", "7")),
        cors_origin=os.environ.get("EXAMSHIELD_AI_CORS_ORIGIN", "*"),
        max_upload_bytes=int(os.environ.get("EXAMSHIELD_MAX_UPLOAD_BYTES", str(12 * 1024 * 1024))),
        supabase_url=(os.environ.get("SUPABASE_URL") or "").rstrip("/"),
        supabase_service_role_key=(
            os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
            or os.environ.get("SUPABASE_SERVICE_KEY")
            or ""
        ).strip(),
        supabase_document_table=os.environ.get("EXAMSHIELD_SUPABASE_DOCUMENT_TABLE", "examshield_documents"),
        supabase_storage_bucket=os.environ.get("EXAMSHIELD_SUPABASE_STORAGE_BUCKET", "evidence-files"),
        public_url=(os.environ.get("EXAMSHIELD_PUBLIC_URL") or "").rstrip("/"),
               telegram_bot_token=(os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip(),
        telegram_webhook_secret=(os.environ.get("TELEGRAM_WEBHOOK_SECRET") or "").strip(),
        telegram_chat_id=(os.environ.get("TELEGRAM_CHAT_ID") or "").strip(),
        telegram_admin_chat_id=(os.environ.get("TELEGRAM_ADMIN_CHAT_ID") or "").strip(),
        api_auth_secret=(os.environ.get("EXAMSHIELD_API_AUTH_SECRET") or "").strip(),
        llm_daily_token_budget=int(os.environ.get("EXAMSHIELD_LLM_DAILY_TOKEN_BUDGET", "0")),
        llm_budget_window_seconds=int(os.environ.get("EXAMSHIELD_LLM_BUDGET_WINDOW_SECONDS", "86400")),
        llm_retry_attempts=int(os.environ.get("EXAMSHIELD_AI_LLM_RETRY_ATTEMPTS", "2")),
        llm_retry_backoff_seconds=float(os.environ.get("EXAMSHIELD_AI_LLM_RETRY_BACKOFF_SECONDS", "0.5")),
        budget_per_request_tokens=int(os.environ.get("EXAMSHIELD_AI_BUDGET_PER_REQUEST_TOKENS", "4000")),
        budget_per_session_tokens=int(os.environ.get("EXAMSHIELD_AI_BUDGET_PER_SESSION_TOKENS", "50000")),
    )


def _split_csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in str(value or "").split(",") if item.strip())
