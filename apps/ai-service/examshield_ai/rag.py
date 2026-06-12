from __future__ import annotations

import hashlib
import json
import logging
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200


@dataclass
class RAGConfig:
    supabase_url: str
    supabase_service_role_key: str
    embed_function_url: str = ""


def extract_text_from_pdf(data: bytes) -> str:
    try:
        import subprocess
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name

        try:
            result = subprocess.run(
                ["python", "-c", f"""
import sys
try:
    import fitz
    doc = fitz.open("{tmp_path}")
    text = ""
    for page in doc:
        text += page.get_text()
    print(text)
except ImportError:
    print("")
"""],
                capture_output=True, text=True, timeout=30,
            )
            return result.stdout.strip()
        finally:
            os.unlink(tmp_path)
    except Exception as exc:
        logger.warning("PDF extraction failed: %s", exc)
        return ""


def extract_text_from_file(filename: str, data: bytes, content_type: str) -> str:
    lower = filename.lower()
    if lower.endswith(".txt") or lower.endswith(".md") or content_type.startswith("text/"):
        return data.decode("utf-8", errors="replace")
    if lower.endswith(".pdf") or content_type == "application/pdf":
        return extract_text_from_pdf(data)
    return ""


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[dict[str, Any]]:
    text = re.sub(r"\n{3,}", "\n\n", text.strip())
    if not text:
        return []

    chunks: list[dict[str, Any]] = []
    start = 0
    idx = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]

        if end < len(text):
            last_period = chunk.rfind(".")
            last_newline = chunk.rfind("\n")
            break_at = max(last_period, last_newline)
            if break_at > chunk_size * 0.3:
                chunk = text[start:start + break_at + 1]
                end = start + break_at + 1

        chunk = chunk.strip()
        if chunk:
            content_hash = hashlib.sha256(chunk.encode("utf-8")).hexdigest()[:16]
            chunks.append({
                "index": idx,
                "content": chunk,
                "contentHash": content_hash,
                "startChar": start,
                "endChar": end,
            })
            idx += 1

        start = end - overlap
        if start <= (end - chunk_size) and end >= len(text):
            break

    return chunks


def _embed_via_supabase(texts: list[str], config: RAGConfig) -> list[list[float]]:
    if not config.embed_function_url:
        raise RuntimeError("Embed function URL not configured")

    embeddings: list[list[float]] = []
    for text in texts:
        truncated = text[:8000]
        body = json.dumps({"input": truncated}).encode("utf-8")
        req = urllib.request.Request(
            config.embed_function_url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {config.supabase_service_role_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                data = json.loads(raw)
                emb = data.get("embedding", [])
                if not emb:
                    raise RuntimeError("Empty embedding returned")
                embeddings.append(emb)
        except Exception as exc:
            logger.error("Embedding failed for text chunk: %s", exc)
            raise

    return embeddings


def _supabase_request(
    method: str,
    path: str,
    config: RAGConfig,
    payload: dict[str, Any] | list[Any] | None = None,
) -> Any:
    url = f"{config.supabase_url}/rest/v1{path}"
    headers = {
        "apikey": config.supabase_service_role_key,
        "Authorization": f"Bearer {config.supabase_service_role_key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return json.loads(raw) if raw.strip() else None
    except urllib.error.HTTPError as exc:
        error_body = ""
        try:
            error_body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        logger.error("Supabase request failed: %s %s -> %d: %s", method, path, exc.code, error_body[:500])
        raise RuntimeError(f"Supabase error {exc.code}: {error_body[:200]}") from exc


def ingest_knowledge_source(
    source_id: str,
    agent_id: str,
    files: list[dict[str, Any]],
    config: RAGConfig,
) -> dict[str, Any]:
    all_chunks: list[dict[str, Any]] = []
    total_chars = 0

    for file_info in files:
        filename = file_info.get("filename", "")
        data = file_info.get("data", b"")
        content_type = file_info.get("contentType", "text/plain")

        text = extract_text_from_file(filename, data, content_type)
        if not text:
            logger.warning("No text extracted from %s", filename)
            continue

        total_chars += len(text)
        chunks = chunk_text(text)
        for chunk in chunks:
            chunk["sourceId"] = source_id
            chunk["agentId"] = agent_id
            chunk["filename"] = filename
        all_chunks.extend(chunks)

    if not all_chunks:
        return {"status": "failed", "error": "No text content extracted from uploaded files"}

    try:
        texts = [c["content"] for c in all_chunks]
        embeddings = _embed_via_supabase(texts, config)

        for chunk, embedding in zip(all_chunks, embeddings):
            chunk["embedding"] = embedding
    except Exception as exc:
        logger.error("Embedding pipeline failed: %s", exc)
        return {"status": "failed", "error": f"Embedding failed: {exc}"}

    stored_count = 0
    for chunk in all_chunks:
        embedding = chunk.pop("embedding", None)
        record = {
            "source_id": chunk["sourceId"],
            "agent_id": chunk["agentId"],
            "content": chunk["content"],
            "content_hash": chunk["contentHash"],
            "metadata": {
                "filename": chunk.get("filename", ""),
                "index": chunk.get("index", 0),
                "startChar": chunk.get("startChar", 0),
                "endChar": chunk.get("endChar", 0),
            },
        }
        if embedding:
            record["embedding"] = str(embedding)

        try:
            _supabase_request(
                "POST",
                f"/agent_knowledge_chunks?on_conflict=source_id,content_hash",
                config,
                record,
            )
            stored_count += 1
        except Exception as exc:
            logger.warning("Failed to store chunk: %s", exc)

    _supabase_request(
        "PATCH",
        f"/agent_knowledge_sources?id=eq.{source_id}",
        config,
        {
            "status": "ready",
            "chunk_count": stored_count,
            "total_chars": total_chars,
        },
    )

    return {
        "status": "ready",
        "chunksStored": stored_count,
        "totalChars": total_chars,
    }


def search_agent_knowledge(
    query: str,
    agent_id: str,
    config: RAGConfig,
    match_count: int = 8,
    threshold: float = 0.7,
) -> list[dict[str, Any]]:
    try:
        embeddings = _embed_via_supabase([query], config)
        query_embedding = embeddings[0]
    except Exception as exc:
        logger.error("Query embedding failed: %s", exc)
        return []

    try:
        results = _supabase_request(
            "POST",
            f"/rpc/match_agent_knowledge",
            config,
            {
                "query_embedding": query_embedding,
                "p_agent_id": agent_id,
                "match_threshold": threshold,
                "match_count": match_count,
            },
        )
        return results if isinstance(results, list) else []
    except Exception as exc:
        logger.error("Knowledge search failed: %s", exc)
        return []
