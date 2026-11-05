from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path

from tests.test_api_hardening import FakeTavily

from yai_scout.api.app import create_app
from yai_scout.api.streams import StreamLimiter
from yai_scout.config import Settings
from yai_scout.store import Store

ROOT = Path(__file__).resolve().parents[1]


def test_benchmark_agents_hides_endpoint_from_public() -> None:
    store = Store(":memory:")
    app = create_app(
        settings=Settings(
            _env_file=None,
            db_path=":memory:",
            scout_mode="benchmark",
            tavily_api_key="",
            openai_api_key="",
            demo_limits_enabled=False,
            admin_token="secret",
            http_agent_url="http://internal.example:9999",
        ),
        store=store,
        tavily=FakeTavily(),  # type: ignore[arg-type]
    )
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        public = client.get("/api/benchmark/agents").json()["agents"]
        external = next(item for item in public if item["id"] == "external_http")
        assert "config" not in external
        assert "internal.example" not in external["description"]
        admin = client.get(
            "/api/benchmark/agents", headers={"Authorization": "Bearer secret"}
        ).json()["agents"]
        external_admin = next(item for item in admin if item["id"] == "external_http")
        assert external_admin["config"]["endpoint"] == "http://internal.example:9999"
    store.close()


def test_stream_release_is_idempotent() -> None:
    limiter = StreamLimiter(max_total=2, max_per_key=1)
    assert limiter.acquire("a")
    limiter.release("a")
    limiter.release("a")
    assert limiter.usage()["active"] == 0


def test_ablation_runs_on_mixed_data(tmp_path: Path) -> None:
    out = tmp_path / "mixed_ablation.json"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_external_ablation.py",
            "--data",
            "benchmarks/external_v2/mixed.jsonl",
            "--variant",
            "full",
            "--out",
            str(out),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert out.exists()


async def test_detector_budget_is_global_across_sessions() -> None:
    from tests.test_benchmark_detector_budget import CountingDetector, FastAgent

    from yai_scout.benchmark.dataset import load_tasks
    from yai_scout.benchmark.runner import BenchmarkRunner

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
    ids = [task.id for task in tasks]
    sessions = [runner.start(["a", "b"], ids), runner.start(["a", "b"], ids)]
    for _ in range(400):
        statuses = [store.get_bench_session(s.id) for s in sessions]
        if all(item is not None and item.status != "running" for item in statuses):
            break
        await asyncio.sleep(0.01)
    assert detector.max_active == 1
    await runner.shutdown()
    store.close()
