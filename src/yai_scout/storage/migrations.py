from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from ..claim_classification import resolve_claim_type
from ..claim_keys import claim_key_v2
from ..domain.models import (
    Anchor,
    utcnow_iso,
)
from .db import Repository


class Migrations(Repository):
    def apply(self) -> None:
        self._apply_migrations()

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

    def _apply_migrations(self) -> None:
        """Sequential, idempotent schema migrations with a recorded version."""
        applied = {
            int(row["version"]) for row in self._conn.execute("SELECT version FROM schema_version")
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
            (10, self._normalize_bench_session_state),
            (11, self._ensure_bench_status_trigger),
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
        columns = {row["name"] for row in self._conn.execute("PRAGMA table_info(bench_session)")}
        additions = {
            "manifest_json": "TEXT NOT NULL DEFAULT '{}'",
            "result_hash": "TEXT",
            "supersedes": "TEXT",
            "finished_at": "TEXT",
            "error": "TEXT",
        }
        for name, decl in additions.items():
            if name not in columns:
                self._conn.execute(f"ALTER TABLE bench_session ADD COLUMN {name} {decl}")

    def _ensure_task_columns(self) -> None:
        columns = {row["name"] for row in self._conn.execute("PRAGMA table_info(research_task)")}
        if "owner_id" not in columns:
            self._conn.execute(
                "ALTER TABLE research_task ADD COLUMN owner_id TEXT NOT NULL DEFAULT ''"
            )

    def _ensure_detector_columns(self) -> None:
        columns = {row["name"] for row in self._conn.execute("PRAGMA table_info(detector_report)")}
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

    def _ensure_anchor_columns(self) -> None:
        columns = {row["name"] for row in self._conn.execute("PRAGMA table_info(anchor)")}
        if "status" not in columns:
            self._conn.execute(
                "ALTER TABLE anchor ADD COLUMN status TEXT NOT NULL DEFAULT 'active'"
            )
        for row in self._conn.execute("SELECT id, payload_json FROM anchor"):
            try:
                status = str(json.loads(row["payload_json"]).get("status") or "active")
            except (TypeError, ValueError):
                status = "active"
            self._conn.execute("UPDATE anchor SET status = ? WHERE id = ?", (status, row["id"]))
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_anchor_status ON anchor(status, created_at)"
        )

    def _ensure_bench_owner_column(self) -> None:
        columns = {row["name"] for row in self._conn.execute("PRAGMA table_info(bench_session)")}
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

    def _ensure_claim_key_columns(self) -> None:
        columns = {row["name"] for row in self._conn.execute("PRAGMA table_info(anchor)")}
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
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_anchor_claim_v2 ON anchor(claim_key_v2)")

    def _refresh_claim_identity(self) -> None:
        """Recompute v2 identity with the canonical classifier.

        Migration 7 could not know the shared claim type; migration 8 fixes
        anchors created before the type was persisted in the payload.
        """
        rows = self._conn.execute("SELECT id, payload_json FROM anchor").fetchall()
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

    def _normalize_bench_session_state(self) -> None:
        count = int(self._conn.execute("SELECT COUNT(*) FROM bench_session").fetchone()[0])
        if not count:
            return
        if self.path != ":memory:":
            stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
            backup = Path(self.path).with_name(
                f"{Path(self.path).name}.pre-v10.{stamp}.{uuid.uuid4().hex[:8]}.bak"
            )
            try:
                self._conn.commit()
                destination = sqlite3.connect(backup)
                try:
                    self._conn.backup(destination)
                finally:
                    destination.close()
            except sqlite3.Error as exc:
                raise RuntimeError(f"cannot create pre-migration backup at {backup}") from exc
        rows = self._conn.execute(
            "SELECT id, config_json, manifest_json FROM bench_session"
        ).fetchall()
        for row in rows:
            config_json = row["config_json"]
            try:
                config = json.loads(config_json or "{}")
            except ValueError:
                config = None
            nested_manifest: object = None
            if isinstance(config, dict):
                nested_manifest = config.get("manifest")
                for field in (
                    "manifest",
                    "status",
                    "finished_at",
                    "error",
                    "result_hash",
                    "supersedes",
                ):
                    config.pop(field, None)
                config_json = json.dumps(config, ensure_ascii=False)
            manifest_json = self._normalize_manifest_json(row["manifest_json"])
            if manifest_json in {"", "{}"} and isinstance(nested_manifest, dict):
                manifest_json = self._normalize_manifest_json(
                    json.dumps(nested_manifest, ensure_ascii=False)
                )
            self._conn.execute(
                "UPDATE bench_session SET config_json = ?, manifest_json = ? WHERE id = ?",
                (config_json, manifest_json, row["id"]),
            )

    def _ensure_bench_status_trigger(self) -> None:
        self._conn.executescript(
            """
            CREATE TRIGGER IF NOT EXISTS trg_bench_session_status_insert
            BEFORE INSERT ON bench_session
            WHEN NEW.status NOT IN ('running', 'done', 'failed')
            BEGIN
                SELECT RAISE(ABORT, 'invalid bench_session status');
            END;
            CREATE TRIGGER IF NOT EXISTS trg_bench_session_status_update
            BEFORE UPDATE OF status ON bench_session
            WHEN NEW.status NOT IN ('running', 'done', 'failed')
            BEGIN
                SELECT RAISE(ABORT, 'invalid bench_session status');
            END;
            """
        )
