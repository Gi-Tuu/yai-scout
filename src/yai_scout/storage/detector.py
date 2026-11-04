from __future__ import annotations

from typing import Any

from ..domain.models import (
    DetectorReport,
)
from .db import Repository
from .rows import (
    _parse_detector_report,
)


class DetectorRepository(Repository):
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
