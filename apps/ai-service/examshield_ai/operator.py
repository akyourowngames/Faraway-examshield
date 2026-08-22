"""Resolve the operator (logged-in user) identity for the EXAMSHIELD AI chat.

The web chat already forwards the Supabase ``Authorization`` JWT to the AI service
(see ``web/src/lib/api-proxy.ts``), and the Settings page reads the user's name and
email from Supabase Auth client-side. We resolve operator identity with two layers
of fallback so the AI can address the user by name:

1. **Client-sent profile** — the frontend includes ``operator: {name, email, role}``
   in the ``/chat`` body. This is the primary path and reuses the exact data the
   Settings page already shows.
2. **Server JWT fallback** — if no body profile is present, we decode the forwarded
   Supabase JWT by calling ``{supabase_url}/auth/v1/user``. This keeps personalization
   working even if a client forgets to send the profile.

Either path yields a normalized ``OperatorContext`` dict, or ``None`` when no usable
identity is available. All failures are swallowed (logged at warning level) so the
chat never breaks just because identity resolution failed.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any

from .settings import Settings
from .store import JsonObject

logger = logging.getLogger(__name__)

# A normalized operator identity. Always has these three keys; ``name``/``email``
# may be empty strings when the source did not provide them.
OperatorContext = dict[str, str]


def resolve_operator(
    payload: JsonObject | None,
    auth_header: str | None,
    settings: Settings,
) -> OperatorContext | None:
    """Return the normalized operator for this chat turn, or ``None``.

    Priority: body ``operator`` first, then the forwarded Supabase JWT.
    """
    body_operator = _normalize_operator((payload or {}).get("operator"))
    if body_operator is not None:
        return body_operator

    jwt = _extract_bearer(auth_header)
    if jwt and settings.supabase_url and settings.supabase_service_role_key:
        server_operator = _operator_via_jwt(settings, jwt)
        if server_operator is not None:
            return server_operator

    return None


def _normalize_operator(raw: Any) -> OperatorContext | None:
    """Normalize a body-supplied operator dict, or ``None`` if unusable."""
    if not isinstance(raw, dict):
        return None
    name = str(raw.get("name") or "").strip()
    email = str(raw.get("email") or "").strip()
    role = str(raw.get("role") or "Operator").strip() or "Operator"
    if not name and not email:
        return None
    return {"name": name, "email": email, "role": role}


def _extract_bearer(auth_header: str | None) -> str | None:
    if not auth_header:
        return None
    parts = str(auth_header).split(None, 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip() or None
    return None


def _operator_via_jwt(settings: Settings, jwt: str) -> OperatorContext | None:
    """Call Supabase Auth with the user's access token to fetch their profile."""
    url = f"{settings.supabase_url.rstrip('/')}/auth/v1/user"
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {jwt}",
            "apikey": settings.supabase_service_role_key,
            "Accept": "application/json",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=settings.supabase_timeout_seconds) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        logger.warning("Operator JWT resolution failed (HTTP %s).", exc.code)
        return None
    except Exception as exc:  # noqa: BLE001 - identity is best-effort
        logger.warning("Operator JWT resolution failed: %s", exc)
        return None

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Operator JWT resolution returned non-JSON.")
        return None

    user = parsed.get("user") if isinstance(parsed, dict) else None
    if not isinstance(user, dict):
        return None

    email = str(user.get("email") or "").strip()
    metadata = user.get("user_metadata") if isinstance(user.get("user_metadata"), dict) else {}
    name = str((metadata or {}).get("full_name") or "").strip() if isinstance(metadata, dict) else ""
    if not name and not email:
        return None
    return {"name": name, "email": email, "role": "Operator"}
