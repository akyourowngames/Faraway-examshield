"""Tests for the thread-safe sliding-window rate limiter (§4.2)."""
from __future__ import annotations

import threading
import time

from examshield_ai.ratelimit import RateLimiter


class TestRateLimiter:
    """Core rate-limiter behaviour: window, daily cap, thread safety, reset."""

    def test_disabled_always_allows(self):
        """max_requests=0 → unlimited (backward-compatible default)."""
        rl = RateLimiter(max_requests=0)
        for _ in range(100):
            allowed, info = rl.allow("ip-1")
            assert allowed is True
            assert info["remaining"] == -1

    def test_allows_within_window(self):
        rl = RateLimiter(max_requests=3, window_seconds=10)
        assert rl.allow("a")[0] is True
        assert rl.allow("a")[0] is True
        assert rl.allow("a")[0] is True

    def test_blocks_when_window_exceeded(self):
        rl = RateLimiter(max_requests=2, window_seconds=60)
        assert rl.allow("b")[0] is True
        assert rl.allow("b")[0] is True
        allowed, info = rl.allow("b")
        assert allowed is False
        assert info["remaining"] == 0
        assert info["retry_after"] > 0

    def test_window_slides(self):
        rl = RateLimiter(max_requests=1, window_seconds=0.1)
        assert rl.allow("c")[0] is True
        assert rl.allow("c")[0] is False
        time.sleep(0.15)
        assert rl.allow("c")[0] is True  # window expired

    def test_daily_cap(self):
        rl = RateLimiter(max_requests=100, window_seconds=60, max_daily=2)
        assert rl.allow("d")[0] is True
        assert rl.allow("d")[0] is True
        allowed, info = rl.allow("d")
        assert allowed is False
        assert info["daily_remaining"] == 0

    def test_daily_disabled_when_zero(self):
        rl = RateLimiter(max_requests=5, window_seconds=60, max_daily=0)
        for _ in range(10):
            allowed, _ = rl.allow("e")
            # Not blocked by daily (only by window)
            if not allowed:
                break
        else:
            # All 10 allowed (window is 5 but daily is disabled)
            # Actually window blocks at 5, so we get False at 6
            pass
        # Verify daily_remaining is always -1 (disabled)
        _, info = rl.allow("e")
        assert info["daily_remaining"] == -1

    def test_keys_are_isolated(self):
        rl = RateLimiter(max_requests=2, window_seconds=60)
        assert rl.allow("ip-1")[0] is True
        assert rl.allow("ip-2")[0] is True  # different key
        assert rl.allow("ip-1")[0] is True  # second request for ip-1
        assert rl.allow("ip-1")[0] is False  # ip-1 exhausted
        assert rl.allow("ip-2")[0] is True  # ip-2 still has capacity

    def test_reset_clears_state(self):
        rl = RateLimiter(max_requests=1, window_seconds=60)
        assert rl.allow("x")[0] is True
        assert rl.allow("x")[0] is False
        rl.reset("x")
        assert rl.allow("x")[0] is True  # reset worked

    def test_thread_safety(self):
        """Concurrent calls from multiple threads don't corrupt state."""
        rl = RateLimiter(max_requests=50, window_seconds=10)
        results = []
        barrier = threading.Barrier(10)

        def worker():
            barrier.wait()
            for _ in range(20):
                results.append(rl.allow("shared")[0])

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 50 allowed out of 200 total attempts
        assert results.count(True) == 50
        assert results.count(False) == 150

    def test_retry_after_is_positive(self):
        rl = RateLimiter(max_requests=1, window_seconds=10)
        rl.allow("y")
        _, info = rl.allow("y")
        assert info["retry_after"] > 0
        assert info["retry_after"] <= 10
