from __future__ import annotations

from ..domain.models import (
    EvidenceSnapshot,
)
from .db import Repository
from .rows import (
    _row_to_snapshot,
)


class SnapshotRepository(Repository):
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

    def list_snapshots_page(self, offset: int = 0, limit: int = 500) -> list[EvidenceSnapshot]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM snapshot ORDER BY fetched_at DESC LIMIT ? OFFSET ?",
                (max(1, limit), max(0, offset)),
            ).fetchall()
        return [_row_to_snapshot(row) for row in rows]

    def list_snapshots_for_url(self, url: str, limit: int = 500) -> list[EvidenceSnapshot]:
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
