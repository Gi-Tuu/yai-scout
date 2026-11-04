"""Regression tests for the audit remediation batch."""
from __future__ import annotations

import asyncio

from yai_scout.api.limits import UsageLimiter
from yai_scout.benchmark.dataset import load_tasks
from yai_scout.benchmark.manifest import build_manifest
from yai_scout.benchmark.runner import (
    POLICY_VERSION,
    WEIGHTS_VERSION,
    BenchmarkRunner,
)
from yai_scout.config import Settings
from yai_scout.domain.models import (
    AgentAnswer,
    AgentSpec,
    BenchSession,
    ResearchTask,
)
from yai_scout.pipeline.director import ResearchDirector
from yai_scout.store import Store


class SlowAnswer:
    id = "slow"
    name = "slow"
    description = "slow"

    async def answer(self, task):
        await asyncio.sleep(10)
        return AgentAnswer(text="late")


class FastAnswer:
    id = "fast"
    name = "fast"
    description = "fast"

    async def answer(self, task):
        return AgentAnswer(text="ok")


async def _wait(store: Store, session_id: str) -> BenchSession:
    for _ in range(300):
        loaded = store.get_bench_session(session_id)
        if loaded is not None and loaded.status != "running":
            return loaded
        await asyncio.sleep(0.01)
    raise AssertionError("benchmark did not finish")


async def test_benchmark_shutdown_persists_terminal_state() -> None:
    store = Store(":memory:")
    runner = BenchmarkRunner(
        store, {"slow": SlowAnswer()}, None, detect_freshness=False
    )
    session = runner.start(["slow"], [load_tasks()[0].id], repeats=1)
    await asyncio.sleep(0.02)
    await runner.shutdown()
    loaded = store.get_bench_session(session.id)
    assert loaded is not None
    assert loaded.status == "failed"
    assert loaded.manifest is not None
    assert loaded.manifest.status == "failed"
    store.close()


async def test_runner_dedupes_task_and_agent_ids() -> None:
    store = Store(":memory:")
    runner = BenchmarkRunner(
        store, {"fast": FastAnswer()}, None, detect_freshness=False
    )
    task_id = load_tasks()[0].id
    session = runner.start(["fast", "fast"], [task_id, task_id], repeats=1)
    await _wait(store, session.id)
    loaded = store.get_bench_session(session.id)
    assert loaded is not None
    assert loaded.task_ids == [task_id]
    assert loaded.agent_ids == ["fast"]
    assert len(store.list_bench_results(session.id)) == 1
    store.close()


def test_interrupted_manifest_matches_session_status() -> None:
    store = Store(":memory:")
    task = load_tasks()[0]
    manifest = build_manifest(
        experiment_id="b1",
        dataset_version="test",
        tasks=[task],
        agents=[AgentSpec(id="fast", name="fast", kind="mock")],
        cfg=Settings(_env_file=None),
        snapshot_ids=[],
        started_at="2026-11-04T00:00:00Z",
        policy_version=POLICY_VERSION,
        weights_version=WEIGHTS_VERSION,
        agent_timeout_s=1,
        max_claims=1,
        detect_freshness=False,
        repeats=1,
    )
    store.create_bench_session(BenchSession(
        id="b1", owner_id="u", status="running", agent_ids=["fast"],
        task_ids=[task.id], dataset_version="test", manifest=manifest,
    ))
    store.mark_interrupted_work()
    loaded = store.get_bench_session("b1")
    assert loaded is not None
    assert loaded.status == "failed"
    assert loaded.manifest is not None
    assert loaded.manifest.status == "failed"
    assert loaded.result_hash is None
    store.close()


class SlowTavily:
    mode = "fake"
    authenticated = False

    async def search(self, query: str, **kwargs):
        await asyncio.sleep(0.2)
        return [], 1.0

    async def aclose(self) -> None:
        return None


async def test_research_submit_enforces_capacity_atomically() -> None:
    store = Store(":memory:")
    director = ResearchDirector(
        store, SlowTavily(), Settings(_env_file=None)  # type: ignore[arg-type]
    )
    first = ResearchTask(
        id="task_1", question="first question", as_of="2026-11-01",
    )
    second = ResearchTask(
        id="task_2", question="second question", as_of="2026-11-01",
    )
    assert await director.submit(first, max_active=1) is True
    assert await director.submit(second, max_active=1) is False
    await director.shutdown()
    store.close()


def test_forwarded_for_uses_nearest_trusted_hop() -> None:
    headers = {"x-forwarded-for": "203.0.113.99, 198.51.100.7"}
    assert UsageLimiter.client_key(headers, "127.0.0.1") == "198.51.100.7"


def test_cloudflare_client_ip_headers_take_precedence() -> None:
    headers = {
        "x-forwarded-for": "203.0.113.99, 104.23.160.7, 10.0.0.8",
        "cf-connecting-ip": "198.51.100.7",
    }
    assert UsageLimiter.client_key(headers, "127.0.0.1") == "198.51.100.7"
