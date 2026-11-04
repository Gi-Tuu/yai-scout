from __future__ import annotations

import json

from ..domain.models import (
    Anchor,
    AnchorCandidate,
    ExperimentManifest,
)
from .db import Repository


class ConsistencyChecker(Repository):
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
                "SELECT id, owner_id, status, config_json, manifest_json, "
                "finished_at, result_hash FROM bench_session"
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
                if not isinstance(session_payload, dict):
                    add(
                        "bench_session",
                        session_row["id"],
                        "config_json",
                        "invalid_schema",
                        session_row["config_json"],
                    )
                    continue
                if str(session_row["status"]) not in {"running", "done", "failed"}:
                    add(
                        "bench_session",
                        session_row["id"],
                        "status",
                        "invalid_status",
                        str(session_row["status"]),
                    )
                if str(session_row["owner_id"]) != str(session_payload.get("owner_id", "")):
                    add(
                        "bench_session",
                        session_row["id"],
                        "owner_id",
                        str(session_row["owner_id"]),
                        str(session_payload.get("owner_id", "")),
                    )
                for field in (
                    "manifest",
                    "status",
                    "finished_at",
                    "error",
                    "result_hash",
                    "supersedes",
                ):
                    if field in session_payload:
                        add(
                            "bench_session",
                            session_row["id"],
                            field,
                            "unexpected_lifecycle_json",
                            str(session_payload.get(field)),
                        )
                raw_manifest = session_row["manifest_json"]
                if raw_manifest and raw_manifest != "{}":
                    try:
                        manifest_payload = json.loads(raw_manifest)
                    except ValueError:
                        add(
                            "bench_session",
                            session_row["id"],
                            "manifest_json",
                            "invalid_json",
                            raw_manifest,
                        )
                        continue
                    if not isinstance(manifest_payload, dict):
                        add(
                            "bench_session",
                            session_row["id"],
                            "manifest_json",
                            "invalid_schema",
                            raw_manifest,
                        )
                        continue
                    for field in ("status", "finished_at", "result_hash"):
                        if field in manifest_payload:
                            add(
                                "bench_session",
                                session_row["id"],
                                f"manifest.{field}",
                                "unexpected_lifecycle_json",
                                str(manifest_payload.get(field)),
                            )
                    try:
                        ExperimentManifest.model_validate(
                            {
                                **manifest_payload,
                                "status": session_row["status"],
                                "finished_at": session_row["finished_at"],
                                "result_hash": session_row["result_hash"],
                            }
                        )
                    except ValueError:
                        add(
                            "bench_session",
                            session_row["id"],
                            "manifest_json",
                            "invalid_schema",
                            raw_manifest,
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
