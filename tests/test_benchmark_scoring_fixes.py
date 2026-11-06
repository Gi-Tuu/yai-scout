from __future__ import annotations

import asyncio

from yai_scout.benchmark.dataset import load_tasks
from yai_scout.benchmark.runner import BenchmarkRunner
from yai_scout.benchmark.scoring import (
    composite_score,
    match_gold,
    numeric_accuracy,
    weighted_view,
)
from yai_scout.domain.models import AgentAnswer
from yai_scout.store import Store


def test_unmeasured_freshness_does_not_get_full_credit() -> None:
    measured = composite_score(
        numeric=1.0,
        has_citations=True,
        stale_rate=0.0,
        completed=True,
        cost_usd=0.0,
    )
    unmeasured = composite_score(
        numeric=1.0,
        has_citations=True,
        stale_rate=None,
        completed=True,
        cost_usd=0.0,
    )
    assert unmeasured < measured
    assert weighted_view(
        accuracy=1.0,
        freshness=None,
        stale_rate=None,
        evidence_quality=None,
        completion=1.0,
        cost_usd=0.0,
        latency_s=0.0,
    ) < weighted_view(
        accuracy=1.0,
        freshness=100.0,
        stale_rate=0.0,
        evidence_quality=1.0,
        completion=1.0,
        cost_usd=0.0,
        latency_s=0.0,
    )


def test_currency_and_credit_units_are_not_normalized_away() -> None:
    assert not match_gold("$20", "€20")
    assert not match_gold("1000 credits", "1000")
    assert match_gold("$20", "price $20")
    assert numeric_accuracy(["$20"], "€20") == 0.0


async def test_repeated_runs_average_valid_samples_and_keep_samples() -> None:
    class Flaky:
        id = "flaky"
        name = "flaky"
        description = "flaky"

        def __init__(self) -> None:
            self.calls = 0

        async def answer(self, task):
            self.calls += 1
            if self.calls == 1:
                return AgentAnswer(text="", error="boom")
            return AgentAnswer(text="1000 credits", tokens=1, latency_s=0.1)

    store = Store(":memory:")
    task = next(item for item in load_tasks() if item.id == "b_tavily_free_credits")
    runner = BenchmarkRunner(
        store,
        {"flaky": Flaky()},
        None,
        detect_freshness=False,
    )
    session = runner.start(["flaky"], [task.id], repeats=2)
    for _ in range(300):
        loaded = store.get_bench_session(session.id)
        if loaded is not None and loaded.status != "running":
            break
        await asyncio.sleep(0.01)
    results = store.list_bench_results(session.id)
    assert len(results) == 1
    result = results[0]
    assert result.samples and len(result.samples) == 2
    assert result.success_rate == 0.5
    assert result.score > 0
    store.close()
