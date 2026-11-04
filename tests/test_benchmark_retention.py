"""Tests for benchmark result uniqueness and TTL pruning."""
from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path

from yai_scout.domain.models import AgentAnswer, BenchSession, TaskResult
from yai_scout.store import Store


def _session(store: Store, session_id: str, *, status: str = "done",
             finished_at: str = "2020-01-01T00:00:00Z") -> None:
    store.create_bench_session(BenchSession(
        id=session_id,
        status=status,  # type: ignore[arg-type]
        agent_ids=["agent"],
        task_ids=["task"],
        dataset_version="test",
        created_at="2020-01-01T00:00:00Z",
        finished_at=finished_at,
    ))


def _result(store: Store, session_id: str, *, task_id: str = "task") -> None:
    store.add_bench_result(session_id, TaskResult(
        task_id=task_id,
        agent_id="agent",
        answer=AgentAnswer(text="answer"),
    ))


def test_benchmark_result_unique_per_cell() -> None:
    store = Store(":memory:")
    _session(store, "b1")
    _result(store, "b1")
    try:
        _result(store, "b1")
    except sqlite3.IntegrityError:
        pass
    else:
        raise AssertionError("duplicate benchmark cell should be rejected")
    assert len(store.list_bench_results("b1")) == 1
    store.close()


def test_prune_removes_only_old_terminal_sessions() -> None:
    store = Store(":memory:")
    _session(store, "old")
    _result(store, "old")
    _session(store, "active", status="running", finished_at=None)
    _result(store, "active")

    dry = store.prune_benchmarks(days=30, dry_run=True)
    assert dry["sessions"] == 1
    assert dry["results"] == 1
    assert store.get_bench_session("old") is not None

    removed = store.prune_benchmarks(days=30)
    assert removed["sessions"] == 1
    assert store.get_bench_session("old") is None
    assert store.get_bench_session("active") is not None
    assert len(store.list_bench_results("old")) == 0
    store.close()


def test_prune_rejects_negative_days() -> None:
    store = Store(":memory:")
    try:
        store.prune_benchmarks(days=-1)
    except ValueError:
        pass
    else:
        raise AssertionError("negative retention days should be rejected")
    store.close()


def test_migration_9_dedupes_legacy_duplicate_results(tmp_path: Path) -> None:
    path = tmp_path / "legacy.sqlite3"
    store = Store(path)
    _session(store, "b1")
    _result(store, "b1")
    # Simulate a pre-migration-9 database: no unique index, version 9 absent.
    store._conn.execute("DROP INDEX IF EXISTS uq_bench_result_cell")
    store._conn.execute("DELETE FROM schema_version WHERE version = 9")
    _result(store, "b1")
    store._conn.commit()
    store.close()

    reopened = Store(path)
    assert len(reopened.list_bench_results("b1")) == 1
    try:
        _result(reopened, "b1")
    except sqlite3.IntegrityError:
        pass
    else:
        raise AssertionError("migration 9 did not install the unique index")
    reopened.close()


def test_prune_parses_non_z_timestamps() -> None:
    store = Store(":memory:")
    _session(store, "old-plus", finished_at="2020-01-01T00:00:00+00:00")
    removed = store.prune_benchmarks(days=30)
    assert removed["sessions"] == 1
    assert removed["skipped"] == 0
    assert store.get_bench_session("old-plus") is None
    store.close()


def test_prune_skips_unparseable_timestamps() -> None:
    store = Store(":memory:")
    _session(store, "bad", finished_at="not-a-date")
    result = store.prune_benchmarks(days=30)
    assert result["sessions"] == 0
    assert result["skipped"] == 1
    assert store.get_bench_session("bad") is not None
    store.close()


def test_prune_writes_audit_before_delete(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite3")
    _session(store, "old")
    _result(store, "old")
    audit_dir = tmp_path / "audit"
    result = store.prune_benchmarks(days=30, audit_dir=audit_dir)
    assert result["sessions"] == 1
    assert result["results"] == 1
    assert result["audit_file"]
    audit_path = audit_dir / str(result["audit_file"])
    assert audit_path.is_file()
    payload = json.loads(audit_path.read_text(encoding="utf-8"))
    assert len(payload["sessions"]) == 1
    assert len(payload["results"]) == 1
    assert store.get_bench_session("old") is None
    store.close()


def test_prune_audit_failure_aborts_delete(tmp_path: Path) -> None:
    store = Store(tmp_path / "db2.sqlite3")
    _session(store, "old")
    audit_dir = tmp_path / "not-a-directory"
    audit_dir.write_text("file", encoding="utf-8")
    try:
        store.prune_benchmarks(days=30, audit_dir=audit_dir)
    except OSError:
        pass
    else:
        raise AssertionError("audit failure should abort pruning")
    assert store.get_bench_session("old") is not None
    store.close()


def test_prune_cleans_old_audit_files(tmp_path: Path) -> None:
    store = Store(tmp_path / "db3.sqlite3")
    audit_dir = tmp_path / "audit"
    audit_dir.mkdir()
    old_audit = audit_dir / "prune_old.json"
    old_audit.write_text("{}", encoding="utf-8")
    old_time = time.time() - 90 * 24 * 3600
    os.utime(old_audit, (old_time, old_time))
    result = store.prune_benchmarks(
        days=30, audit_dir=audit_dir, audit_keep_days=30
    )
    assert result["audit_removed"] == 1
    assert not old_audit.exists()
    store.close()
