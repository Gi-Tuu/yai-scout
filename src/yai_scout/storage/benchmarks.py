from __future__ import annotations

import json
from typing import Any

from ..domain.models import (
    BenchSession,
    ExperimentManifest,
    TaskResult,
)
from .db import Repository


class BenchmarkRepository(Repository):
    @staticmethod
    def _bench_config_payload(session: BenchSession) -> str:
        return session.model_dump_json(
            exclude={
                "manifest",
                "status",
                "finished_at",
                "error",
                "result_hash",
                "supersedes",
            }
        )

    @staticmethod
    def _normalize_manifest_payload(manifest: ExperimentManifest) -> str:
        return manifest.model_dump_json(exclude={"status", "finished_at", "result_hash"})

    @staticmethod
    def _normalize_manifest_json(raw: str) -> str:
        try:
            payload = json.loads(raw or "{}")
        except ValueError:
            return raw
        if not isinstance(payload, dict):
            return raw
        for field in ("status", "finished_at", "result_hash"):
            payload.pop(field, None)
        return json.dumps(payload, ensure_ascii=False)

    def create_bench_session(self, session: BenchSession) -> BenchSession:
        with self.db.write():
            self._conn.execute(
                """INSERT INTO bench_session
                   (id, owner_id, status, config_json, manifest_json, result_hash,
                    supersedes, created_at, finished_at, error)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    session.id,
                    session.owner_id,
                    session.status,
                    self._bench_config_payload(session),
                    (
                        self._normalize_manifest_payload(session.manifest)
                        if session.manifest
                        else "{}"
                    ),
                    session.result_hash,
                    session.supersedes,
                    session.created_at,
                    session.finished_at,
                    session.error,
                ),
            )
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
        with self.db.atomic():
            row = self._conn.execute(
                "SELECT status, result_hash, manifest_json, config_json "
                "FROM bench_session WHERE id = ?",
                (session_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"bench session not found: {session_id}")
            if status is not None and status not in {"running", "done", "failed"}:
                raise ValueError("invalid bench session status")
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
                manifest_json = self._normalize_manifest_json(manifest_json)
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
            vals.append(session_id)
            self._conn.execute(f"UPDATE bench_session SET {', '.join(sets)} WHERE id = ?", vals)

    def get_bench_session(self, session_id: str) -> BenchSession | None:
        with self.db.read():
            row = self._conn.execute(
                """SELECT id, owner_id, created_at, config_json, manifest_json,
                          result_hash, supersedes, status, finished_at, error
                   FROM bench_session WHERE id = ?""",
                (session_id,),
            ).fetchone()
        if row is None:
            return None
        try:
            payload = json.loads(row["config_json"] or "{}")
        except ValueError as exc:
            raise ValueError("bench_session config_json is invalid") from exc
        if not isinstance(payload, dict):
            raise ValueError("bench_session config_json must be an object")
        payload.setdefault("id", row["id"])
        payload.setdefault("created_at", row["created_at"])
        payload.update(
            {
                "owner_id": row["owner_id"],
                "status": row["status"],
                "finished_at": row["finished_at"],
                "error": row["error"],
                "result_hash": row["result_hash"],
                "supersedes": row["supersedes"],
            }
        )
        manifest = None
        if row["manifest_json"] and row["manifest_json"] != "{}":
            try:
                manifest_payload = json.loads(row["manifest_json"])
            except ValueError as exc:
                raise ValueError("bench_session manifest_json is invalid") from exc
            if not isinstance(manifest_payload, dict):
                raise ValueError("bench_session manifest_json must be an object")
            manifest_payload.update(
                {
                    "status": row["status"],
                    "finished_at": row["finished_at"],
                    "result_hash": row["result_hash"],
                }
            )
            manifest = ExperimentManifest.model_validate(manifest_payload)
        payload["manifest"] = manifest
        return BenchSession.model_validate(payload)

    def add_bench_result(self, session_id: str, result: TaskResult) -> None:
        with self.db.write():
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

    def list_bench_results(self, session_id: str) -> list[TaskResult]:
        with self.db.read():
            rows = self._conn.execute(
                """SELECT payload_json FROM bench_result WHERE session_id = ?
                   ORDER BY id ASC""",
                (session_id,),
            ).fetchall()
        return [TaskResult.model_validate_json(r["payload_json"]) for r in rows]
