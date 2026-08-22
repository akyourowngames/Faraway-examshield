from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from python_multipart import parse_form

from .store import UploadedFile


def parse_multipart(body: bytes, content_type: str) -> dict[str, str | UploadedFile]:
    """Parse a ``multipart/form-data`` request body into plain fields and files.

    Replaces the stdlib ``cgi.FieldStorage`` parser, which is deprecated in
    Python 3.13+ (audit §8 — Backend Weaknesses, "Validation"). The result maps
    each field name to either a ``str`` (text field) or an ``UploadedFile``
    (file field), matching the previous ``cgi.FieldStorage`` contract.

    Malformed input (missing/unparseable boundary, truncated body, or a
    non-multipart content type) is returned as an empty dict rather than
    raising, so callers can surface a client-safe error.
    """
    if not content_type or "multipart/form-data" not in content_type:
        return {}

    values: dict[str, str | UploadedFile] = {}
    headers = {"Content-Type": content_type.encode("utf-8")}
    stream = io.BytesIO(body)

    def on_field(field: Any) -> None:
        name = (field.field_name or b"").decode("utf-8")
        if name not in values:
            values[name] = (field.value or b"").decode("utf-8")

    def on_file(field: Any) -> None:
        name = (field.field_name or b"").decode("utf-8")
        raw_filename = field.file_name
        filename = raw_filename.decode("utf-8") if isinstance(raw_filename, bytes) else (raw_filename or "")
        # Strip any directory components from the client-supplied filename
        # (defence against path traversal, matching the previous cgi behaviour).
        filename = Path(filename).name
        content_type_inner = field.content_type or "application/octet-stream"
        field.file_object.seek(0)
        data = field.file_object.read()
        if name not in values:
            values[name] = UploadedFile(filename=filename, content_type=content_type_inner, data=data)

    try:
        parse_form(headers, stream, on_field, on_file)
    except Exception:
        # Unparseable boundary or truncated payload -> empty, caller decides.
        return {}
    return values
