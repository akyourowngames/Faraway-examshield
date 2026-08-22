"""FastAPI dependency injectors mirroring the stdlib handler's auth + limits.

Each dependency reads ``request.app.state.settings`` / ``request.app.state.core``
and raises an exception from :mod:`responses` on failure.
"""
from __future__ import annotations

from fastapi import Request

from examshield_ai.auth import is_authorized, is_path_exempt

from .responses import PayloadTooLarge, RateLimited, Unauthorized
from .state import AppState


def get_settings(request: Request):
    return request.app.state.settings


def get_core(request: Request) -> AppState:
    return request.app.state.core


def client_ip(request: Request) -> str:
    """Client IP, respecting X-Forwarded-For (first entry)."""
    xff = (request.headers.get("X-Forwarded-For") or "").strip()
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else ""


def backend_secret(request: Request) -> None:
    """Shared-secret gate, honoring ``API_AUTH_EXEMPT``."""
    path = request.url.path
    if is_path_exempt(path):
        return
    settings = request.app.state.settings
    if is_authorized(request.headers, settings.api_auth_secret, path):
        return
    raise Unauthorized()


def rate_limit_ocr(request: Request) -> None:
    limiter = request.app.state.core.ocr_limiter
    if limiter.max_requests <= 0:
        return
    allowed, info = limiter.allow(client_ip(request))
    if not allowed:
        raise RateLimited("OCR", float(info["retry_after"]))


def rate_limit_upload(request: Request) -> None:
    limiter = request.app.state.core.upload_limiter
    if limiter.max_requests <= 0:
        return
    allowed, info = limiter.allow(client_ip(request))
    if not allowed:
        raise RateLimited("upload", float(info["retry_after"]))


def body_size_guard(request: Request) -> None:
    """Reject requests whose declared Content-Length exceeds the server cap (413)."""
    settings = request.app.state.settings
    cap = settings.max_request_body_bytes
    if cap <= 0:
        return
    try:
        length = int(request.headers.get("Content-Length") or "0")
    except ValueError:
        length = 0
    if length > cap:
        raise PayloadTooLarge()
