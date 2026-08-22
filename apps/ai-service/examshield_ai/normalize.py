from __future__ import annotations

from typing import Any, Mapping, Optional

# Boundary normalization (audit §6.4).
#
# Client payloads arrive in camelCase (`evidenceId`, `currentEvidenceId`,
# `apiKeyEncrypted`) while a few internal helpers also accept the snake_case
# variants. These helpers read either form so handlers don't have to remember
# which one the caller used — the canonical wire key is camelCase.

Json = Mapping[str, Any]


def normalize_evidence_id(payload: Json) -> str:
    """Return the evidence id from a client payload, accepting either key form."""
    value = payload.get("evidenceId")
    if value is None:
        value = payload.get("evidence_id")
    return str(value or "").strip()


def normalize_current_evidence_id(payload: Json) -> Optional[str]:
    """Return `currentEvidenceId` (if present) from a client payload, else None."""
    value = payload.get("currentEvidenceId")
    if value is None:
        value = payload.get("current_evidence_id")
    if not value:
        return None
    return str(value).strip()


def normalize_api_key(config: Json) -> str:
    """Return the encrypted API key from a client config, accepting either key form."""
    value = config.get("apiKeyEncrypted")
    if value is None:
        value = config.get("api_key_encrypted")
    return str(value or "")
