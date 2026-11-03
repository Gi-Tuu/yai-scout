# ruff: noqa: E501
"""Offline SQLite FK migration (copy-only).

This script never modifies the source database. It copies it, rebuilds tables
with foreign keys/unique constraints, validates the copy, and only then reports
success. Deployment is a separate, explicitly approved step.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import shutil
import sqlite3
from collections.abc import Iterable
from pathlib import Path

TABLE_DDL = {
    "research_task": """
        CREATE TABLE research_task (
            id TEXT PRIMARY KEY,
            question TEXT NOT NULL,
            as_of TEXT NOT NULL,
            status TEXT NOT NULL,
            owner_id TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            finished_at TEXT,
            error TEXT,
            report_md TEXT,
            stats_json TEXT NOT NULL DEFAULT '{}'
        )
    """,
    "plan": """
        CREATE TABLE plan (
            task_id TEXT PRIMARY KEY REFERENCES research_task(id) ON DELETE CASCADE,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """,
    "source": """
        CREATE TABLE source (
            id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL REFERENCES research_task(id) ON DELETE CASCADE,
            url TEXT NOT NULL,
            canonical_url TEXT NOT NULL,
            domain TEXT NOT NULL,
            title TEXT NOT NULL DEFAULT '',
            published_at TEXT,
            fetched_at TEXT NOT NULL,
            content_hash TEXT NOT NULL DEFAULT '',
            tier INTEGER NOT NULL DEFAULT 3,
            tier_reason TEXT NOT NULL DEFAULT '',
            score REAL NOT NULL DEFAULT 0,
            snippet TEXT NOT NULL DEFAULT '',
            UNIQUE (task_id, canonical_url)
        )
    """,
    "run_event": """
        CREATE TABLE run_event (
            seq INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL REFERENCES research_task(id) ON DELETE CASCADE,
            stage TEXT NOT NULL,
            type TEXT NOT NULL,
            payload_json TEXT NOT NULL DEFAULT '{}',
            ts TEXT NOT NULL
        )
    """,
    "cost_ledger": """
        CREATE TABLE cost_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL REFERENCES research_task(id) ON DELETE CASCADE,
            provider TEXT NOT NULL,
            unit TEXT NOT NULL,
            amount REAL NOT NULL,
            credits REAL NOT NULL DEFAULT 0,
            usd_estimate REAL NOT NULL DEFAULT 0,
            ts TEXT NOT NULL
        )
    """,
    "detector_report": """
        CREATE TABLE detector_report (
            id TEXT PRIMARY KEY,
            owner_id TEXT NOT NULL DEFAULT '',
            answer TEXT NOT NULL,
            as_of TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """,
    "bench_session": """
        CREATE TABLE bench_session (
            id TEXT PRIMARY KEY,
            owner_id TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL,
            config_json TEXT NOT NULL DEFAULT '{}',
            manifest_json TEXT NOT NULL DEFAULT '{}',
            result_hash TEXT,
            supersedes TEXT,
            created_at TEXT NOT NULL,
            finished_at TEXT,
            error TEXT
        )
    """,
    "bench_result": """
        CREATE TABLE bench_result (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL REFERENCES bench_session(id) ON DELETE CASCADE,
            task_id TEXT NOT NULL,
            agent_id TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            score REAL NOT NULL DEFAULT 0,
            UNIQUE (session_id, task_id, agent_id)
        )
    """,
    "anchor": """
        CREATE TABLE anchor (
            id TEXT PRIMARY KEY,
            claim_key TEXT NOT NULL,
            url TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """,
    "anchor_candidate": """
        CREATE TABLE anchor_candidate (
            id TEXT PRIMARY KEY,
            anchor_id TEXT NOT NULL REFERENCES anchor(id) ON DELETE RESTRICT,
            status TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """,
    "anchor_observation": """
        CREATE TABLE anchor_observation (
            id TEXT PRIMARY KEY,
            anchor_id TEXT NOT NULL REFERENCES anchor(id) ON DELETE RESTRICT,
            status TEXT NOT NULL,
            content_changed INTEGER NOT NULL DEFAULT 0,
            observed_hash TEXT NOT NULL DEFAULT '',
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """,
    "anchor_audit": """
        CREATE TABLE anchor_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            anchor_id TEXT NOT NULL,
            related_id TEXT NOT NULL DEFAULT '',
            details_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL
        )
    """,
    "snapshot": """
        CREATE TABLE snapshot (
            id TEXT PRIMARY KEY,
            url TEXT NOT NULL,
            title TEXT NOT NULL DEFAULT '',
            origin TEXT NOT NULL DEFAULT 'live',
            content_hash TEXT NOT NULL DEFAULT '',
            raw_path TEXT NOT NULL DEFAULT '',
            text_path TEXT NOT NULL DEFAULT '',
            published_at TEXT,
            updated_at TEXT,
            fetched_at TEXT NOT NULL,
            tier INTEGER NOT NULL DEFAULT 3,
            notes TEXT NOT NULL DEFAULT ''
        )
    """,
}

COPY_COLUMNS = {
    "research_task": "id, question, as_of, status, owner_id, created_at, finished_at, error, report_md, stats_json",
    "plan": "task_id, payload_json, created_at",
    "source": "id, task_id, url, canonical_url, domain, title, published_at, fetched_at, content_hash, tier, tier_reason, score, snippet",
    "run_event": "seq, task_id, stage, type, payload_json, ts",
    "cost_ledger": "id, task_id, provider, unit, amount, credits, usd_estimate, ts",
    "detector_report": "id, owner_id, answer, as_of, payload_json, created_at",
    "bench_session": "id, owner_id, status, config_json, manifest_json, result_hash, supersedes, created_at, finished_at, error",
    "bench_result": "id, session_id, task_id, agent_id, payload_json, score",
    "anchor": "id, claim_key, url, status, payload_json, created_at",
    "anchor_candidate": "id, anchor_id, status, payload_json, created_at",
    "anchor_observation": "id, anchor_id, status, content_changed, observed_hash, payload_json, created_at",
    "anchor_audit": "id, action, anchor_id, related_id, details_json, created_at",
    "snapshot": "id, url, title, origin, content_hash, raw_path, text_path, published_at, updated_at, fetched_at, tier, notes",
}

INDEX_SQL = (
    "CREATE INDEX idx_source_task ON source(task_id)",
    "CREATE INDEX idx_event_task ON run_event(task_id, seq)",
    "CREATE INDEX idx_bench_result_session ON bench_result(session_id)",
    "CREATE INDEX idx_anchor_claim ON anchor(claim_key)",
    "CREATE INDEX idx_anchor_candidate_anchor ON anchor_candidate(anchor_id)",
    "CREATE INDEX idx_anchor_candidate_status ON anchor_candidate(status)",
    "CREATE INDEX idx_anchor_observation_anchor ON anchor_observation(anchor_id)",
    "CREATE INDEX idx_anchor_audit_anchor ON anchor_audit(anchor_id, id)",
    "CREATE INDEX idx_detector_report_owner ON detector_report(owner_id, created_at)",
    "CREATE INDEX idx_research_task_owner ON research_task(owner_id, created_at)",
    "CREATE INDEX idx_snapshot_url ON snapshot(url, fetched_at)",
    "CREATE INDEX idx_anchor_status ON anchor(status, created_at)",
    "CREATE INDEX idx_bench_session_owner ON bench_session(owner_id, created_at)",
)

ORPHAN_CHECKS = (
    ("source", "task_id", "research_task", "id"),
    ("plan", "task_id", "research_task", "id"),
    ("run_event", "task_id", "research_task", "id"),
    ("cost_ledger", "task_id", "research_task", "id"),
    ("bench_result", "session_id", "bench_session", "id"),
    ("anchor_candidate", "anchor_id", "anchor", "id"),
    ("anchor_observation", "anchor_id", "anchor", "id"),
)


class MigrationError(RuntimeError):
    pass


def _counts(conn: sqlite3.Connection, tables: Iterable[str]) -> dict[str, int]:
    return {
        table: int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        for table in tables
    }


def _orphans(conn: sqlite3.Connection) -> list[dict[str, object]]:
    issues: list[dict[str, object]] = []
    for table, column, parent, parent_id in ORPHAN_CHECKS:
        rows = conn.execute(
            f"SELECT {column} FROM {table} "
            f"WHERE {column} NOT IN (SELECT {parent_id} FROM {parent})"
        ).fetchall()
        for row in rows:
            issues.append(
                {"table": table, "column": column, "value": str(row[column])}
            )
    return issues


def _duplicate_bench_results(conn: sqlite3.Connection) -> list[dict[str, object]]:
    rows = conn.execute(
        """SELECT session_id, task_id, agent_id, COUNT(*) AS n
           FROM bench_result
           GROUP BY session_id, task_id, agent_id HAVING n > 1"""
    ).fetchall()
    return [
        {
            "session_id": row["session_id"],
            "task_id": row["task_id"],
            "agent_id": row["agent_id"],
            "count": row["n"],
        }
        for row in rows
    ]


def migrate_copy(source: Path, target: Path) -> dict[str, object]:
    if not source.is_file():
        raise MigrationError(f"source DB not found: {source}")
    if target.exists():
        raise MigrationError(f"refusing to overwrite target: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)

    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    try:
        before = _counts(conn, TABLE_DDL)
        orphans = _orphans(conn)
        duplicates = _duplicate_bench_results(conn)
        if orphans or duplicates:
            raise MigrationError(
                f"preflight failed: orphans={orphans} duplicate_bench_results={duplicates}"
            )

        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute("BEGIN IMMEDIATE")
        for table, ddl in TABLE_DDL.items():
            conn.execute(f"DROP TABLE IF EXISTS {table}_new")
            conn.execute(ddl.replace(f"CREATE TABLE {table}", f"CREATE TABLE {table}_new", 1))
            columns = COPY_COLUMNS[table]
            conn.execute(
                f"INSERT INTO {table}_new ({columns}) SELECT {columns} FROM {table}"
            )
            conn.execute(f"DROP TABLE {table}")
            conn.execute(f"ALTER TABLE {table}_new RENAME TO {table}")
        for sql in INDEX_SQL:
            conn.execute(sql)
        fk_errors = conn.execute("PRAGMA foreign_key_check").fetchall()
        if fk_errors:
            raise MigrationError(f"foreign_key_check failed: {fk_errors}")
        conn.commit()
        conn.execute("PRAGMA foreign_keys = ON")
        after = _counts(conn, TABLE_DDL)
        if before != after:
            raise MigrationError(f"row count mismatch: before={before} after={after}")
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise MigrationError(f"integrity check failed: {integrity}")
        return {
            "source": str(source),
            "target": str(target),
            "before": before,
            "after": after,
            "orphans": orphans,
            "duplicates": duplicates,
            "foreign_key_check": "ok",
            "integrity": integrity,
        }
    except Exception:
        conn.rollback()
        conn.close()
        target.unlink(missing_ok=True)
        raise
    finally:
        with contextlib.suppress(sqlite3.Error):
            conn.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--target", required=True)
    args = parser.parse_args()
    report = migrate_copy(Path(args.source), Path(args.target))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
