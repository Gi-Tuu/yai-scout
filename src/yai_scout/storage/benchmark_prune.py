from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from ..domain.models import (
    utcnow_iso,
)
from .db import Repository


class BenchmarkPruneRepository(Repository):
    def prune_benchmarks(
        self,
        *,
        days: int = 30,
        dry_run: bool = False,
        audit_dir: str | Path | None = None,
        audit_keep_days: int = 30,
    ) -> dict[str, int | str | bool]:
        """Delete terminal benchmark sessions older than ``days``.

        Before deletion, the affected sessions and results are written to an
        audit JSON file. If the audit write fails, deletion is aborted. Running
        sessions are never touched.
        """
        if days < 0:
            raise ValueError("days must be >= 0")
        if audit_keep_days < 0:
            raise ValueError("audit_keep_days must be >= 0")
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
            audit_file = ""
            audit_removed = 0
            target_dir = self._audit_target_dir(audit_dir)
            if ids:
                placeholders = ",".join("?" for _ in ids)
                session_rows = self._conn.execute(
                    "SELECT id, status, config_json, manifest_json, created_at, "
                    "finished_at, error FROM bench_session "
                    f"WHERE id IN ({placeholders})",
                    tuple(ids),
                ).fetchall()
                result_rows = self._conn.execute(
                    "SELECT session_id, task_id, agent_id, payload_json, score "
                    f"FROM bench_result WHERE session_id IN ({placeholders})",
                    tuple(ids),
                ).fetchall()
                result_count = len(result_rows)
                if not dry_run:
                    audit_path = self._write_prune_audit(
                        session_rows, result_rows, cutoff_iso, audit_dir
                    )
                    if audit_path is not None:
                        audit_file = audit_path.name
                    self._conn.execute(
                        f"DELETE FROM bench_session WHERE id IN ({placeholders})",
                        tuple(ids),
                    )
                    self._conn.commit()
            if not dry_run:
                audit_removed = self._cleanup_prune_audits(target_dir, audit_keep_days)
        return {
            "sessions": len(ids),
            "results": result_count,
            "skipped": skipped,
            "cutoff": cutoff_iso,
            "dry_run": dry_run,
            "audit_file": audit_file,
            "audit_removed": audit_removed,
        }

    def _audit_target_dir(self, audit_dir: str | Path | None) -> Path | None:
        if self.path == ":memory:" and audit_dir is None:
            return None
        if audit_dir is None:
            return Path(self.path).parent / "benchmark_prune_audit"
        return Path(audit_dir)

    def _cleanup_prune_audits(self, target_dir: Path | None, keep_days: int) -> int:
        if target_dir is None or not target_dir.is_dir():
            return 0
        cutoff = datetime.now(UTC) - timedelta(days=keep_days)
        removed = 0
        for path in target_dir.glob("prune_*.json"):
            try:
                modified = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
            except OSError:
                continue
            if modified < cutoff:
                try:
                    path.unlink()
                except OSError:
                    continue
                removed += 1
        return removed

    def _write_prune_audit(
        self,
        session_rows: list[sqlite3.Row],
        result_rows: list[sqlite3.Row],
        cutoff: str,
        audit_dir: str | Path | None,
    ) -> Path | None:
        target = self._audit_target_dir(audit_dir)
        if target is None:
            return None
        target_dir = target
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / (
            f"prune_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}.json"
        )
        payload = {
            "created_at": utcnow_iso(),
            "cutoff": cutoff,
            "sessions": [dict(row) for row in session_rows],
            "results": [dict(row) for row in result_rows],
        }
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        temporary.replace(path)
        return path
