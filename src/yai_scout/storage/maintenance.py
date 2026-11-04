from __future__ import annotations

from ..domain.models import (
    utcnow_iso,
)
from .db import Repository


class MaintenanceRepository(Repository):
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
            self._conn.execute(
                "UPDATE bench_session SET status = 'failed', finished_at = ?, "
                "error = ? WHERE status = 'running'",
                (now, error),
            )
            self._conn.commit()
