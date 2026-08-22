from __future__ import annotations


def allowed_cors_origins(cors_origin: str) -> list[str]:
    """Parse ``EXAMSHIELD_AI_CORS_ORIGIN`` into an allow-list for CORS middleware.

    An empty value returns ``[]`` (no cross-origin access) to preserve the
    fail-closed default. An explicit ``*`` returns ``["*"]``. Commas and
    surrounding whitespace are accepted.
    """
    raw = (cors_origin or "").strip()
    if not raw:
        return []
    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    if "*" in origins:
        return ["*"]
    return origins
