"""SQLite 存储层：任务 / 计划 / 来源 / 事件 / 成本。

G0 用同步 sqlite3 + 进程内锁：写少读多、单机演示足够。
后续并发上来后再把热点路径切到 asyncio.to_thread 或连接池。
"""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from .domain.models import (
    CostEntry,
    Plan,
    ResearchTask,
    RunEvent,
    SourceRecord,
    TaskStatus,
    utcnow_iso,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS research_task (
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
CREATE TABLE IF NOT EXISTS plan (
    task_id TEXT PRIMARY KEY,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS source (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
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
    task_id TEXT NOT NULL,
    stage TEXT NOT NULL,
    type TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    ts TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_event_task ON run_event(task_id, seq);
CREATE TABLE IF NOT EXISTS cost_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    unit TEXT NOT NULL,
    amount REAL NOT NULL,
    credits REAL NOT NULL DEFAULT 0,
    usd_estimate REAL NOT NULL DEFAULT 0,
    ts TEXT NOT NULL
);
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
            self._conn.commit()

    # ------------------------------------------------------------------ lifecycle
    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ------------------------------------------------------------------ tasks
    def create_task(self, task: ResearchTask) -> ResearchTask:
        with self._lock:
            self._conn.execute(
                """INSERT INTO research_task
                   (id, question, as_of, status, created_at, stats_json)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    task.id,
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

    def list_tasks(self, limit: int = 20) -> list[ResearchTask]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM research_task ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
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


# ---------------------------------------------------------------------- row mappers
def _row_to_task(row: sqlite3.Row) -> ResearchTask:
    return ResearchTask(
        id=row["id"],
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
