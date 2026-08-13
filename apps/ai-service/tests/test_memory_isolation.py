from __future__ import annotations

from examshield_ai.memory import MemoryManager

# Two near-identical contents that share enough non-stopword tokens to exceed the
# 0.76 jaccard threshold, so same-owner items correlate. They differ by exactly one
# token (telegram/whatsapp) so their fingerprints differ (two distinct items), while
# a DIFFERENT owner with the same content must NOT correlate with owner A.
LEAK_A = (
    "CS301 midterm examination leaked question paper circulating on telegram "
    "with watermark copy shared in student group"
)
LEAK_B = (
    "CS301 midterm examination leaked question paper circulating on whatsapp "
    "with watermark copy shared in student group"
)
UNRELATED = "Network latency spike observed on worker node during scheduled job"


def test_search_isolated_between_owners(store) -> None:
    manager = MemoryManager(store)
    manager.ingest_manual({"content": LEAK_A}, owner_id="owner-A")
    a_matches = manager.search(LEAK_A, owner_id="owner-A")["matches"]
    b_matches = manager.search(LEAK_A, owner_id="owner-B")["matches"]
    assert any(x.get("ownerId") == "owner-A" for x in a_matches)
    assert not any(x.get("ownerId") == "owner-A" for x in b_matches)


def test_get_memory_scoped_to_owner(store) -> None:
    manager = MemoryManager(store)
    stored = manager.ingest_manual({"content": LEAK_A}, owner_id="owner-A")["item"]
    assert manager.get_memory(stored["id"], owner_id="owner-B") is None
    assert manager.get_memory(stored["id"], owner_id="owner-A") is not None


def test_correlation_stays_within_owner(store) -> None:
    manager = MemoryManager(store)
    a1 = manager.ingest_manual({"content": LEAK_A}, owner_id="owner-A")["item"]
    manager.ingest_manual({"content": LEAK_B}, owner_id="owner-A")  # correlates with A's first
    b1 = manager.ingest_manual({"content": LEAK_A}, owner_id="owner-B")
    assert manager.correlate_item(b1, notify=False, owner_id="owner-B") is None
    assert manager.correlate_item(a1, notify=False, owner_id="owner-A") is not None


def test_alerts_scoped_to_owner(store) -> None:
    manager = MemoryManager(store)
    manager.ingest_manual({"content": LEAK_A}, owner_id="owner-A")
    manager.ingest_manual({"content": LEAK_B}, owner_id="owner-A")  # raises an alert for A
    a_alerts = manager.list_memory_alerts(owner_id="owner-A")
    b_alerts = manager.list_memory_alerts(owner_id="owner-B")
    assert a_alerts and all(a.get("ownerId") == "owner-A" for a in a_alerts)
    assert not b_alerts


def test_offline_single_user_owner_none_sees_all(store) -> None:
    manager = MemoryManager(store)
    manager.ingest_manual({"content": LEAK_A}, owner_id=None)
    manager.ingest_manual({"content": UNRELATED}, owner_id=None)
    # owner_id=None shows every local item; a named (unknown) owner sees nothing.
    assert len(manager._list_items(owner_id=None)) == 2
    assert manager._list_items(owner_id="someone-else") == []
