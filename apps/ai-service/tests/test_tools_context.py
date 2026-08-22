from __future__ import annotations

import json

import pytest
from examshield_ai.store import EvidenceStore
from examshield_ai.tools import ExamshieldToolRegistry


@pytest.fixture
def registry(store: EvidenceStore) -> ExamshieldToolRegistry:
    return ExamshieldToolRegistry(store)


def test_registry_exposes_core_tools(registry: ExamshieldToolRegistry):
    names = registry.names()

    assert "listEvidence" in names
    assert "listThreats" in names
    assert "searchMemory" in names
    assert registry.schemas(), "schemas should be non-empty"


def test_execute_list_evidence_returns_parseable_answer_context(
    registry: ExamshieldToolRegistry,
):
    execution = registry.execute("listEvidence", {})

    context = json.loads(execution.model_context)
    assert context["tool"] == "listEvidence"
    assert isinstance(context["metrics"], dict)
    assert context["answerRules"], "answer rules must always accompany tool data"
    assert "Use metrics for all totals and counts." in context["answerRules"]


def test_execute_unknown_tool_reports_requested_name_and_available_tools(
    registry: ExamshieldToolRegistry,
):
    execution = registry.execute("doesNotExist", {})

    assert execution.result["tool"] == "doesNotExist"
    assert execution.result["title"] == "TOOL NOT FOUND"
    assert "doesNotExist" in execution.result["summary"]
    context = json.loads(execution.model_context)
    assert all(name in context["metrics"]["Available Tools"] for name in ("listEvidence", "listThreats"))


def test_list_threats_context_carries_posture_and_extra_rules(
    registry: ExamshieldToolRegistry,
):
    execution = registry.execute("listThreats", {})

    context = json.loads(execution.model_context)
    assert context["threatPosture"] == "stable"
    extra = [rule for rule in context["answerRules"] if "registry threats" in rule]
    assert extra, "listThreats must extend the shared answer rules"


def test_planner_context_shape_is_consistent(registry: ExamshieldToolRegistry):
    context = registry.planner_context("EV-001")

    assert context["currentEvidenceId"] == "EV-001"
    assert isinstance(context["recentEvidence"], list)
    assert isinstance(context["openAlerts"], list)


def test_search_memory_requires_a_query(registry: ExamshieldToolRegistry):
    execution = registry.execute("searchMemory", {"query": ""})

    assert "QUERY" in execution.result["title"]
