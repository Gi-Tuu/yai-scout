from __future__ import annotations

import asyncio

import pytest

from yai_scout.benchmark.dataset import load_tasks
from yai_scout.benchmark.runner import BenchmarkRunner
from yai_scout.domain.models import AgentAnswer, DetectorReport
from yai_scout.store import Store


class FastAgent:
    def __init__(self, agent_id: str) -> None:
        self.id = agent_id
        self.name = agent_id
        self.description = "fast"

    async def answer(self, task):
        return AgentAnswer(text=f"answer {task.id}")


class CountingDetector:
    def __init__(self) -> None:
        self.active = 0
        self.max_active = 0

    async def detect(self, answer, **kwargs):
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            await asyncio.sleep(0.01)
            return DetectorReport(id="d", answer=answer, as_of=kwargs["as_of"])
        finally:
            self.active -= 1


@pytest.mark.asyncio
async def test_benchmark_detector_budget_is_enforced() -> None:
    store = Store(":memory:")
    detector = CountingDetector()
    tasks = load_tasks()[:2]
    runner = BenchmarkRunner(
        store,
        {"a": FastAgent("a"), "b": FastAgent("b")},
        detector,  # type: ignore[arg-type]
        detect_freshness=True,
        detector_concurrency=1,
    )
    session = runner.start(["a", "b"], [task.id for task in tasks])
    for _ in range(300):
        loaded = store.get_bench_session(session.id)
        if loaded is not None and loaded.status != "running":
            break
        await asyncio.sleep(0.01)
    assert loaded is not None and loaded.status == "done"
    assert detector.max_active == 1
    store.close()
