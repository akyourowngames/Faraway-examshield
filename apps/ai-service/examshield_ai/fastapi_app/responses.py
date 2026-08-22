"""Response + error helpers for the FastAPI transport.

Keeps JSON body shapes and status codes identical to the stdlib handler so the
Vercel proxy, the Next.js dashboard, and the existing tests behave the same.
"""
from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

_UNAUTHORIZED_BODY = {"error": "Unauthorized."}
_FORBIDDEN_BODY = {"error": "Forbidden."}
_PAYLOAD_TOO_LARGE_BODY = {"status": "failed", "error": "Payload too large for this endpoint."}


class Unauthorized(Exception):
    def __init__(self, body: dict[str, str] | None = None) -> None:
        super().__init__()
        self.body = body or _UNAUTHORIZED_BODY


class Forbidden(Exception):
    def __init__(self, body: dict[str, str] | None = None) -> None:
        super().__init__()
        self.body = body or _FORBIDDEN_BODY


class PayloadTooLarge(Exception):
    pass


class RateLimited(Exception):
    def __init__(self, label: str, retry_after: float) -> None:
        super().__init__()
        self.label = label
        self.retry_after = retry_after


def register_error_handlers(app: Any) -> None:
    @app.exception_handler(Unauthorized)
    async def _handle_unauthorized(request: Request, exc: Unauthorized) -> JSONResponse:
        return JSONResponse(
            status_code=401,
            content=exc.body,
            headers={"WWW-Authenticate": 'Bearer realm="examshield-api"'},
        )

    @app.exception_handler(Forbidden)
    async def _handle_forbidden(request: Request, exc: Forbidden) -> JSONResponse:
        return JSONResponse(status_code=403, content=exc.body)

    @app.exception_handler(PayloadTooLarge)
    async def _handle_too_large(request: Request, exc: PayloadTooLarge) -> JSONResponse:
        return JSONResponse(status_code=413, content=_PAYLOAD_TOO_LARGE_BODY)

    @app.exception_handler(RateLimited)
    async def _handle_rate_limited(request: Request, exc: RateLimited) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            content={
                "error": f"Rate limit exceeded for {exc.label}. Retry after {exc.retry_after:.0f}s."
            },
        )


def json_response(
    payload: dict[str, Any],
    *,
    status: int = 200,
    request: Request | None = None,
    cache: bool = True,
) -> JSONResponse:
    """Serialize ``payload`` as JSON, matching the stdlib ``_send_json``."""
    resp = JSONResponse(content=payload, status_code=status)
    if (
        cache
        and request is not None
        and request.method == "GET"
        and request.url.path != "/health"
    ):
        # User-scoped GET responses must never be shared across accounts.
        # `public` allowed the Vercel CDN to cache by URL only (ignoring the
        # auth cookie), serving one user's payload to another within the window.
        resp.headers["Cache-Control"] = "private, no-store"
    return resp
