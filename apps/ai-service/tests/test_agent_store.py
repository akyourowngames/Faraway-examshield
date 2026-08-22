from __future__ import annotations

import pytest
from examshield_ai.store import AgentStore, EvidenceStore


def test_agent_children_require_an_existing_agent(store: EvidenceStore):
    agents = AgentStore(store)

    with pytest.raises(LookupError):
        agents.upsert_llm_config("missing", {"provider": "openai", "apiKey": "secret"})
    with pytest.raises(LookupError):
        agents.create_knowledge_source("missing", {"name": "orphan"})


def test_agent_delete_cascades_and_knowledge_delete_works(store: EvidenceStore):
    agents = AgentStore(store)
    agent = agents.create_agent({"name": "Test Agent"})
    agent_id = agent["id"]
    agents.upsert_llm_config(agent_id, {"provider": "openai", "model": "gpt", "apiKey": "secret"})
    agents.upsert_telegram_config(agent_id, {"botToken": "token"})
    source = agents.create_knowledge_source(agent_id, {"name": "Notes"})
    agents.replace_knowledge_chunks(source["id"], agent_id, [{"content": "exam security procedures"}])
    agents.log_conversation(agent_id, "hello", "hi")

    assert agents.delete_knowledge_source(source["id"])
    assert agents.list_knowledge_sources(agent_id) == []
    assert agents.delete_agent(agent_id)
    assert agents.get_agent(agent_id) is None
    assert agents.get_llm_config(agent_id) is None
    assert agents.get_telegram_config(agent_id) is None
    assert agents.list_conversations(agent_id) == []


def test_local_knowledge_search_returns_matching_chunks(store: EvidenceStore):
    agents = AgentStore(store)
    agent = agents.create_agent({"name": "Knowledge Agent"})
    source = agents.create_knowledge_source(agent["id"], {"name": "Policy"})
    agents.replace_knowledge_chunks(source["id"], agent["id"], [
        {"content": "Watermark verification is required for every question paper."},
        {"content": "Cafeteria opening hours are nine to five."},
    ])

    results = agents.search_knowledge_chunks(agent["id"], "How is watermark verification done?")

    assert results
    assert "Watermark" in results[0]["content"]
