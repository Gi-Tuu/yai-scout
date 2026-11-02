from __future__ import annotations

import sqlite3
from pathlib import Path

from yai_scout.store import Store


def _old_database(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE bench_session (
            id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            config_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL
        );
        CREATE TABLE research_task (
            id TEXT PRIMARY KEY,
            question TEXT NOT NULL,
            as_of TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            finished_at TEXT,
            error TEXT,
            report_md TEXT,
            stats_json TEXT NOT NULL DEFAULT '{}'
        );
        INSERT INTO bench_session (id, status, created_at) VALUES ('b1', 'done', '2026-01-01');
        INSERT INTO research_task (id, question, as_of, status, created_at)
            VALUES ('t1', 'old question', '2026-01-01', 'delivered', '2026-01-01');
        """
    )
    conn.commit()
    conn.close()


def test_migrations_upgrade_old_database_idempotently(tmp_path: Path):
    path = tmp_path / "old.sqlite3"
    _old_database(path)

    store = Store(path)
    columns = {
        row["name"] for row in store._conn.execute("PRAGMA table_info(bench_session)")
    }
    assert {"manifest_json", "result_hash", "supersedes"} <= columns
    task_columns = {
        row["name"] for row in store._conn.execute("PRAGMA table_info(research_task)")
    }
    assert "owner_id" in task_columns
    versions = [
        row["version"] for row in store._conn.execute("SELECT version FROM schema_version")
    ]
    assert versions == [1, 2, 3, 4, 5, 6]
    old_task = store.get_task("t1")
    assert old_task is not None
    assert old_task.question == "old question"
    assert old_task.owner_id == ""
    store.close()

    # Re-open: no duplicate migration rows, data intact.
    store = Store(path)
    versions = [
        row["version"] for row in store._conn.execute("SELECT version FROM schema_version")
    ]
    assert versions == [1, 2, 3, 4, 5, 6]
    assert store.get_task("t1") is not None
    store.close()


def test_migration_backfills_anchor_status_and_owner_columns(tmp_path: Path):
    path = tmp_path / "old_anchor.sqlite3"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE anchor (
            id TEXT PRIMARY KEY,
            claim_key TEXT NOT NULL,
            url TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE detector_report (
            id TEXT PRIMARY KEY,
            answer TEXT NOT NULL,
            as_of TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        INSERT INTO anchor VALUES ('a1', 'k', 'https://example.com',
            '{"id":"a1","claim_key":"k","url":"https://example.com","status":"superseded"}',
            '2025-01-01');
        INSERT INTO detector_report VALUES ('r1', 'a', '2026-11-01', '{}', '2025-01-01');
        """
    )
    conn.commit()
    conn.close()

    store = Store(path)
    anchor_columns = {
        row["name"] for row in store._conn.execute("PRAGMA table_info(anchor)")
    }
    report_columns = {
        row["name"] for row in store._conn.execute("PRAGMA table_info(detector_report)")
    }
    assert "status" in anchor_columns
    assert "owner_id" in report_columns
    session_columns = {
        row["name"] for row in store._conn.execute("PRAGMA table_info(bench_session)")
    }
    assert "owner_id" in session_columns
    anchor = store.get_anchor("a1")
    assert anchor is not None and anchor.status == "superseded"
    store.close()


