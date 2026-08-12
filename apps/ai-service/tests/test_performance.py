from __future__ import annotations

import dataclasses
import json

from examshield_ai import ocr as ocr_mod
from examshield_ai.memory import MemoryManager, _item_created_at_or_after
from examshield_ai.ocr import analyze_image
from examshield_ai.ocr_cache import OcrResultCache, _hash_bytes
from examshield_ai.response_cache import ReadResponseCache, cached_get
from examshield_ai.store import EvidenceStore

# ─────────────────────────────────────────────────────────────────────────────
# OCR result cache (audit §5 / §11.1: no caching of identical images)
# ─────────────────────────────────────────────────────────────────────────────

def test_ocr_result_cache_basic_ttl_and_eviction():
    cache = OcrResultCache(max_entries=2, ttl_seconds=0.0)
    cache.put(b"aa", {"status": "completed", "text": "x"})
    assert cache.get(b"aa") == {"status": "completed", "text": "x"}
    # ttl_seconds=0 disables expiry-on-time but still serves within capacity
    assert cache.get(b"bb") is None  # never inserted

    cache.put(b"bb", {"status": "completed", "text": "y"})
    cache.put(b"cc", {"status": "completed", "text": "z"})  # evicts oldest (aa)
    assert cache.get(b"aa") is None
    assert cache.get(b"cc") is not None


def test_ocr_result_cache_expires_after_ttl():
    cache = OcrResultCache(max_entries=10, ttl_seconds=10.0)
    cache.put(b"aa", {"status": "completed"})
    # Force the stored stamp far into the past so it is considered expired.
    cache._store[_hash_bytes(b"aa")] = (-1e9, {"status": "completed"})
    assert cache.get(b"aa") is None


def test_ocr_analyze_image_serves_identical_bytes_from_cache(monkeypatch):
    """Re-running OCR on identical bytes must NOT re-execute the OCR engine."""
    monkeypatch.setattr(ocr_mod, "OCR_CHAIN", ("tesseract",))
    calls = {"n": 0}

    def fake_candidates(path, *, deadline=None):
        calls["n"] += 1
        return [{
            "status": "completed",
            "engine": "tesseract",
            "psm": "6",
            "text": "NEET leaked paper",
            "confidence": 80,
            "qualityScore": 90,
        }]

    monkeypatch.setattr("examshield_ai.ocr.read_ocr_candidates", fake_candidates)
    monkeypatch.setattr("examshield_ai.ocr._OCR_RESULT_CACHE", OcrResultCache(max_entries=10, ttl_seconds=60))

    data = b"\x89PNG fake-image-bytes-for-hashing"
    first = analyze_image(data, ".png")
    second = analyze_image(data, ".png")

    assert first["status"] == "completed"
    assert calls["n"] == 1, "second call with identical bytes must hit the cache"
    assert second == first


# ─────────────────────────────────────────────────────────────────────────────
# HTTP GET response cache + Cache-Control (audit §5: no response caching)
# ─────────────────────────────────────────────────────────────────────────────

def test_read_response_cache_miss_then_hit():
    cache = ReadResponseCache(ttl_seconds=30)
    produced = []

    def producer():
        produced.append(1)
        return {"ok": True, "n": len(produced)}

    assert cached_get(cache, "/evidence", producer) == {"ok": True, "n": 1}
    assert cached_get(cache, "/evidence", producer) == {"ok": True, "n": 1}
    assert produced == [1], "producer must run once within the TTL window"


def test_read_response_cache_ttl_disabled_does_not_cache():
    cache = ReadResponseCache(ttl_seconds=0)
    produced = []

    def producer():
        produced.append(1)
        return {"n": len(produced)}

    cached_get(cache, "/x", producer)
    cached_get(cache, "/x", producer)
    assert len(produced) == 2, "ttl=0 disables caching (producer must run every call)"


# ─────────────────────────────────────────────────────────────────────────────
# Vector memory search time-bound pre-filtering (audit §5: no time bound)
# ─────────────────────────────────────────────────────────────────────────────

def test_item_created_at_or_after_helper():
    old = {"createdAt": "2026-01-01T00:00:00Z"}
    new = {"createdAt": "2026-08-01T00:00:00Z"}
    cutoff = "2026-06-01T00:00:00Z"
    assert _item_created_at_or_after(new, cutoff) is True
    assert _item_created_at_or_after(old, cutoff) is False
    # No filter or unparseable cutoff keeps everything.
    assert _item_created_at_or_after(old, None) is True
    assert _item_created_at_or_after(old, "not-a-date") is True
    # Unparseable item timestamp is kept (never silently dropped).
    assert _item_created_at_or_after({"createdAt": "garbage"}, cutoff) is True


def test_memory_search_filters_local_fallback_by_created_after(tmp_settings, monkeypatch):
    """Local (non-vector) search must drop items created before created_after."""
    store = EvidenceStore(tmp_settings)
    memory = MemoryManager(store)
    assert not memory.vector_enabled

    items = [
        {"id": "1", "content": "neet leak", "createdAt": "2026-01-01T00:00:00Z"},
        {"id": "2", "content": "neet leak exam", "createdAt": "2026-09-01T00:00:00Z"},
    ]
    monkeypatch.setattr(memory, "_list_items", lambda *, limit=100: items)

    recent = memory.search("neet leak", created_after="2026-06-01T00:00:00Z")
    assert [m["id"] for m in recent["matches"]] == ["2"]

    everything = memory.search("neet leak")
    assert {m["id"] for m in everything["matches"]} == {"1", "2"}


def test_memory_search_passes_min_created_at_to_rpc(tmp_settings, monkeypatch):
    """Vector-enabled search must forward min_created_at to the Supabase RPC."""
    settings = dataclasses.replace(
        tmp_settings, supabase_url="https://x.supabase.co", supabase_service_role_key="svc"
    )
    store = EvidenceStore(settings)
    memory = MemoryManager(store)
    assert memory.vector_enabled

    captured = {}

    def fake_supabase_json(method, path, body):
        captured["path"] = path
        captured["body"] = body
        return []

    monkeypatch.setattr(store, "_supabase_json", fake_supabase_json)
    monkeypatch.setattr(memory, "_embed", lambda content: [0.1] * 4)

    memory.search("leak", created_after="2026-06-01T00:00:00Z")
    assert captured["path"].endswith("/rpc/match_examshield_memory")
    assert captured["body"]["min_created_at"] == "2026-06-01T00:00:00Z"


# ─────────────────────────────────────────────────────────────────────────────
# mtime-based directory cache (audit §5: blocking file I/O O(n) per request)
# ─────────────────────────────────────────────────────────────────────────────

def test_dir_cache_skips_reread_when_mtime_unchanged(tmp_settings):
    store = EvidenceStore(tmp_settings)
    store.ensure_storage()
    collection = "records"

    reads = {"n": 0}
    real_uncached = store._read_json_dir_uncached

    def counting(name):
        reads["n"] += 1
        return real_uncached(name)

    store._read_json_dir_uncached = counting

    store._read_json_dir(collection)  # first read -> uncached
    store._read_json_dir(collection)  # mtime unchanged -> served from cache
    assert reads["n"] == 1, "unchanged directory must not be re-scanned"

    # Writing a file changes the directory mtime -> must re-read.
    (store.root / collection / "new.json").write_text(json.dumps({"evidenceId": "E1"}))
    store._read_json_dir(collection)
    assert reads["n"] == 2


def test_dir_mtime_returns_none_for_missing_dir(tmp_settings):
    from examshield_ai.store import _dir_mtime

    assert _dir_mtime(tmp_settings.upload_root / "does-not-exist") is None
