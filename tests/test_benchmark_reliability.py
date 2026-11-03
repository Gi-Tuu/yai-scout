from __future__ import annotations

import asyncio

from yai_scout.benchmark.runner import BenchmarkRunner, FailureInjection
from yai_scout.benchmark.scoring import leaderboard
from yai_scout.domain.models import AgentAnswer
from yai_scout.store import Store


class Adapter:
    def __init__(self, agent_id: str) -> None:
        self.id = agent_id
        self.name = agent_id
        self.description = "test"

    async def answer(self, task):
        return AgentAnswer(
            text=f"{task.question} {task.gold_values[0] if task.gold_values else ''}",
            citations=task.gold_sources[:1],
            latency_s=0.01,
            trace=[{"step": "tool.test", "ok": True}],
        )


async def _wait(store: Store, session_id: str):
    for _ in range(200):
        loaded = store.get_bench_session(session_id)
        if loaded is not None and loaded.status != "running":
            return loaded
        await asyncio.sleep(0.01)
    raise AssertionError("benchmark did not finish")


async def test_repeated_runs_aggregate_stability_and_trace():
    store = Store(":memory:")
    adapter = Adapter("agent")
    runner = BenchmarkRunner(
        store,
        {"agent": adapter},
        detector=None,
        concurrency=1,
        detect_freshness=False,
    )
    session = runner.start(
        ["agent"],
        ["b_tavily_free_credits"],
        repeats=3,
    )
    current = await _wait(store, session.id)
    assert current.status == "done"
    result = store.list_bench_results(session.id)[0]
    assert result.repeats == 3
    assert result.success_rate == 1.0
    assert result.score_std == 0.0
    assert result.trace
    assert any(item.get("step") == "run.started" for item in result.trace)
    assert any(item.get("step") == "score.completed" for item in result.trace)
    assert current.manifest is not None
    assert current.manifest.repeats == 3
    assert leaderboard([result])[0]["samples"] == 3
    store.close()


async def test_failure_injection_marks_runs_failed():
    store = Store(":memory:")
    runner = BenchmarkRunner(
        store,
        {"agent": Adapter("agent")},
        detector=None,
        concurrency=1,
        detect_freshness=False,
    )
    session = runner.start(
        ["agent"],
        ["b_tavily_free_credits"],
        repeats=2,
        failure_injection=FailureInjection(
            enabled=True, rate=1.0, modes=["error"]
        ),
    )
    current = await _wait(store, session.id)
    assert current.status == "done"
    result = store.list_bench_results(session.id)[0]
    assert result.repeats == 2
    assert result.success_rate == 0.0
    assert result.faults == ["error"]
    assert result.error
    assert current.manifest is not None
    assert current.manifest.failure_injection["enabled"] is True
    store.close()


async def test_fault_injection_is_reproducible_across_sessions():
    store = Store(":memory:")
    runner = BenchmarkRunner(
        store,
        {"agent": Adapter("agent")},
        detector=None,
        concurrency=1,
        detect_freshness=False,
    )
    injection = FailureInjection(
        enabled=True, rate=0.5, modes=["error", "empty"]
    )
    first = runner.start(
        ["agent"],
        ["b_tavily_free_credits"],
        repeats=4,
        failure_injection=injection,
    )
    await _wait(store, first.id)
    second = runner.start(
        ["agent"],
        ["b_tavily_free_credits"],
        repeats=4,
        failure_injection=injection,
    )
    await _wait(store, second.id)
    first_result = store.list_bench_results(first.id)[0]
    second_result = store.list_bench_results(second.id)[0]
    assert first_result.faults == second_result.faults
    assert first_result.success_rate == second_result.success_rate
    store.close()
