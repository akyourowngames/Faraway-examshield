from __future__ import annotations

import pytest
from examshield_ai.store import EvidenceStore


def test_add_registry_paper_requires_paper_id(store: EvidenceStore):
    with pytest.raises(ValueError, match="paperId is required"):
        store.add_registry_paper({"exam": "NEET"})


def test_add_registry_paper_rejects_duplicates_with_clear_error(store: EvidenceStore):
    store.add_registry_paper({"paperId": "NEET-2026-DEL-001", "centerCode": "DEL-01"})

    with pytest.raises(LookupError, match="already exists"):
        store.add_registry_paper({"paperId": "NEET-2026-DEL-001"})


def test_monitored_group_removal_reports_consistent_removed_flag(store: EvidenceStore):
    added = store.add_monitored_group("-100777", name="Ops")

    assert added["created"] is True
    assert store.is_monitored_group("-100777") is True

    removed = store.remove_monitored_group("-100777")
    assert removed["removed"] is True

    # Removing again stays idempotent: group remains inactive either way.
    store.remove_monitored_group("-100777")
    assert store.is_monitored_group("-100777") is False

    unknown = store.remove_monitored_group("-100999")
    assert unknown["removed"] is False
