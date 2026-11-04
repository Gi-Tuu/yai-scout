from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from yai_scout.api.app import create_app
from yai_scout.api.streams import StreamLimiter
from yai_scout.benchmark.dataset import load_tasks
from yai_scout.benchmark.runner import BenchmarkRunner
from yai_scout.config import Settings
from yai_scout.domain.models import AgentAnswer, Anchor, ResearchTask
from yai_scout.store import Store


class FakeTavily:
    mode = "fake"
    authenticated = False

    async def search(self, *args: object, **kwargs: object):
        return [], 0.0

    async def aclose(self) -> None:
        return None


class FastAgent:
    id = "fast"
    name = "fast"
    description = "fast"

    async def answer(self, task):
        return AgentAnswer(text="ok")


def test_public_benchmark_tasks_hide_gold() -> None:
    store = Store(":memory:")
    app = create_app(
        settings=Settings(
            _env_file=None,
            db_path=":memory:",
            tavily_api_key="",
            openai_api_key="",
            demo_limits_enabled=False,
        ),
        store=store,
        tavily=FakeTavily(),  # type: ignore[arg-type]
    )
    with TestClient(app) as client:
        response = client.get("/api/benchmark/tasks")
        assert response.status_code == 200
        task = response.json()["tasks"][0]
        assert "gold_values" not in task
        assert "expected_claims" not in task
        assert "gold_sources" not in task
        assert "reference_evidence" not in task
    store.close()


def test_unknown_agent_ids_are_rejected() -> None:
    store = Store(":memory:")
    runner = BenchmarkRunner(
        store,
        {"fast": FastAgent()},
        None,
        detect_freshness=False,
    )
    task_id = load_tasks()[0].id
    with pytest.raises(ValueError, match="unknown agent ids"):
        runner.start(["fast", "bogus"], [task_id])
    store.close()


def test_legacy_ownerless_task_is_admin_only() -> None:
    store = Store(":memory:")
    store.create_task(
        ResearchTask(
            id="legacy",
            owner_id="",
            question="legacy private question",
            as_of="2026-11-01",
        )
    )
    app = create_app(
        settings=Settings(
            _env_file=None,
            db_path=":memory:",
            tavily_api_key="",
            openai_api_key="",
            demo_limits_enabled=False,
            admin_token="secret",
        ),
        store=store,
        tavily=FakeTavily(),  # type: ignore[arg-type]
    )
    with TestClient(app) as client:
        assert client.get("/api/research").json()["tasks"] == []
        assert client.get("/api/research/legacy").status_code == 404
        admin = client.get(
            "/api/research", headers={"Authorization": "Bearer secret"}
        )
        assert [item["id"] for item in admin.json()["tasks"]] == ["legacy"]
    store.close()


def test_write_context_rolls_back_on_error() -> None:
    store = Store(":memory:")
    anchor = Anchor(
        id="a",
        claim_key="k",
        claim_key_v2="v",
        claim_key_version=2,
        url="https://example.com",
    )
    store.save_anchor(anchor)
    with pytest.raises(sqlite3.IntegrityError):
        store.save_anchor(anchor)
    assert store._conn.in_transaction is False
    store.close()


def test_stream_limiter_caps_total_and_per_key() -> None:
    limiter = StreamLimiter(max_total=3, max_per_key=2)
    assert limiter.acquire("a")
    assert limiter.acquire("a")
    assert not limiter.acquire("a")
    assert limiter.acquire("b")
    assert not limiter.acquire("c")
    limiter.release("a")
    assert limiter.acquire("c")
    assert limiter.usage()["active"] == 3


def test_proxy_headers_ignored_when_untrusted() -> None:
    from yai_scout.api.limits import UsageLimiter

    headers = {"cf-connecting-ip": "203.0.113.9", "x-forwarded-for": "203.0.113.9"}
    assert UsageLimiter.client_key(headers, "peer", trust_proxy=False) == "peer"
