from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from yai_scout.api.app import create_app
from yai_scout.benchmark.adapters import MockAdapter
from yai_scout.benchmark.dataset import load_dataset, load_tasks
from yai_scout.benchmark.manifest import (
    build_manifest,
    canonical_json,
    config_hash,
    redact,
    result_hash,
)
from yai_scout.benchmark.runner import BenchmarkRunner
from yai_scout.benchmark.scoring import evidence_metrics
from yai_scout.config import Settings
from yai_scout.detector.service import StaleAnswerDetector
from yai_scout.detector.versions import POLICY_VERSION, WEIGHTS_VERSION
from yai_scout.domain.models import (
    AgentAnswer,
    AgentSpec,
    BenchmarkTask,
    BenchSession,
    Claim,
    DetectorReport,
    FreshnessStatus,
    FreshnessVerdict,
    TaskResult,
    TemporalSensitivity,
)
from yai_scout.store import Store


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "_env_file": None,
        "openai_api_key": "",
        "tavily_api_key": "",
        "openai_base_url": "https://api.example.com/v1",
        "llm_model": "model-a",
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def _task(task_id: str = "t1", **overrides: object) -> BenchmarkTask:
    data: dict[str, object] = {
        "id": task_id,
        "question": "q",
        "as_of": "2026-11-01",
        "gold_values": ["1"],
    }
    data.update(overrides)
    return BenchmarkTask.model_validate(data)


def _manifest(**overrides: object):
    params: dict[str, object] = {
        "experiment_id": "exp-1",
        "dataset_version": "v1",
        "tasks": [_task()],
        "agents": [AgentSpec(id="a1", name="A", kind="mock", config={"api_key": "secret-a"})],
        "cfg": _settings(),
        "snapshot_ids": ["s1"],
        "started_at": "2026-11-01T00:00:00Z",
        "policy_version": "p1",
        "weights_version": "w1",
        "agent_timeout_s": 1.0,
        "max_claims": 2,
        "detect_freshness": True,
    }
    params.update(overrides)
    manifest = build_manifest(**params)  # type: ignore[arg-type]
    manifest.config_hash = config_hash(manifest)
    return manifest


def test_canonical_json_is_order_independent():
    assert canonical_json({"b": 1, "a": 2}) == canonical_json({"a": 2, "b": 1})


def test_config_hash_is_deterministic():
    assert _manifest().config_hash == _manifest().config_hash


def test_config_hash_changes_with_model_and_weights():
    assert _manifest(cfg=_settings(llm_model="model-b")).config_hash != _manifest().config_hash
    assert _manifest(weights_version="w2").config_hash != _manifest().config_hash


def test_manifest_redacts_secrets_but_hash_is_sensitive():
    manifest = _manifest()
    dumped = manifest.model_dump_json()
    assert "secret-a" not in dumped
    assert redact({"api_key": "secret-a"})["api_key"].startswith("sha256:")
    changed = _manifest(
        agents=[AgentSpec(id="a1", name="A", kind="mock", config={"api_key": "secret-b"})]
    )
    assert changed.config_hash != manifest.config_hash


def test_credential_change_changes_hash_without_leaking_key():
    changed = _manifest(cfg=_settings(tavily_api_key="real-secret-key"))
    assert changed.config_hash != _manifest().config_hash
    assert "real-secret-key" not in changed.model_dump_json()


def test_result_hash_is_deterministic_and_order_independent():
    first = TaskResult(
        task_id="t1", agent_id="a1", answer=AgentAnswer(text="1"), score=0.5
    )
    second = TaskResult(
        task_id="t2", agent_id="a2", answer=AgentAnswer(text="2"), score=0.7
    )
    assert result_hash([first, second]) == result_hash([second, first])
    changed = first.model_copy(update={"answer": AgentAnswer(text="999")})
    assert result_hash([changed]) != result_hash([first])


def test_hidden_tasks_are_not_in_public_dataset():
    _, tasks = load_dataset()
    hidden_ids = {task.id for task in tasks if task.hidden}
    assert hidden_ids
    public_ids = {task.id for task in load_tasks()}
    assert hidden_ids.isdisjoint(public_ids)
    assert all(task.compromised for task in tasks if task.hidden)


def test_runner_rejects_hidden_task_without_private_context():
    store = Store(":memory:")
    runner = BenchmarkRunner(
        store,
        {"mock_good": MockAdapter("mock_good", "Mock")},
        None,
        cfg=_settings(),
    )
    hidden_id = next(task.id for task in load_dataset()[1] if task.hidden)
    with pytest.raises(ValueError, match="hidden tasks"):
        runner.start(["mock_good"], [hidden_id])
    store.close()


def test_public_api_cannot_read_or_run_hidden_tasks():
    class FakeTavily:
        mode = "fake"
        authenticated = False

        async def aclose(self) -> None:
            return None

    app = create_app(
        settings=_settings(),
        tavily=FakeTavily(),  # type: ignore[arg-type]
        store=Store(":memory:"),
    )
    hidden_id = next(task.id for task in load_dataset()[1] if task.hidden)
    with TestClient(app) as client:
        tasks = client.get("/api/benchmark/tasks").json()["tasks"]
        assert hidden_id not in {task["id"] for task in tasks}
        response = client.post(
            "/api/benchmark/run",
            json={"agent_ids": ["mock_good"], "task_ids": [hidden_id]},
        )
        assert response.status_code == 400


def _report_with_claims() -> DetectorReport:
    stable_claim = Claim(
        id="c1", text="1 mile is 1.609 km", temporal_sensitivity=TemporalSensitivity.STABLE
    )
    sensitive_claim = Claim(
        id="c2", text="price is 10", temporal_sensitivity=TemporalSensitivity.SENSITIVE
    )
    return DetectorReport(
        id="r1",
        answer="a",
        as_of="2026-11-01",
        claims=[stable_claim, sensitive_claim],
        verdicts=[
            FreshnessVerdict(claim_id="c1", status=FreshnessStatus.FRESH),
            FreshnessVerdict(claim_id="c2", status=FreshnessStatus.STALE),
        ],
    )


def test_stable_fact_integrity_only_counts_stable_claims():
    metrics = evidence_metrics(_report_with_claims())
    assert metrics["stable_fact_integrity"] == 1.0


def test_stable_fact_integrity_is_none_without_stable_claims():
    report = _report_with_claims()
    report.claims = [report.claims[1]]
    report.verdicts = [report.verdicts[1]]
    assert evidence_metrics(report)["stable_fact_integrity"] is None


def test_evidence_metrics_legacy_compat_for_missing_sensitivity():
    report = _report_with_claims()
    report.claims[0].temporal_sensitivity = None
    assert evidence_metrics(report)["stable_fact_integrity"] is None


async def test_service_records_actual_versions():
    class FakeTavily:
        mode = "fake"
        authenticated = False

        async def search(self, *args: object, **kwargs: object):
            return [], 0.0

        async def aclose(self) -> None:
            return None

    detector = StaleAnswerDetector(FakeTavily(), as_of="2026-11-01", max_claims=1)
    report = await detector.detect("The price is 10 dollars.")
    assert report.policy_version == POLICY_VERSION
    assert report.weights_version == WEIGHTS_VERSION


def test_legacy_reports_keep_unknown_versions():
    report = DetectorReport(id="legacy", answer="a", as_of="2026-11-01")
    assert report.policy_version == "unknown"
    store = Store(":memory:")
    store.save_detector_report(report)
    loaded = store.get_detector_report("legacy")
    assert loaded is not None
    assert loaded.policy_version == "unknown"
    assert loaded.weights_version == "unknown"
    store.close()


def test_bench_session_is_immutable_after_completion():
    store = Store(":memory:")
    store.create_bench_session(BenchSession(id="b1"))
    store.update_bench_session(
        "b1", status="done", finished_at="2026-11-01T00:00:00Z", result_hash="abc"
    )
    with pytest.raises(ValueError, match="immutable"):
        store.update_bench_session("b1", status="done")
    session = store.get_bench_session("b1")
    assert session is not None
    assert session.result_hash == "abc"
    store.close()


def test_result_hash_mismatch_is_rejected():
    store = Store(":memory:")
    store.create_bench_session(BenchSession(id="b1"))
    store.update_bench_session("b1", result_hash="abc")
    with pytest.raises(ValueError, match="differs"):
        store.update_bench_session("b1", result_hash="def")
    store.close()


def test_store_migrates_legacy_bench_session_table(tmp_path: Path):
    db = tmp_path / "legacy.sqlite3"
    connection = sqlite3.connect(db)
    connection.execute(
        """CREATE TABLE bench_session (
               id TEXT PRIMARY KEY,
               status TEXT NOT NULL,
               config_json TEXT NOT NULL DEFAULT '{}',
               created_at TEXT NOT NULL,
               finished_at TEXT,
               error TEXT
           )"""
    )
    old_session = BenchSession(id="old", status="done", dataset_version="v0")
    connection.execute(
        "INSERT INTO bench_session (id, status, config_json, created_at) VALUES (?, ?, ?, ?)",
        ("old", "done", old_session.model_dump_json(), old_session.created_at),
    )
    connection.commit()
    connection.close()

    store = Store(db)
    session = store.get_bench_session("old")
    assert session is not None
    assert session.dataset_version == "v0"
    assert session.manifest is None
    columns = {
        row["name"] for row in store._conn.execute("PRAGMA table_info(bench_session)")
    }
    assert {"manifest_json", "result_hash", "supersedes"} <= columns
    store.close()


async def _wait_done(store: Store, session_id: str) -> BenchSession:
    for _ in range(100):
        loaded = store.get_bench_session(session_id)
        assert loaded is not None
        if loaded.status != "running":
            return loaded
        await asyncio.sleep(0.02)
    raise AssertionError("session did not finish")


async def test_same_manifest_and_results_are_reproducible():
    store = Store(":memory:")
    runner = BenchmarkRunner(
        store,
        {"mock_good": MockAdapter("mock_good", "Mock")},
        None,
        cfg=_settings(),
        detect_freshness=False,
    )
    first = runner.start(["mock_good"], ["b_tavily_free_credits"])
    done_first = await _wait_done(store, first.id)
    second = runner.start(["mock_good"], ["b_tavily_free_credits"])
    done_second = await _wait_done(store, second.id)
    assert done_first.manifest is not None
    assert done_second.manifest is not None
    assert done_first.manifest.config_hash == done_second.manifest.config_hash
    assert done_first.result_hash == done_second.result_hash
    store.close()


async def test_private_hidden_execution_requires_explicit_context():
    store = Store(":memory:")
    runner = BenchmarkRunner(
        store,
        {"mock_good": MockAdapter("mock_good", "Mock")},
        None,
        cfg=_settings(),
    )
    hidden_id = next(task.id for task in load_dataset()[1] if task.hidden)
    session = runner.start(["mock_good"], [hidden_id], allow_hidden=True)
    loaded = await _wait_done(store, session.id)
    assert loaded.status == "done"
    assert hidden_id in loaded.task_ids
    assert loaded.manifest is not None
    store.close()


async def test_revision_session_records_supersedes():
    store = Store(":memory:")
    runner = BenchmarkRunner(
        store,
        {"mock_good": MockAdapter("mock_good", "Mock")},
        None,
        cfg=_settings(),
        detect_freshness=False,
    )
    first = runner.start(["mock_good"], ["b_tavily_free_credits"])
    await _wait_done(store, first.id)
    revision = runner.start(
        ["mock_good"], ["b_tavily_free_credits"], supersedes=first.id
    )
    loaded = await _wait_done(store, revision.id)
    assert loaded.supersedes == first.id
    assert loaded.id != first.id
    store.close()



