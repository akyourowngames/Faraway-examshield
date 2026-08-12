"""Latency benchmark for the chat planning step.

The audit (§5/§11.2) flagged that every `/chat` turn ran `ToolPlanner.plan`
(an LLM call, `EXAMSHIELD_TOOL_PLANNER_TIMEOUT_SECONDS=4`). That path is gone:
`ChatSession.run` now uses the zero-LLM `classify_turn_intent` heuristic (memoised)
to decide whether to attach tool schemas. This script measures the cost of that
step on this machine.
"""

from __future__ import annotations

import statistics
import time
from types import SimpleNamespace

from examshield_ai.chat import ChatSession
from examshield_ai.turn_policy import (
    classify_turn_intent,
    clear_turn_intent_cache,
)

GREETINGS = ["hi", "hello", "hey there", "thanks!", "goodbye", "how are you?"]
DATA = [
    "show me recent evidence",
    "generate a report",
    "what threats are active",
    "list compromised papers",
    "get details on EV-001",
]


class _BenchClient:
    def __init__(self) -> None:
        self.configured = True
        self.settings = SimpleNamespace(model="bench", chat_max_tokens=64)
        self.calls = 0

    def stream_chat(self, **kwargs):
        self.calls += 1
        kwargs["on_token"]("ok")
        return True


class _BenchRegistry:
    def schemas(self):
        return [{"type": "function", "function": {"name": "listEvidence"}}]

    def execute(self, name, arguments):
        return SimpleNamespace(result={"tool": name, "summary": "x", "metrics": []}, model_context="{}")


def _bench_classify(n: int = 5000):
    clear_turn_intent_cache()
    cold = []
    for p in GREETINGS + DATA:
        t0 = time.perf_counter()
        classify_turn_intent(p)
        cold.append((time.perf_counter() - t0) * 1000)

    warm = []
    for i in range(n):
        p = GREETINGS[i % len(GREETINGS)]
        t0 = time.perf_counter()
        classify_turn_intent(p)
        warm.append((time.perf_counter() - t0) * 1000)

    return statistics.mean(cold), statistics.mean(warm), max(warm), classify_turn_intent.cache_info()


def _bench_run_planning():
    """Time the planning decision inside a real ChatSession.run for a greeting
    (no tools) vs a live-data query (tools attached)."""
    greeting_t, data_t = [], []
    for _ in range(200):
        client = _BenchClient()
        session = ChatSession(client=client, registry=_BenchRegistry(), write=lambda e: None)
        t0 = time.perf_counter()
        session.run("hi", [], None)
        greeting_t.append((time.perf_counter() - t0) * 1000)

        client = _BenchClient()
        session = ChatSession(client=client, registry=_BenchRegistry(), write=lambda e: None)
        t0 = time.perf_counter()
        session.run("show me recent evidence", [], None)
        data_t.append((time.perf_counter() - t0) * 1000)

    return statistics.mean(greeting_t), statistics.mean(data_t)


def main() -> None:
    cold, warm, warm_max, info = _bench_classify()
    greet_run, data_run = _bench_run_planning()

    print("=== Chat planning-step latency (replaces old ToolPlanner.plan) ===")
    print(f"classify_turn_intent  cold (unique prompts) : {cold:.4f} ms avg")
    print(f"classify_turn_intent  warm (cache hits)     : {warm:.5f} ms avg  (max {warm_max:.5f} ms)")
    print(f"ChatSession.run       greeting (no tools)   : {greet_run:.4f} ms avg")
    print(f"ChatSession.run       live-data query      : {data_run:.4f} ms avg")
    print(f"memo cache info                            : {info}")
    print()
    print("OLD path (historical): 1 LLM round-trip per /chat turn,")
    print("  EXAMSHIELD_TOOL_PLANNER_TIMEOUT_SECONDS=4  -> up to ~4000 ms/turn + token cost.")
    print("NEW path            : zero-LLM regex + memo  -> sub-millisecond; no network, no tokens.")


if __name__ == "__main__":
    main()
