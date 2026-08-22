from __future__ import annotations

from examshield_ai.store import EvidenceStore, UploadedFile


def _make_image_upload(name: str) -> UploadedFile:
    data = bytes([0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01])
    return UploadedFile(filename=name, content_type="image/jpeg", data=data)


def _upload(store: EvidenceStore, name: str, owner_id: str) -> None:
    store.create_evidence(_make_image_upload(name), owner_id=owner_id)


def test_list_evidence_scopes_every_collection_to_owner(store) -> None:
    _upload(store, "a.jpg", "owner-A")
    _upload(store, "b.jpg", "owner-B")

    a = store.list_evidence(owner_id="owner-A")
    b = store.list_evidence(owner_id="owner-B")

    assert [e["evidenceId"] for e in a["evidence"]] != [e["evidenceId"] for e in b["evidence"]]
    assert all(e.get("ownerId") == "owner-A" for e in a["evidence"])
    assert all(e.get("ownerId") == "owner-B" for e in b["evidence"])

    # Memory and every child collection must follow the parent evidence scope.
    a_ids = {e["evidenceId"] for e in a["evidence"]}
    b_ids = {e["evidenceId"] for e in b["evidence"]}
    for collection in (
        "jobs",
        "attributions",
        "watermarks",
        "forensicReports",
        "telegramEvents",
        "alerts",
    ):
        assert all(item["evidenceId"] in a_ids for item in a[collection])
        assert all(item["evidenceId"] in b_ids for item in b[collection])


def test_list_evidence_unscoped_is_explicit_system_view(store) -> None:
    _upload(store, "a.jpg", "owner-A")
    _upload(store, "b.jpg", "owner-B")

    # owner_id=None is the internal/system view (local single-user/offline) and
    # must NOT be used for authenticated dashboards.
    assert len(store.list_evidence()["evidence"]) == 2
    assert len(store.list_evidence(owner_id="owner-A")["evidence"]) == 1


def test_get_bundle_is_owner_scoped(store) -> None:
    created = store.create_evidence(_make_image_upload("a.jpg"), owner_id="owner-A")
    evidence_id = created["evidence"]["evidenceId"]
    assert store.get_bundle(evidence_id, owner_id="owner-A") is not None
    assert store.get_bundle(evidence_id, owner_id="owner-B") is None
