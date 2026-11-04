"""SQLite 存储层：任务 / 计划 / 来源 / 事件 / 成本。

G0 用同步 sqlite3 + 进程内锁：写少读多、单机演示足够。
后续并发上来后再把热点路径切到 asyncio.to_thread 或连接池。
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .claim_classification import resolve_claim_type
from .claim_keys import claim_key_v2
from .domain.models import (
    Anchor,
    AnchorCandidate,
    AnchorObservation,
    BenchSession,
    CostEntry,
    DetectorReport,
    EvidenceSnapshot,
    ExperimentManifest,
    Plan,
    ResearchTask,
    RunEvent,
    SourceRecord,
    TaskResult,
    TaskStatus,
    utcnow_iso,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS research_task (
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
);
CREATE TABLE IF NOT EXISTS plan (
    task_id TEXT PRIMARY KEY REFERENCES research_task(id) ON DELETE CASCADE,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS source (
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
);
CREATE INDEX IF NOT EXISTS idx_source_task ON source(task_id);
CREATE TABLE IF NOT EXISTS run_event (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL REFERENCES research_task(id) ON DELETE CASCADE,
    stage TEXT NOT NULL,
    type TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    ts TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_event_task ON run_event(task_id, seq);
CREATE TABLE IF NOT EXISTS cost_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL REFERENCES research_task(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    unit TEXT NOT NULL,
    amount REAL NOT NULL,
    credits REAL NOT NULL DEFAULT 0,
    usd_estimate REAL NOT NULL DEFAULT 0,
    ts TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS detector_report (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL DEFAULT '',
    answer TEXT NOT NULL,
    as_of TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS bench_session (
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
);
CREATE TABLE IF NOT EXISTS bench_result (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES bench_session(id) ON DELETE CASCADE,
    task_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    score REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS anchor (
    id TEXT PRIMARY KEY,
    claim_key TEXT NOT NULL,
    claim_key_v2 TEXT NOT NULL DEFAULT '',
    claim_key_version INTEGER NOT NULL DEFAULT 1,
    url TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_anchor_claim ON anchor(claim_key);
CREATE TABLE IF NOT EXISTS anchor_candidate (
    id TEXT PRIMARY KEY,
    anchor_id TEXT NOT NULL REFERENCES anchor(id) ON DELETE RESTRICT,
    status TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_anchor_candidate_anchor ON anchor_candidate(anchor_id);
CREATE INDEX IF NOT EXISTS idx_anchor_candidate_status ON anchor_candidate(status);
CREATE TABLE IF NOT EXISTS anchor_observation (
    id TEXT PRIMARY KEY,
    anchor_id TEXT NOT NULL REFERENCES anchor(id) ON DELETE RESTRICT,
    status TEXT NOT NULL,
    content_changed INTEGER NOT NULL DEFAULT 0,
    observed_hash TEXT NOT NULL DEFAULT '',
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_anchor_observation_anchor ON anchor_observation(anchor_id);
CREATE TABLE IF NOT EXISTS anchor_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL,
    anchor_id TEXT NOT NULL,
    related_id TEXT NOT NULL DEFAULT '',
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_anchor_audit_anchor ON anchor_audit(anchor_id, id);
CREATE TABLE IF NOT EXISTS snapshot (
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
);
CREATE INDEX IF NOT EXISTS idx_bench_result_session ON bench_result(session_id);
CREATE INDEX IF NOT EXISTS idx_snapshot_url ON snapshot(url, fetched_at);
"""


class Store:
    """进程内 SQLite 存储。所有方法线程安全（单写锁 + 自动提交）。"""

    def __init__(self, path: str | Path = ":memory:") -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            if self.path != ":memory:":
                self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.executescript(SCHEMA)
            self._apply_migrations()
            self._conn.commit()
            self._conn.execute("PRAGMA foreign_keys=ON")

    def _apply_migrations(self) -> None:
        """Sequential, idempotent schema migrations with a recorded version."""
        applied = {
            int(row["version"])
            for row in self._conn.execute("SELECT version FROM schema_version")
        }
        migrations = (
            (1, self._ensure_bench_columns),
            (2, self._ensure_task_columns),
            (3, self._ensure_detector_columns),
            (4, self._ensure_anchor_columns),
            (5, self._ensure_bench_owner_column),
            (6, self._sync_bench_config_json),
            (7, self._ensure_claim_key_columns),
            (8, self._refresh_claim_identity),
            (9, self._ensure_bench_result_unique),
        )
        for version, migrate in migrations:
            if version in applied:
                continue
            migrate()
            self._conn.execute(
                "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                (version, utcnow_iso()),
            )

    def _ensure_bench_columns(self) -> None:
        """向后兼容迁移：只加列，不重建表，不删除历史数据。"""
        columns = {
            row["name"] for row in self._conn.execute("PRAGMA table_info(bench_session)")
        }
        additions = {
            "manifest_json": "TEXT NOT NULL DEFAULT '{}'",
            "result_hash": "TEXT",
            "supersedes": "TEXT",
            "finished_at": "TEXT",
            "error": "TEXT",
        }
        for name, decl in additions.items():
            if name not in columns:
                self._conn.execute(
                    f"ALTER TABLE bench_session ADD COLUMN {name} {decl}"
                )

    def _ensure_detector_columns(self) -> None:
        columns = {
            row["name"]
            for row in self._conn.execute("PRAGMA table_info(detector_report)")
        }
        if "owner_id" not in columns:
            self._conn.execute(
                "ALTER TABLE detector_report ADD COLUMN owner_id TEXT NOT NULL DEFAULT ''"
            )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_detector_report_owner "
            "ON detector_report(owner_id, created_at)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_research_task_owner "
            "ON research_task(owner_id, created_at)"
        )

    def _ensure_task_columns(self) -> None:
        columns = {
            row["name"] for row in self._conn.execute("PRAGMA table_info(research_task)")
        }
        if "owner_id" not in columns:
            self._conn.execute(
                "ALTER TABLE research_task ADD COLUMN owner_id TEXT NOT NULL DEFAULT ''"
            )

    def _ensure_claim_key_columns(self) -> None:
        columns = {
            row["name"] for row in self._conn.execute("PRAGMA table_info(anchor)")
        }
        if "claim_key_v2" not in columns:
            self._conn.execute(
                "ALTER TABLE anchor ADD COLUMN claim_key_v2 TEXT NOT NULL DEFAULT ''"
            )
        if "claim_key_version" not in columns:
            self._conn.execute(
                "ALTER TABLE anchor ADD COLUMN claim_key_version INTEGER NOT NULL DEFAULT 1"
            )
        for row in self._conn.execute(
            "SELECT id, claim_key_v2, claim_key_version, payload_json FROM anchor"
        ):
            try:
                payload = Anchor.model_validate_json(row["payload_json"])
            except ValueError:
                continue
            if not payload.claim_text:
                continue
            resolved = resolve_claim_type(payload.claim_text, payload.claim_type)
            v2 = claim_key_v2(payload.claim_text, resolved)
            version = 2
            if (
                row["claim_key_v2"] == v2
                and int(row["claim_key_version"]) == version
                and payload.claim_type is resolved
            ):
                continue
            payload = payload.model_copy(
                update={
                    "claim_key_v2": v2,
                    "claim_key_version": version,
                    "claim_type": resolved,
                }
            )
            self._conn.execute(
                "UPDATE anchor SET claim_key_v2 = ?, claim_key_version = ?, payload_json = ? "
                "WHERE id = ?",
                (v2, version, payload.model_dump_json(), row["id"]),
            )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_anchor_claim_v2 ON anchor(claim_key_v2)"
        )

    def _refresh_claim_identity(self) -> None:
        """Recompute v2 identity with the canonical classifier.

        Migration 7 could not know the shared claim type; migration 8 fixes
        anchors created before the type was persisted in the payload.
        """
        rows = self._conn.execute(
            "SELECT id, payload_json FROM anchor"
        ).fetchall()
        for row in rows:
            try:
                payload = Anchor.model_validate_json(row["payload_json"])
            except ValueError:
                continue
            if not payload.claim_text:
                continue
            resolved = resolve_claim_type(payload.claim_text, payload.claim_type)
            payload = payload.model_copy(
                update={
                    "claim_key_v2": claim_key_v2(payload.claim_text, resolved),
                    "claim_key_version": 2,
                    "claim_type": resolved,
                }
            )
            self._conn.execute(
                "UPDATE anchor SET claim_key_v2 = ?, claim_key_version = ?, "
                "payload_json = ? WHERE id = ?",
                (
                    payload.claim_key_v2,
                    payload.claim_key_version,
                    payload.model_dump_json(),
                    row["id"],
                ),
            )

    def _ensure_bench_result_unique(self) -> None:
        """Deduplicate legacy cells, then enforce one result per task/agent/session."""
        self._conn.execute(
            """DELETE FROM bench_result
               WHERE id NOT IN (
                   SELECT MIN(id) FROM bench_result
                   GROUP BY session_id, task_id, agent_id
               )"""
        )
        self._conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_bench_result_cell "
            "ON bench_result(session_id, task_id, agent_id)"
        )

    def _ensure_bench_owner_column(self) -> None:
        columns = {
            row["name"]
            for row in self._conn.execute("PRAGMA table_info(bench_session)")
        }
        if "owner_id" not in columns:
            self._conn.execute(
                "ALTER TABLE bench_session ADD COLUMN owner_id TEXT NOT NULL DEFAULT ''"
            )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_bench_session_owner "
            "ON bench_session(owner_id, created_at)"
        )

    def _sync_bench_config_json(self) -> None:
        """Backfill bench_session.config_json from lifecycle columns."""
        rows = self._conn.execute(
            "SELECT id, status, finished_at, error, config_json FROM bench_session"
        ).fetchall()
        for row in rows:
            try:
                config = json.loads(row["config_json"] or "{}")
            except ValueError:
                continue
            config["status"] = row["status"]
            config["finished_at"] = row["finished_at"]
            config["error"] = row["error"]
            self._conn.execute(
                "UPDATE bench_session SET config_json = ? WHERE id = ?",
                (json.dumps(config, ensure_ascii=False), row["id"]),
            )

    def _ensure_anchor_columns(self) -> None:
        columns = {
            row["name"] for row in self._conn.execute("PRAGMA table_info(anchor)")
        }
        if "status" not in columns:
            self._conn.execute(
                "ALTER TABLE anchor ADD COLUMN status TEXT NOT NULL DEFAULT 'active'"
            )
        for row in self._conn.execute("SELECT id, payload_json FROM anchor"):
            try:
                status = str(json.loads(row["payload_json"]).get("status") or "active")
            except (TypeError, ValueError):
                status = "active"
            self._conn.execute(
                "UPDATE anchor SET status = ? WHERE id = ?", (status, row["id"])
            )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_anchor_status "
            "ON anchor(status, created_at)"
        )

    def consistency_report(self) -> list[dict[str, str]]:
        """Read-only check: payload columns vs JSON payload, plus orphan rows."""
        issues: list[dict[str, str]] = []

        def add(table: str, row_id: str, field: str, column: str, payload: str) -> None:
            issues.append(
                {
                    "table": table,
                    "id": row_id,
                    "field": field,
                    "column": column,
                    "payload": payload,
                }
            )

        with self._lock:
            for anchor_row in self._conn.execute("SELECT * FROM anchor"):
                try:
                    anchor_payload = Anchor.model_validate_json(anchor_row["payload_json"])
                except ValueError:
                    add(
                        "anchor",
                        anchor_row["id"],
                        "payload",
                        "invalid_json",
                        anchor_row["payload_json"],
                    )
                    continue
                for field in ("claim_key", "claim_key_v2", "claim_key_version", "url", "status"):
                    if str(anchor_row[field]) != str(getattr(anchor_payload, field)):
                        add(
                            "anchor",
                            anchor_row["id"],
                            field,
                            str(anchor_row[field]),
                            str(getattr(anchor_payload, field)),
                        )

            for candidate_row in self._conn.execute("SELECT * FROM anchor_candidate"):
                try:
                    candidate_payload = AnchorCandidate.model_validate_json(
                        candidate_row["payload_json"]
                    )
                except ValueError:
                    add(
                        "anchor_candidate",
                        candidate_row["id"],
                        "payload",
                        "invalid_json",
                        candidate_row["payload_json"],
                    )
                    continue
                if str(candidate_row["anchor_id"]) != candidate_payload.anchor_id:
                    add(
                        "anchor_candidate",
                        candidate_row["id"],
                        "anchor_id",
                        str(candidate_row["anchor_id"]),
                        candidate_payload.anchor_id,
                    )
                if str(candidate_row["status"]) != candidate_payload.accuracy_status:
                    add(
                        "anchor_candidate",
                        candidate_row["id"],
                        "status",
                        str(candidate_row["status"]),
                        candidate_payload.accuracy_status,
                    )

            for report_row in self._conn.execute("SELECT * FROM detector_report"):
                try:
                    report_payload = json.loads(report_row["payload_json"])
                except ValueError:
                    add(
                        "detector_report",
                        report_row["id"],
                        "payload",
                        "invalid_json",
                        report_row["payload_json"],
                    )
                    continue
                for field in ("owner_id", "answer", "as_of"):
                    if str(report_row[field]) != str(report_payload.get(field, "")):
                        add(
                            "detector_report",
                            report_row["id"],
                            field,
                            str(report_row[field]),
                            str(report_payload.get(field, "")),
                        )

            for session_row in self._conn.execute(
                "SELECT id, owner_id, status, config_json FROM bench_session"
            ):
                try:
                    session_payload = json.loads(session_row["config_json"] or "{}")
                except ValueError:
                    add(
                        "bench_session",
                        session_row["id"],
                        "config_json",
                        "invalid_json",
                        session_row["config_json"],
                    )
                    continue
                for field in ("owner_id", "status"):
                    if str(session_row[field]) != str(session_payload.get(field, "")):
                        add(
                            "bench_session",
                            session_row["id"],
                            field,
                            str(session_row[field]),
                            str(session_payload.get(field, "")),
                        )

            orphan_checks = (
                ("source", "task_id", "research_task", "id"),
                ("plan", "task_id", "research_task", "id"),
                ("run_event", "task_id", "research_task", "id"),
                ("bench_result", "session_id", "bench_session", "id"),
                ("anchor_candidate", "anchor_id", "anchor", "id"),
                ("anchor_observation", "anchor_id", "anchor", "id"),
                ("anchor_audit", "anchor_id", "anchor", "id"),
            )
            for table, column, parent, parent_id in orphan_checks:
                rows = self._conn.execute(
                    f"SELECT {column} FROM {table} "
                    f"WHERE {column} NOT IN (SELECT {parent_id} FROM {parent})"
                ).fetchall()
                for orphan_row in rows:
                    issues.append(
                        {
                            "table": table,
                            "id": str(orphan_row[column]),
                            "field": f"orphan_{column}",
                            "column": "",
                            "payload": "",
                        }
                    )
        return issues

    # ------------------------------------------------------------------ lifecycle
    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def ping(self) -> None:
        """Raise when the SQLite connection cannot execute a trivial query."""
        with self._lock:
            self._conn.execute("SELECT 1").fetchone()

    # ------------------------------------------------------------------ tasks
    def create_task(self, task: ResearchTask) -> ResearchTask:
        with self._lock:
            self._conn.execute(
                """INSERT INTO research_task
                   (id, owner_id, question, as_of, status, created_at, stats_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    task.id,
                    task.owner_id,
                    task.question,
                    task.as_of,
                    str(task.status),
                    task.created_at,
                    json.dumps(task.stats, ensure_ascii=False),
                ),
            )
            self._conn.commit()
        return task

    def get_task(self, task_id: str) -> ResearchTask | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM research_task WHERE id = ?", (task_id,)
            ).fetchone()
        return _row_to_task(row) if row else None

    def list_tasks(
        self, limit: int = 20, *, owner_id: str | None = None
    ) -> list[ResearchTask]:
        query = "SELECT * FROM research_task"
        vals: list[Any] = []
        if owner_id is not None:
            query += " WHERE owner_id = ? OR owner_id = ''"
            vals.append(owner_id)
        query += " ORDER BY created_at DESC LIMIT ?"
        vals.append(limit)
        with self._lock:
            rows = self._conn.execute(query, vals).fetchall()
        return [_row_to_task(r) for r in rows]

    def update_task(
        self,
        task_id: str,
        *,
        status: TaskStatus | None = None,
        finished_at: str | None = None,
        error: str | None = None,
        report_md: str | None = None,
        stats: dict[str, Any] | None = None,
    ) -> None:
        sets: list[str] = []
        vals: list[Any] = []
        if status is not None:
            sets.append("status = ?")
            vals.append(str(status))
        if finished_at is not None:
            sets.append("finished_at = ?")
            vals.append(finished_at)
        if error is not None:
            sets.append("error = ?")
            vals.append(error)
        if report_md is not None:
            sets.append("report_md = ?")
            vals.append(report_md)
        if stats is not None:
            sets.append("stats_json = ?")
            vals.append(json.dumps(stats, ensure_ascii=False))
        if not sets:
            return
        vals.append(task_id)
        with self._lock:
            self._conn.execute(f"UPDATE research_task SET {', '.join(sets)} WHERE id = ?", vals)
            self._conn.commit()

    def mark_interrupted_work(self) -> None:
        """Mark tasks/sessions left running by a previous process as failed."""
        error = "interrupted by process restart"
        now = utcnow_iso()
        with self._lock:
            self._conn.execute(
                """UPDATE research_task
                   SET status = 'failed', finished_at = ?, error = ?
                   WHERE status IN ('pending', 'running')""",
                (now, error),
            )
            rows = self._conn.execute(
                "SELECT id, config_json, manifest_json FROM bench_session "
                "WHERE status = 'running'"
            ).fetchall()
            for row in rows:
                config: dict[str, object] = {}
                try:
                    loaded = json.loads(row["config_json"] or "{}")
                    if isinstance(loaded, dict):
                        config = loaded
                except ValueError:
                    config = {}
                config.update({"status": "failed", "finished_at": now, "error": error})
                manifest_json = row["manifest_json"]
                try:
                    manifest = json.loads(manifest_json or "{}")
                except ValueError:
                    manifest = {}
                if isinstance(manifest, dict) and manifest:
                    manifest.update({
                        "status": "failed",
                        "finished_at": now,
                        "result_hash": None,
                    })
                    manifest_json = json.dumps(manifest, ensure_ascii=False)
                self._conn.execute(
                    "UPDATE bench_session SET status = 'failed', finished_at = ?, "
                    "error = ?, config_json = ?, manifest_json = ? WHERE id = ?",
                    (now, error, json.dumps(config, ensure_ascii=False),
                     manifest_json, row["id"]),
                )
            self._conn.commit()

    # ------------------------------------------------------------------ plan
    def save_plan(self, task_id: str, plan: Plan) -> None:
        with self._lock:
            self._conn.execute(
                """INSERT INTO plan (task_id, payload_json, created_at) VALUES (?, ?, ?)
                   ON CONFLICT(task_id) DO UPDATE SET
                   payload_json = excluded.payload_json, created_at = excluded.created_at""",
                (task_id, plan.model_dump_json(), utcnow_iso()),
            )
            self._conn.commit()

    def get_plan(self, task_id: str) -> Plan | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT payload_json FROM plan WHERE task_id = ?", (task_id,)
            ).fetchone()
        return Plan.model_validate_json(row["payload_json"]) if row else None

    # ------------------------------------------------------------------ sources
    def add_source(self, source: SourceRecord) -> bool:
        """插入来源；同一 task 下 canonical_url 重复则忽略。返回是否新增。"""
        with self._lock:
            cur = self._conn.execute(
                """INSERT OR IGNORE INTO source
                   (id, task_id, url, canonical_url, domain, title, published_at,
                    fetched_at, content_hash, tier, tier_reason, score, snippet)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    source.id,
                    source.task_id,
                    source.url,
                    source.canonical_url,
                    source.domain,
                    source.title,
                    source.published_at,
                    source.fetched_at,
                    source.content_hash,
                    source.tier,
                    source.tier_reason,
                    source.score,
                    source.snippet,
                ),
            )
            self._conn.commit()
            return cur.rowcount > 0

    def list_sources(self, task_id: str) -> list[SourceRecord]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM source WHERE task_id = ? ORDER BY tier ASC, score DESC",
                (task_id,),
            ).fetchall()
        return [_row_to_source(r) for r in rows]

    def count_sources(self, task_id: str) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) AS n FROM source WHERE task_id = ?", (task_id,)
            ).fetchone()
        return int(row["n"])

    # ------------------------------------------------------------------ events
    def append_event(self, event: RunEvent) -> RunEvent:
        with self._lock:
            cur = self._conn.execute(
                """INSERT INTO run_event (task_id, stage, type, payload_json, ts)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    event.task_id,
                    str(event.stage),
                    event.type,
                    json.dumps(event.payload, ensure_ascii=False),
                    event.ts,
                ),
            )
            self._conn.commit()
            seq = int(cur.lastrowid or 0)
        return event.model_copy(update={"seq": seq})

    def list_events(self, task_id: str, after_seq: int = 0, limit: int = 1000) -> list[RunEvent]:
        with self._lock:
            rows = self._conn.execute(
                """SELECT * FROM run_event WHERE task_id = ? AND seq > ?
                   ORDER BY seq ASC LIMIT ?""",
                (task_id, after_seq, limit),
            ).fetchall()
        return [_row_to_event(r) for r in rows]

    # ------------------------------------------------------------------ cost
    def add_cost(self, entry: CostEntry) -> CostEntry:
        with self._lock:
            cur = self._conn.execute(
                """INSERT INTO cost_ledger
                   (task_id, provider, unit, amount, credits, usd_estimate, ts)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    entry.task_id,
                    entry.provider,
                    entry.unit,
                    entry.amount,
                    entry.credits,
                    entry.usd_estimate,
                    entry.ts,
                ),
            )
            self._conn.commit()
            return entry.model_copy(update={"id": int(cur.lastrowid or 0)})

    def cost_sum(self, task_id: str) -> tuple[float, float]:
        with self._lock:
            row = self._conn.execute(
                """SELECT COALESCE(SUM(credits), 0) AS credits,
                          COALESCE(SUM(usd_estimate), 0) AS usd
                   FROM cost_ledger WHERE task_id = ?""",
                (task_id,),
            ).fetchone()
        return float(row["credits"]), float(row["usd"])

    # ------------------------------------------------------------------ detector
    def save_detector_report(self, report: DetectorReport) -> DetectorReport:
        with self._lock:
            self._conn.execute(
                """INSERT INTO detector_report
                   (id, owner_id, answer, as_of, payload_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                     owner_id = excluded.owner_id,
                     answer = excluded.answer,
                     as_of = excluded.as_of,
                     payload_json = excluded.payload_json""",
                (
                    report.id,
                    report.owner_id,
                    report.answer,
                    report.as_of,
                    report.model_dump_json(),
                    report.created_at,
                ),
            )
            self._conn.commit()
        return report

    def list_detector_reports(
        self, limit: int = 20, *, owner_id: str | None = None
    ) -> list[DetectorReport]:
        query = "SELECT payload_json FROM detector_report"
        vals: list[Any] = []
        if owner_id is not None:
            query += " WHERE owner_id = ? OR owner_id = ''"
            vals.append(owner_id)
        query += " ORDER BY created_at DESC LIMIT ?"
        vals.append(limit)
        with self._lock:
            rows = self._conn.execute(query, vals).fetchall()
        return [_parse_detector_report(row["payload_json"]) for row in rows]

    def get_detector_report(self, report_id: str) -> DetectorReport | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT payload_json FROM detector_report WHERE id = ?", (report_id,)
            ).fetchone()
        return _parse_detector_report(row["payload_json"]) if row else None

    # ------------------------------------------------------------------ benchmark
    def create_bench_session(self, session: BenchSession) -> BenchSession:
        with self._lock:
            self._conn.execute(
                """INSERT INTO bench_session
                   (id, owner_id, status, config_json, manifest_json, result_hash,
                    supersedes, created_at, finished_at, error)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    session.id,
                    session.owner_id,
                    session.status,
                    session.model_dump_json(),
                    session.manifest.model_dump_json() if session.manifest else "{}",
                    session.result_hash,
                    session.supersedes,
                    session.created_at,
                    session.finished_at,
                    session.error,
                ),
            )
            self._conn.commit()
        return session

    def update_bench_session(
        self,
        session_id: str,
        *,
        status: str | None = None,
        finished_at: str | None = None,
        error: str | None = None,
        result_hash: str | None = None,
        manifest_json: str | None = None,
    ) -> None:
        """生命周期更新；完成后不可变。配置 hash 不允许被改写。"""
        with self._lock:
            row = self._conn.execute(
                "SELECT status, result_hash, manifest_json, config_json "
                "FROM bench_session WHERE id = ?",
                (session_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"bench session not found: {session_id}")
            if str(row["status"]) in {"done", "failed"}:
                raise ValueError("bench session is immutable after completion")
            if result_hash is not None and row["result_hash"] is not None:
                if row["result_hash"] != result_hash:
                    raise ValueError("result_hash already set and differs")
                result_hash = None
            if manifest_json is not None:
                stored = json.loads(row["manifest_json"] or "{}")
                incoming = json.loads(manifest_json or "{}")
                if stored.get("config_hash") != incoming.get("config_hash"):
                    raise ValueError("manifest config_hash is immutable")
            sets: list[str] = []
            vals: list[Any] = []
            if status is not None:
                sets.append("status = ?")
                vals.append(status)
            if finished_at is not None:
                sets.append("finished_at = ?")
                vals.append(finished_at)
            if error is not None:
                sets.append("error = ?")
                vals.append(error)
            if result_hash is not None:
                sets.append("result_hash = ?")
                vals.append(result_hash)
            if manifest_json is not None:
                sets.append("manifest_json = ?")
                vals.append(manifest_json)
            if not sets:
                return
            config = json.loads(row["config_json"] or "{}")
            if status is not None:
                config["status"] = status
            if finished_at is not None:
                config["finished_at"] = finished_at
            if error is not None:
                config["error"] = error
            if result_hash is not None:
                config["result_hash"] = result_hash
            sets.append("config_json = ?")
            vals.append(json.dumps(config, ensure_ascii=False))
            vals.append(session_id)
            self._conn.execute(
                f"UPDATE bench_session SET {', '.join(sets)} WHERE id = ?", vals
            )
            self._conn.commit()

    def get_bench_session(self, session_id: str) -> BenchSession | None:
        with self._lock:
            row = self._conn.execute(
                """SELECT config_json, manifest_json, result_hash, supersedes,
                          status, finished_at, error
                   FROM bench_session WHERE id = ?""",
                (session_id,),
            ).fetchone()
        if row is None:
            return None
        session = BenchSession.model_validate_json(row["config_json"])
        manifest = None
        if row["manifest_json"] and row["manifest_json"] != "{}":
            manifest = ExperimentManifest.model_validate_json(row["manifest_json"])
        return session.model_copy(
            update={
                "status": row["status"],
                "finished_at": row["finished_at"],
                "error": row["error"],
                "result_hash": row["result_hash"],
                "supersedes": row["supersedes"],
                "manifest": manifest,
            }
        )

    def add_bench_result(self, session_id: str, result: TaskResult) -> None:
        with self._lock:
            self._conn.execute(
                """INSERT INTO bench_result (session_id, task_id, agent_id, payload_json, score)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    session_id,
                    result.task_id,
                    result.agent_id,
                    result.model_dump_json(),
                    result.score,
                ),
            )
            self._conn.commit()

    def prune_benchmarks(
        self, *, days: int = 30, dry_run: bool = False
    ) -> dict[str, int | str | bool]:
        """Delete terminal benchmark sessions older than ``days``.

        Results are removed by the bench_session foreign-key cascade. Running
        sessions are never touched.
        """
        if days < 0:
            raise ValueError("days must be >= 0")
        cutoff = datetime.now(UTC) - timedelta(days=days)
        cutoff_iso = cutoff.isoformat(timespec="seconds").replace("+00:00", "Z")

        def parse_timestamp(value: object) -> datetime | None:
            if not value:
                return None
            try:
                parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            except ValueError:
                return None
            return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed

        with self._lock:
            rows = self._conn.execute(
                "SELECT id, finished_at, created_at FROM bench_session "
                "WHERE status IN ('done', 'failed')"
            ).fetchall()
            ids: list[str] = []
            skipped = 0
            for row in rows:
                timestamp = parse_timestamp(row["finished_at"] or row["created_at"])
                if timestamp is None:
                    skipped += 1
                    continue
                if timestamp < cutoff:
                    ids.append(str(row["id"]))
            result_count = 0
            if ids:
                placeholders = ",".join("?" for _ in ids)
                result_count = int(self._conn.execute(
                    f"SELECT COUNT(*) FROM bench_result WHERE session_id IN ({placeholders})",
                    tuple(ids),
                ).fetchone()[0])
                if not dry_run:
                    self._conn.execute(
                        f"DELETE FROM bench_session WHERE id IN ({placeholders})",
                        tuple(ids),
                    )
                    self._conn.commit()
        return {
            "sessions": len(ids),
            "results": result_count,
            "skipped": skipped,
            "cutoff": cutoff_iso,
            "dry_run": dry_run,
        }

    def list_bench_results(self, session_id: str) -> list[TaskResult]:
        with self._lock:
            rows = self._conn.execute(
                """SELECT payload_json FROM bench_result WHERE session_id = ?
                   ORDER BY id ASC""",
                (session_id,),
            ).fetchall()
        return [TaskResult.model_validate_json(r["payload_json"]) for r in rows]

    # ------------------------------------------------------------------ anchors
    def save_anchor(self, anchor: Anchor) -> Anchor:
        with self._lock:
            self._conn.execute(
                """INSERT INTO anchor
                   (id, claim_key, claim_key_v2, claim_key_version, url, status,
                    payload_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    anchor.id,
                    anchor.claim_key,
                    anchor.claim_key_v2,
                    anchor.claim_key_version,
                    anchor.url,
                    anchor.status,
                    anchor.model_dump_json(),
                    anchor.last_verified_at,
                ),
            )
            self._conn.commit()
        return anchor

    def list_anchors(
        self, claim_key: str | None = None, *, active_only: bool = True, limit: int = 200
    ) -> list[Anchor]:
        query = "SELECT payload_json FROM anchor"
        clauses: list[str] = []
        vals: list[Any] = []
        if claim_key is not None:
            clauses.append("claim_key = ?")
            vals.append(claim_key)
        if active_only:
            clauses.append("status = 'active'")
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at DESC LIMIT ?"
        vals.append(limit)
        with self._lock:
            rows = self._conn.execute(query, vals).fetchall()
        return [Anchor.model_validate_json(row["payload_json"]) for row in rows]

    def get_anchor(self, anchor_id: str) -> Anchor | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT payload_json FROM anchor WHERE id = ?", (anchor_id,)
            ).fetchone()
        return Anchor.model_validate_json(row["payload_json"]) if row else None

    def save_anchor_observation(self, observation: AnchorObservation) -> AnchorObservation:
        with self._lock:
            self._conn.execute(
                """INSERT INTO anchor_observation
                   (id, anchor_id, status, content_changed, observed_hash, payload_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    observation.id,
                    observation.anchor_id,
                    observation.status,
                    int(observation.content_changed),
                    observation.observed_hash,
                    observation.model_dump_json(),
                    observation.observed_at,
                ),
            )
            self._conn.commit()
        return observation

    def list_anchor_observations(
        self, anchor_id: str | None = None, limit: int = 100
    ) -> list[AnchorObservation]:
        query = "SELECT payload_json FROM anchor_observation"
        vals: list[Any] = []
        if anchor_id is not None:
            query += " WHERE anchor_id = ?"
            vals.append(anchor_id)
        query += " ORDER BY created_at DESC LIMIT ?"
        vals.append(limit)
        with self._lock:
            rows = self._conn.execute(query, vals).fetchall()
        return [AnchorObservation.model_validate_json(row["payload_json"]) for row in rows]

    def save_anchor_candidate(self, candidate: AnchorCandidate) -> AnchorCandidate:
        with self._lock:
            self._conn.execute(
                """INSERT INTO anchor_candidate (id, anchor_id, status, payload_json, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    candidate.id,
                    candidate.anchor_id,
                    candidate.accuracy_status,
                    candidate.model_dump_json(),
                    candidate.created_at,
                ),
            )
            self._conn.commit()
        return candidate

    def update_anchor_candidate(self, candidate: AnchorCandidate) -> AnchorCandidate:
        with self._lock:
            self._conn.execute(
                "UPDATE anchor_candidate SET status = ?, payload_json = ? WHERE id = ?",
                (candidate.accuracy_status, candidate.model_dump_json(), candidate.id),
            )
            self._conn.commit()
        return candidate

    def apply_candidate_transaction(
        self,
        candidate_id: str,
        new_anchor: Anchor,
        *,
        status: str,
        decided_by: str,
    ) -> AnchorCandidate | None:
        """Atomically claim a pending candidate, insert its replacement, supersede the old anchor.

        The candidate status check makes concurrent approvals single-winner.
        """
        with self._lock:
            candidate_row = self._conn.execute(
                "SELECT payload_json FROM anchor_candidate WHERE id = ?",
                (candidate_id,),
            ).fetchone()
            if candidate_row is None:
                return None
            candidate = AnchorCandidate.model_validate_json(
                candidate_row["payload_json"]
            )
            if candidate.accuracy_status != "pending":
                return None
            anchor_row = self._conn.execute(
                "SELECT payload_json FROM anchor WHERE id = ?",
                (new_anchor.supersedes,),
            ).fetchone()
            if anchor_row is None:
                return None
            old_anchor = Anchor.model_validate_json(anchor_row["payload_json"])
            if old_anchor.status != "active":
                return None
            superseded = old_anchor.model_copy(
                update={"status": "superseded", "superseded_by": new_anchor.id}
            )
            updated = candidate.model_copy(
                update={
                    "accuracy_status": status,
                    "decided_at": utcnow_iso(),
                    "decided_by": decided_by,
                    "applied_anchor_id": new_anchor.id,
                }
            )
            try:
                self._conn.execute(
                    """INSERT INTO anchor
                       (id, claim_key, claim_key_v2, claim_key_version, url,
                        status, payload_json, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        new_anchor.id,
                        new_anchor.claim_key,
                        new_anchor.claim_key_v2,
                        new_anchor.claim_key_version,
                        new_anchor.url,
                        new_anchor.status,
                        new_anchor.model_dump_json(),
                        new_anchor.last_verified_at,
                    ),
                )
                self._conn.execute(
                    "UPDATE anchor SET payload_json = ?, status = ? WHERE id = ?",
                    (
                        superseded.model_dump_json(),
                        superseded.status,
                        old_anchor.id,
                    ),
                )
                self._conn.execute(
                    "UPDATE anchor_candidate SET status = ?, payload_json = ? WHERE id = ?",
                    (updated.accuracy_status, updated.model_dump_json(), candidate_id),
                )
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
        return updated

    def get_anchor_candidate(self, candidate_id: str) -> AnchorCandidate | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT payload_json FROM anchor_candidate WHERE id = ?", (candidate_id,)
            ).fetchone()
        return AnchorCandidate.model_validate_json(row["payload_json"]) if row else None

    def list_anchor_candidates(
        self, status: str | None = None, limit: int = 100
    ) -> list[AnchorCandidate]:
        query = "SELECT payload_json FROM anchor_candidate"
        vals: list[Any] = []
        if status:
            query += " WHERE status = ?"
            vals.append(status)
        query += " ORDER BY created_at DESC LIMIT ?"
        vals.append(limit)
        with self._lock:
            rows = self._conn.execute(query, vals).fetchall()
        return [AnchorCandidate.model_validate_json(row["payload_json"]) for row in rows]

    def find_anchor_candidate(
        self,
        anchor_id: str,
        normalized_new: str,
        gate_decision: str,
        *,
        statuses: tuple[str, ...] = ("pending", "rejected"),
    ) -> AnchorCandidate | None:
        placeholders = ",".join("?" for _ in statuses)
        query = (
            "SELECT payload_json FROM anchor_candidate "
            f"WHERE anchor_id = ? AND status IN ({placeholders}) "
            "ORDER BY created_at DESC"
        )
        with self._lock:
            rows = self._conn.execute(
                query, (anchor_id, *statuses)
            ).fetchall()
        for row in rows:
            candidate = AnchorCandidate.model_validate_json(row["payload_json"])
            if (
                candidate.normalized_new == normalized_new
                and candidate.gate_decision == gate_decision
            ):
                return candidate
        return None

    def mark_candidates_rolled_back(self, applied_anchor_id: str) -> int:
        count = 0
        for candidate in self.list_anchor_candidates(limit=1000):
            if (
                candidate.applied_anchor_id == applied_anchor_id
                and candidate.accuracy_status in {"approved", "auto_applied"}
            ):
                updated = candidate.model_copy(
                    update={
                        "accuracy_status": "rolled_back",
                        "decided_at": utcnow_iso(),
                        "decided_by": "rollback",
                    }
                )
                self.update_anchor_candidate(updated)
                count += 1
        return count

    def save_anchor_audit(
        self,
        action: str,
        anchor_id: str,
        *,
        related_id: str = "",
        details: dict[str, Any] | None = None,
    ) -> int:
        with self._lock:
            cursor = self._conn.execute(
                """INSERT INTO anchor_audit
                   (action, anchor_id, related_id, details_json, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    action,
                    anchor_id,
                    related_id,
                    json.dumps(details or {}, ensure_ascii=False),
                    utcnow_iso(),
                ),
            )
            self._conn.commit()
        return int(cursor.lastrowid or 0)

    def list_anchor_audit(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                """SELECT id, action, anchor_id, related_id, details_json, created_at
                   FROM anchor_audit ORDER BY id DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        result = []
        for row in rows:
            result.append(
                {
                    "id": row["id"],
                    "action": row["action"],
                    "anchor_id": row["anchor_id"],
                    "related_id": row["related_id"],
                    "details": json.loads(row["details_json"] or "{}"),
                    "created_at": row["created_at"],
                }
            )
        return result

    def update_anchor(self, anchor: Anchor) -> Anchor:
        with self._lock:
            self._conn.execute(
                "UPDATE anchor SET payload_json = ?, status = ?, claim_key_v2 = ?, "
            "claim_key_version = ? WHERE id = ?",
                (
                    anchor.model_dump_json(),
                    anchor.status,
                    anchor.claim_key_v2,
                    anchor.claim_key_version,
                    anchor.id,
                ),
            )
            self._conn.commit()
        return anchor

    def rollback_anchor(self, anchor_id: str) -> tuple[Anchor, Anchor] | None:
        new_anchor = self.get_anchor(anchor_id)
        if new_anchor is None or not new_anchor.supersedes:
            return None
        old_anchor = self.get_anchor(new_anchor.supersedes)
        if old_anchor is None:
            return None
        rolled_back = new_anchor.model_copy(update={"status": "rolled_back"})
        restored = old_anchor.model_copy(
            update={"status": "active", "superseded_by": None}
        )
        with self._lock:
            try:
                self._conn.execute(
                    "UPDATE anchor SET payload_json = ?, status = ? WHERE id = ?",
                    (rolled_back.model_dump_json(), rolled_back.status, rolled_back.id),
                )
                self._conn.execute(
                    "UPDATE anchor SET payload_json = ?, status = ? WHERE id = ?",
                    (restored.model_dump_json(), restored.status, restored.id),
                )
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
        return restored, rolled_back

    def save_anchor_replacement(self, old_id: str, new_anchor: Anchor) -> bool:
        """Atomically insert replacement and mark the old anchor superseded."""
        with self._lock:
            try:
                row = self._conn.execute(
                    "SELECT payload_json FROM anchor WHERE id = ?", (old_id,)
                ).fetchone()
                if row is None:
                    return False
                old = Anchor.model_validate_json(row["payload_json"])
                superseded = old.model_copy(
                    update={"status": "superseded", "superseded_by": new_anchor.id}
                )
                self._conn.execute(
                    """INSERT INTO anchor
                       (id, claim_key, claim_key_v2, claim_key_version, url, status,
                        payload_json, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        new_anchor.id,
                        new_anchor.claim_key,
                        new_anchor.claim_key_v2,
                        new_anchor.claim_key_version,
                        new_anchor.url,
                        new_anchor.status,
                        new_anchor.model_dump_json(),
                        new_anchor.last_verified_at,
                    ),
                )
                self._conn.execute(
                    "UPDATE anchor SET payload_json = ?, status = ? WHERE id = ?",
                    (superseded.model_dump_json(), superseded.status, old_id),
                )
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
        return True

    def supersede_anchor(self, old_id: str, new_id: str) -> None:
        anchor = self.get_anchor(old_id)
        if anchor is None:
            return
        updated = anchor.model_copy(update={"status": "superseded", "superseded_by": new_id})
        with self._lock:
            self._conn.execute(
                "UPDATE anchor SET payload_json = ?, status = ? WHERE id = ?",
                (updated.model_dump_json(), updated.status, old_id),
            )
            self._conn.commit()

    # ------------------------------------------------------------------ snapshots
    def save_snapshot(self, snapshot: EvidenceSnapshot) -> EvidenceSnapshot:
        with self._lock:
            self._conn.execute(
                """INSERT INTO snapshot
                   (id, url, title, origin, content_hash, raw_path, text_path,
                    published_at, updated_at, fetched_at, tier, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                     content_hash = excluded.content_hash,
                     text_path = excluded.text_path,
                     fetched_at = excluded.fetched_at""",
                (
                    snapshot.id,
                    snapshot.url,
                    snapshot.title,
                    snapshot.origin,
                    snapshot.content_hash,
                    snapshot.raw_path,
                    snapshot.text_path,
                    snapshot.published_at,
                    snapshot.updated_at,
                    snapshot.fetched_at,
                    snapshot.tier,
                    snapshot.notes,
                ),
            )
            self._conn.commit()
        return snapshot

    def list_snapshots_page(
        self, offset: int = 0, limit: int = 500
    ) -> list[EvidenceSnapshot]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM snapshot ORDER BY fetched_at DESC LIMIT ? OFFSET ?",
                (max(1, limit), max(0, offset)),
            ).fetchall()
        return [_row_to_snapshot(row) for row in rows]

    def list_snapshots_for_url(
        self, url: str, limit: int = 500
    ) -> list[EvidenceSnapshot]:
        return self.list_snapshots_for_url_page(url, offset=0, limit=limit)

    def list_snapshots_for_url_page(
        self, url: str, offset: int = 0, limit: int = 500
    ) -> list[EvidenceSnapshot]:
        with self._lock:
            rows = self._conn.execute(
                """SELECT * FROM snapshot WHERE url = ?
                   ORDER BY fetched_at DESC LIMIT ? OFFSET ?""",
                (url, max(1, limit), max(0, offset)),
            ).fetchall()
        return [_row_to_snapshot(row) for row in rows]

    def get_snapshot(self, snapshot_id: str) -> EvidenceSnapshot | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM snapshot WHERE id = ?", (snapshot_id,)
            ).fetchone()
        if row is None:
            return None
        return _row_to_snapshot(row)

    def list_snapshots(self, limit: int = 50) -> list[EvidenceSnapshot]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM snapshot ORDER BY fetched_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [_row_to_snapshot(row) for row in rows]


# ---------------------------------------------------------------------- row mappers
def _row_to_task(row: sqlite3.Row) -> ResearchTask:
    return ResearchTask(
        id=row["id"],
        owner_id=row["owner_id"] or "",
        question=row["question"],
        as_of=row["as_of"],
        status=TaskStatus(row["status"]),
        created_at=row["created_at"],
        finished_at=row["finished_at"],
        error=row["error"],
        report_md=row["report_md"],
        stats=json.loads(row["stats_json"] or "{}"),
    )


def _row_to_source(row: sqlite3.Row) -> SourceRecord:
    return SourceRecord(
        id=row["id"],
        task_id=row["task_id"],
        url=row["url"],
        canonical_url=row["canonical_url"],
        domain=row["domain"],
        title=row["title"],
        published_at=row["published_at"],
        fetched_at=row["fetched_at"],
        content_hash=row["content_hash"],
        tier=row["tier"],
        tier_reason=row["tier_reason"],
        score=row["score"],
        snippet=row["snippet"],
    )


def _row_to_event(row: sqlite3.Row) -> RunEvent:
    return RunEvent(
        seq=row["seq"],
        task_id=row["task_id"],
        stage=row["stage"],
        type=row["type"],
        payload=json.loads(row["payload_json"] or "{}"),
        ts=row["ts"],
    )


def _row_to_snapshot(row: sqlite3.Row) -> EvidenceSnapshot:
    return EvidenceSnapshot(
        id=row["id"],
        url=row["url"],
        title=row["title"],
        origin=row["origin"],
        content_hash=row["content_hash"],
        raw_path=row["raw_path"],
        text_path=row["text_path"],
        published_at=row["published_at"],
        updated_at=row["updated_at"],
        fetched_at=row["fetched_at"],
        tier=row["tier"],
        notes=row["notes"],
    )


def _parse_detector_report(payload: str) -> DetectorReport:
    """兼容旧报告：uncertain/unverifiable → insufficient。"""
    data = json.loads(payload)
    for verdict in data.get("verdicts", []):
        status = str(verdict.get("status") or "")
        if status in {"uncertain", "unverifiable"}:
            verdict["status"] = "insufficient"
    return DetectorReport.model_validate(data)


















