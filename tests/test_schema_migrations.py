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
    assert versions == [1, 2, 3]
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
    assert versions == [1, 2, 3]
    assert store.get_task("t1") is not None
    store.close()

