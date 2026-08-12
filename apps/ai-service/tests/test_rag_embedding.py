from __future__ import annotations

import json
from typing import Any

import pytest
from examshield_ai.rag import RAGConfig, ingest_knowledge_source


@pytest.fixture
def rag_config() -> RAGConfig:
    return RAGConfig(
        supabase_url="https://example.supabase.co",
        supabase_service_role_key="test-key",
        embed_function_url="https://example.supabase.co/functions/v1/embed",
    )


def test_knowledge_chunks_store_embedding_as_real_vector(rag_config: RAGConfig, monkeypatch: pytest.MonkeyPatch):
    """rag.py must insert the embedding as a real vector (list), not a string.

    Storing str(embedding) produces a JSON string like "[0.1, 0.2, ...]" which a
    pgvector(384) column rejects or stores as text, breaking RAG search for
    community agents. The embedding must round-trip as a JSON array.
    """
    fake_embedding = [0.1, 0.2, 0.3, 0.4]

    monkeypatch.setattr(
        "examshield_ai.rag._embed_via_supabase",
        lambda texts, config: [list(fake_embedding) for _ in texts],
    )

    captured: list[dict[str, Any]] = []

    def fake_supabase_request(method, path, config, payload=None):
        if method == "POST" and "agent_knowledge_chunks" in path:
            captured.append(payload)
        return None

    monkeypatch.setattr("examshield_ai.rag._supabase_request", fake_supabase_request)

    result = ingest_knowledge_source(
        source_id="00000000-0000-0000-0000-000000000001",
        agent_id="00000000-0000-0000-0000-000000000002",
        files=[{"filename": "notes.txt", "data": b"Watermark verification is required.", "contentType": "text/plain"}],
        config=rag_config,
    )

    assert result["status"] == "ready"
    assert captured, "expected at least one chunk record to be stored"
    assert len(captured) == result["chunksStored"]

    for record in captured:
        embedding = record["embedding"]
        assert isinstance(embedding, list), (
            f"embedding must be a list (real vector), got {type(embedding).__name__}: {embedding!r}"
        )
        assert embedding == [0.1, 0.2, 0.3, 0.4], "embedding values were altered before storage"

    # The serialized payload must be a JSON array, not a quoted string.
    serialized = json.dumps(captured[0])
    assert '"embedding": [0.1, 0.2, 0.3, 0.4]' in serialized, (
        f"embedding must serialize as a JSON array, got: {serialized}"
    )
