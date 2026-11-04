from __future__ import annotations

import json
from typing import Any

from ..domain.models import (
    CostEntry,
    Plan,
    ResearchTask,
    RunEvent,
    SourceRecord,
    TaskStatus,
    utcnow_iso,
)
from .db import Repository
from .rows import (
    _row_to_event,
    _row_to_source,
    _row_to_task,
)


class TaskRepository(Repository):
    def create_task(self, task: ResearchTask) -> ResearchTask:
        with self.db.write():
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
        return task

    def get_task(self, task_id: str) -> ResearchTask | None:
        with self.db.read():
            row = self._conn.execute(
                "SELECT * FROM research_task WHERE id = ?", (task_id,)
            ).fetchone()
        return _row_to_task(row) if row else None

    def list_tasks(self, limit: int = 20, *, owner_id: str | None = None) -> list[ResearchTask]:
        query = "SELECT * FROM research_task"
        vals: list[Any] = []
        if owner_id is not None:
            query += " WHERE owner_id = ?"
            vals.append(owner_id)
        query += " ORDER BY created_at DESC LIMIT ?"
        vals.append(limit)
        with self.db.read():
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
        with self.db.write():
            self._conn.execute(f"UPDATE research_task SET {', '.join(sets)} WHERE id = ?", vals)

    def save_plan(self, task_id: str, plan: Plan) -> None:
        with self.db.write():
            self._conn.execute(
                """INSERT INTO plan (task_id, payload_json, created_at) VALUES (?, ?, ?)
                   ON CONFLICT(task_id) DO UPDATE SET
                   payload_json = excluded.payload_json, created_at = excluded.created_at""",
                (task_id, plan.model_dump_json(), utcnow_iso()),
            )

    def get_plan(self, task_id: str) -> Plan | None:
        with self.db.read():
            row = self._conn.execute(
                "SELECT payload_json FROM plan WHERE task_id = ?", (task_id,)
            ).fetchone()
        return Plan.model_validate_json(row["payload_json"]) if row else None

    def add_source(self, source: SourceRecord) -> bool:
        """插入来源；同一 task 下 canonical_url 重复则忽略。返回是否新增。"""
        with self.db.write():
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
            return cur.rowcount > 0

    def list_sources(self, task_id: str) -> list[SourceRecord]:
        with self.db.read():
            rows = self._conn.execute(
                "SELECT * FROM source WHERE task_id = ? ORDER BY tier ASC, score DESC",
                (task_id,),
            ).fetchall()
        return [_row_to_source(r) for r in rows]

    def count_sources(self, task_id: str) -> int:
        with self.db.read():
            row = self._conn.execute(
                "SELECT COUNT(*) AS n FROM source WHERE task_id = ?", (task_id,)
            ).fetchone()
        return int(row["n"])

    def append_event(self, event: RunEvent) -> RunEvent:
        with self.db.write():
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
            seq = int(cur.lastrowid or 0)
        return event.model_copy(update={"seq": seq})

    def list_events(self, task_id: str, after_seq: int = 0, limit: int = 1000) -> list[RunEvent]:
        with self.db.read():
            rows = self._conn.execute(
                """SELECT * FROM run_event WHERE task_id = ? AND seq > ?
                   ORDER BY seq ASC LIMIT ?""",
                (task_id, after_seq, limit),
            ).fetchall()
        return [_row_to_event(r) for r in rows]

    def add_cost(self, entry: CostEntry) -> CostEntry:
        with self.db.write():
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
            return entry.model_copy(update={"id": int(cur.lastrowid or 0)})

    def cost_sum(self, task_id: str) -> tuple[float, float]:
        with self.db.read():
            row = self._conn.execute(
                """SELECT COALESCE(SUM(credits), 0) AS credits,
                          COALESCE(SUM(usd_estimate), 0) AS usd
                   FROM cost_ledger WHERE task_id = ?""",
                (task_id,),
            ).fetchone()
        return float(row["credits"]), float(row["usd"])
