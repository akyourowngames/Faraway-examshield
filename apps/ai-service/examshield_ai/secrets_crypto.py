"""App-level envelope encryption for secrets stored at rest.

Issue 2.3 (audit): agent LLM API keys were persisted in plaintext in the
``agent_llm_configs`` collection (both the local-JSON fallback and the Supabase
document bag). A single database read or backup leak exposed third-party
provider credentials.

This module encrypts those secrets before they are written and decrypts them
only when the backend actually calls the provider. The plaintext value is never
returned to API clients (the server already strips ``apiKeyEncrypted`` from
responses).

Encryption uses :class:`cryptography.fernet.Fernet` (AES-128-CBC + HMAC-SHA256,
authenticated). The key is a *master key* supplied via ``EXAMSHIELD_AI_MASTER_KEY``
and must live outside the database (e.g. a Render secret). If the variable is
unset we fall back to a built-in development key and log a loud warning — this
keeps local/dev runs working and still converts plaintext-at-rest into
ciphertext-at-rest, but it is NOT secure for production.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

# Built-in fallback only used when EXAMSHIELD_AI_MASTER_KEY is unset. Deliberately
# a constant so decryption is stable across restarts within a dev process.
_DEV_MASTER_KEY_SOURCE = b"examshield-dev-only-master-key-DO-NOT-USE-IN-PROD"

_MASTER_KEY_ENV = "EXAMSHIELD_AI_MASTER_KEY"


def _resolve_master_key(master_key: str | None) -> bytes:
    """Return a Fernet-compatible 32-byte key from ``master_key``.

    Accepts either a ready-made Fernet key or an arbitrary passphrase (which is
    derived into a key via SHA-256). When ``master_key`` is empty/None the
    insecure development key is used instead, with a warning.
    """
    if master_key:
        try:
            Fernet(master_key.encode())
            return master_key.encode()
        except Exception:  # noqa: BLE001 - any non-Fernet input is treated as a passphrase
            digest = hashlib.sha256(master_key.encode()).digest()
            return base64.urlsafe_b64encode(digest)

    logger.warning(
        "EXAMSHIELD_AI_MASTER_KEY is not set; using an INSECURE built-in "
        "development key to encrypt secrets at rest. Set EXAMSHIELD_AI_MASTER_KEY "
        "in production so agent LLM keys are protected by a secret that is NOT "
        "stored in the database."
    )
    digest = hashlib.sha256(_DEV_MASTER_KEY_SOURCE).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_secret(plaintext: str, master_key: str | None = None) -> str:
    """Encrypt ``plaintext`` for storage. Empty input yields an empty string."""
    if not plaintext:
        return ""
    fernet = Fernet(_resolve_master_key(master_key))
    return fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_secret(ciphertext: str, master_key: str | None = None) -> str:
    """Decrypt ``ciphertext`` back to plaintext.

    Returns the input unchanged when it is not a valid Fernet token. This keeps
    backward compatibility with secrets that were written in plaintext before
    encryption was introduced and avoids crashing on a wrong/unset master key.
    """
    if not ciphertext:
        return ""
    fernet = Fernet(_resolve_master_key(master_key))
    try:
        return fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError):
        return ciphertext


def generate_master_key() -> str:
    """Return a new random Fernet master key (print it, then set the env var)."""
    return Fernet.generate_key().decode("utf-8")


def load_master_key_from_env() -> str | None:
    """Return the configured master key (or ``None`` when unset)."""
    value = os.environ.get(_MASTER_KEY_ENV)
    return value or None
