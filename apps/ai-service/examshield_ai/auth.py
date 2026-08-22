from __future__ import annotations

import hmac
from typing import Any

# Backend shared-secret gate between the Vercel frontend proxy and the Render
# backend. The frontend sends `X-Examshield-Api-Key` on every upstream call; an
# `Authorization: Bearer <secret>` is also accepted. Enforced only when a secret
# is configured — when it is empty the gate is disabled (dev/offline).
API_AUTH_HEADER = "X-Examshield-Api-Key"

# Routes that must never require the backend secret:
#  - /health is the Render health check.
#  - /telegram/webhook and /telegram/events are called directly by Telegram's
#    servers and carry their own TELEGRAM_WEBHOOK_SECRET validation.
API_AUTH_EXEMPT = {"/health", "/", "/telegram/webhook", "/telegram/events"}


def is_path_exempt(path: str) -> bool:
    """Return True if *path* must never require the backend shared secret."""
    return path in API_AUTH_EXEMPT


def _bearer_secret(authorization: str | None) -> str | None:
    if not authorization:
        return None
    authorization = authorization.strip()
    if authorization.lower().startswith("bearer "):
        token = authorization[len("bearer "):].strip()
        return token or None
    return None


def is_authorized(headers: Any, secret: str, path: str) -> bool:
    """Decide whether a request may proceed.

    - No secret configured -> auth disabled (offline/dev parity).
    - Exempt path -> always allowed.
    - Otherwise the request must carry the matching shared secret, compared in
      constant time to avoid leaking the secret via timing.
    """
    if not secret:
        return True
    if is_path_exempt(path):
        return True
    provided = headers.get(API_AUTH_HEADER) or _bearer_secret(headers.get("Authorization"))
    return bool(provided) and hmac.compare_digest(provided, secret)
