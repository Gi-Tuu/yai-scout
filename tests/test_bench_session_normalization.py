from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from yai_scout.domain.models import BenchSession, ExperimentManifest
from yai_scout.store import Store


def _manifest(session_id: str = "b1") -> ExperimentManifest:
    return ExperimentManifest(experiment_id=session_id, dataset_version="v")


def test_create_stores_lifecycle_only_in_columns() -> None:
    store = Store(":memory:")
    store.create_bench_session(BenchSession(
        id="b1", status="running", manifest=_manifest(),
    ))
    row = store._conn.execute(
        "SELECT status, config_json, manifest_json FROM bench_session WHERE id = 'b1'"
    ).fetchone()
    assert row["status"] == "running"
    config = json.loads(row["config_json"])
    manifest = json.loads(row["manifest_json"])
    for field in ("manifest", "status", "finished_at", "error", "result_hash", "supersedes"):
        assert field not in config
    for field in ("status", "finished_at", "result_hash"):
        assert field not in manifest
    loaded = store.get_bench_session("b1")
    assert loaded is not None and loaded.status == "running"
    assert loaded.manifest is not None and loaded.manifest.status == "running"
    assert store.consistency_report() == []
    store.close()


def test_update_and_interrupt_derive_manifest_from_columns() -> None:
    store = Store(":memory:")
    store.create_bench_session(BenchSession(
        id="b1", status="running", manifest=_manifest(),
    ))
    final = _manifest().model_copy(update={"status": "done", "finished_at": "2026-11-01T00:00:00Z"})
    store.update_bench_session(
        "b1",
        status="done",
        finished_at="2026-11-01T00:00:00Z",
        manifest_json=final.model_dump_json(),
    )
    loaded = store.get_bench_session("b1")
    assert loaded is not None and loaded.status == "done"
    assert loaded.manifest is not None and loaded.manifest.status == "done"
    raw = json.loads(
        store._conn.execute(
            "SELECT manifest_json FROM bench_session WHERE id = 'b1'"
        ).fetchone()["manifest_json"]
    )
    assert "status" not in raw and "finished_at" not in raw

    store.create_bench_session(BenchSession(
        id="b2", status="running", manifest=_manifest("b2"),
    ))
    store.mark_interrupted_work()
    interrupted = store.get_bench_session("b2")
    assert interrupted is not None and interrupted.status == "failed"
    assert interrupted.manifest is not None and interrupted.manifest.status == "failed"
    assert store.consistency_report() == []
    store.close()


def test_migration_10_strips_lifecycle_json(tmp_path: Path) -> None:
    db = tmp_path / "legacy.sqlite3"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE bench_session (
            id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            config_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            finished_at TEXT,
            error TEXT
        );
        """
    )
    legacy = BenchSession(
        id="old",
        status="done",
        finished_at="2026-11-01T00:00:00Z",
        manifest=_manifest("old"),
    )
    conn.execute(
        "INSERT INTO bench_session (id, status, config_json, created_at, finished_at) "
        "VALUES (?, ?, ?, ?, ?)",
        ("old", "done", legacy.model_dump_json(), legacy.created_at, legacy.finished_at),
    )
    conn.commit()
    conn.close()

    store = Store(db)
    row = store._conn.execute(
        "SELECT config_json, manifest_json FROM bench_session WHERE id = 'old'"
    ).fetchone()
    config = json.loads(row["config_json"])
    manifest = json.loads(row["manifest_json"])
    assert "manifest" not in config and "status" not in config
    assert "status" not in manifest and "finished_at" not in manifest
    loaded = store.get_bench_session("old")
    assert loaded is not None and loaded.status == "done"
    assert loaded.manifest is not None and loaded.manifest.status == "done"
    assert db.with_name("legacy.sqlite3.pre-v10.bak").is_file()
    store.close()


def test_consistency_flags_legacy_lifecycle_json() -> None:
    store = Store(":memory:")
    store.create_bench_session(BenchSession(id="b1", status="running"))
    store._conn.execute(
        "UPDATE bench_session SET config_json = ? WHERE id = 'b1'",
        (json.dumps({"id": "b1", "status": "running"}),),
    )
    store._conn.commit()
    issues = store.consistency_report()
    assert any(item["field"] == "status" for item in issues)
    store.close()


def test_invalid_config_fails_closed() -> None:
    store = Store(":memory:")
    store.create_bench_session(BenchSession(id="b1", status="running"))
    store._conn.execute(
        "UPDATE bench_session SET config_json = '{' WHERE id = 'b1'"
    )
    store._conn.commit()
    try:
        store.get_bench_session("b1")
    except ValueError as exc:
        assert "config_json" in str(exc)
    else:
        raise AssertionError("invalid config must not produce a synthetic session")
    assert any(item["column"] == "invalid_json" for item in store.consistency_report())
    store.close()


def test_invalid_manifest_fails_closed() -> None:
    store = Store(":memory:")
    store.create_bench_session(BenchSession(
        id="b1", status="running", manifest=_manifest(),
    ))
    store._conn.execute(
        "UPDATE bench_session SET manifest_json = '{' WHERE id = 'b1'"
    )
    store._conn.commit()
    try:
        store.get_bench_session("b1")
    except ValueError as exc:
        assert "manifest_json" in str(exc)
    else:
        raise AssertionError("invalid manifest must not be silently dropped")
    store.close()
