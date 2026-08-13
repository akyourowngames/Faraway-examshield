"""Preventive invisible watermarking for ExamShield paper issuance.

This module is the *inverse* of the leak-detection pipeline: instead of only
*reading* a watermark that a leaked paper already carries, it *mints* a unique,
invisible, tamper-evident watermark per recipient and embeds it into the
document text. When a leak later surfaces, the existing OCR -> ``extract_watermark``
-> attribution flow resolves it to the exact issuing recipient.

The watermark uses zero-width Unicode characters (U+200B, U+200C, U+200D, U+2060)
to encode a token into the document's text layer. It is invisible to readers and
survives digital copying / re-flow / paste (the dominant exam-leak channel:
Telegram / WhatsApp forwards of the file, copy-paste). It does NOT survive a
camera photo of a printed paper -- that is a documented limitation (see the plan).

Token format::

    CPY-<seq>|<paperId>|<recipientRef>|<checksum>

The checksum is a short digest of the rest of the token, so a leaker who edits
the visible document text cannot forge a valid watermark to frame someone else.
"""

from __future__ import annotations

import hashlib
import re

# 2-bit carriers. Keep all four invisible; avoid U+FEFF (BOM normalization risk).
ZW = (chr(0x200B), chr(0x200C), chr(0x200D), chr(0x2060))  # 00, 01, 10, 11
ZW_SET = frozenset(ZW)
# Sentinels are formatting marks distinct from the carriers above, so they never
# appear inside an encoded payload (which would otherwise break span matching).
START = chr(0x200E)  # LEFT-TO-RIGHT MARK (opening marker)
END = chr(0x200F)  # RIGHT-TO-LEFT MARK (closing marker)

ZW_CLASS = "[" + "".join(ZW) + "]"
_TOKEN_RE = re.compile(rf"{START}({ZW_CLASS}+?){END}")
_COPY_RE = re.compile(r"^CPY-\d{4,}$")


def _checksum(payload: str) -> str:
    """Short stable checksum (first 8 hex chars of sha256)."""
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:8]


def build_token(copy_id: str, paper_id: str, recipient_ref: str) -> str:
    """Assemble the watermark token for one issued copy."""
    body = f"{copy_id}|{paper_id}|{recipient_ref}"
    return f"{body}|{_checksum(body)}"


def parse_token(token: str) -> dict | None:
    """Validate + split a token into its fields, or return ``None`` if invalid."""
    if not isinstance(token, str) or token.count("|") != 3:
        return None
    copy_id, paper_id, recipient_ref, checksum = token.split("|")
    if not _COPY_RE.match(copy_id):
        return None
    if _checksum(f"{copy_id}|{paper_id}|{recipient_ref}") != checksum:
        return None
    return {
        "copyId": copy_id,
        "paperId": paper_id,
        "recipientRef": recipient_ref,
        "watermarkId": copy_id,
    }


def encode(token: str) -> str:
    """Encode a token into a string of zero-width carriers."""
    data = token.encode("utf-8")
    out: list[str] = []
    for byte in data:
        for shift in (6, 4, 2, 0):
            out.append(ZW[(byte >> shift) & 0b11])
    return "".join(out)


def decode(payload: str) -> str | None:
    """Decode zero-width carriers back into a token string, or ``None``."""
    if not payload:
        return None
    bits: list[int] = []
    for ch in payload:
        if ch not in ZW_SET:
            return None
        bits.append(ZW.index(ch))
    if len(bits) % 4 != 0:
        return None
    data = bytearray()
    for i in range(0, len(bits), 4):
        byte = (bits[i] << 6) | (bits[i + 1] << 4) | (bits[i + 2] << 2) | bits[i + 3]
        data.append(byte)
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def embed(text: str, token: str, repeat: int = 3) -> str:
    """Embed ``token`` (invisibly) into ``text``.

    The zero-width payload is inserted at the start of the document and after
    each newline (paragraph boundary); ``repeat`` controls how many copies are
    scattered so partial edits / truncation still leave a recoverable watermark.
    """
    payload = START + encode(token) + END
    insertions = payload * repeat
    if not text:
        return insertions
    result = insertions + text
    if "\n" in text:
        result = result.replace("\n", "\n" + insertions)
    return result


def decode_watermark(text: str) -> list[str]:
    """Recover all valid watermark tokens hidden in ``text`` (deduplicated)."""
    if not text:
        return []
    found: list[str] = []
    for raw in _TOKEN_RE.findall(text):
        decoded = decode(raw)
        if decoded is None:
            continue
        if parse_token(decoded) is not None and decoded not in found:
            found.append(decoded)
    return found


def strip_watermark(text: str) -> str:
    """Remove all zero-width watermark carriers from ``text`` (clean view)."""
    cleaned = _TOKEN_RE.sub("", text)
    removal = ZW_SET | {START, END}
    return "".join(ch for ch in cleaned if ch not in removal)
