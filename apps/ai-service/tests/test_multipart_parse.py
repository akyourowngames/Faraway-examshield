from __future__ import annotations

from examshield_ai.multipart_parse import parse_multipart
from examshield_ai.store import UploadedFile


def _build_multipart(boundary: str, parts: list[tuple[str, bytes, str | None, bytes]]) -> tuple[bytes, str]:
    """Build a multipart/form-data body.

    parts: (name, filename_or_None, content_type_or_None, value)
    """
    b = boundary.encode()
    chunks: list[bytes] = []
    for name, filename, content_type, value in parts:
        chunks.append(b"--" + b)
        disp = f'Content-Disposition: form-data; name="{name}"'
        if filename is not None:
            disp += f'; filename="{filename}"'
        chunks.append(("\r\n" + disp + "\r\n").encode())
        if content_type is not None:
            chunks.append(f"Content-Type: {content_type}\r\n".encode())
        chunks.append(b"\r\n" + value + b"\r\n")
    chunks.append(b"--" + b + b"--\r\n")
    body = b"".join(chunks)
    return body, f"multipart/form-data; boundary={boundary}"


def test_parse_multipart_text_and_file_fields() -> None:
    body, content_type = _build_multipart(
        "----boundary1234",
        [
            ("title", None, None, b"Hello World"),
            ("evidence", "leak.jpg", "image/jpeg", b"\xff\xd8\xff\xe0leakdata"),
        ],
    )

    result = parse_multipart(body, content_type)

    assert result["title"] == "Hello World"
    file_field = result["evidence"]
    assert isinstance(file_field, UploadedFile)
    assert file_field.filename == "leak.jpg"
    assert file_field.content_type == "image/jpeg"
    assert file_field.data == b"\xff\xd8\xff\xe0leakdata"


def test_parse_multipart_returns_empty_for_non_multipart() -> None:
    result = parse_multipart(b"not a multipart body", "application/json")
    assert result == {}


def test_parse_multipart_handles_missing_boundary_gracefully() -> None:
    # multipart content-type but no boundary -> unparseable; must not raise.
    result = parse_multipart(b"garbage", "multipart/form-data")
    assert result == {}


def test_parse_multipart_multiple_text_fields() -> None:
    body, content_type = _build_multipart(
        "----boundary1234",
        [
            ("a", None, None, b"1"),
            ("b", None, None, b"2"),
        ],
    )
    result = parse_multipart(body, content_type)
    assert result == {"a": "1", "b": "2"}
