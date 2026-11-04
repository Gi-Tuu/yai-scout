from __future__ import annotations

import json
from typing import Any

from ..domain.models import (
    Anchor,
    AnchorObservation,
    utcnow_iso,
)
from .db import Repository


class AnchorRepository(Repository):
    def save_anchor(self, anchor: Anchor) -> Anchor:
        with self.db.write():
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
        with self.db.read():
            rows = self._conn.execute(query, vals).fetchall()
        return [Anchor.model_validate_json(row["payload_json"]) for row in rows]

    def get_anchor(self, anchor_id: str) -> Anchor | None:
        with self.db.read():
            row = self._conn.execute(
                "SELECT payload_json FROM anchor WHERE id = ?", (anchor_id,)
            ).fetchone()
        return Anchor.model_validate_json(row["payload_json"]) if row else None

    def save_anchor_observation(self, observation: AnchorObservation) -> AnchorObservation:
        with self.db.write():
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
        with self.db.read():
            rows = self._conn.execute(query, vals).fetchall()
        return [AnchorObservation.model_validate_json(row["payload_json"]) for row in rows]

    def save_anchor_audit(
        self,
        action: str,
        anchor_id: str,
        *,
        related_id: str = "",
        details: dict[str, Any] | None = None,
    ) -> int:
        with self.db.write():
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
        return int(cursor.lastrowid or 0)

    def list_anchor_audit(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.db.read():
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
        with self.db.write():
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
        return anchor

    def rollback_anchor(self, anchor_id: str) -> tuple[Anchor, Anchor] | None:
        new_anchor = self.get_anchor(anchor_id)
        if new_anchor is None or not new_anchor.supersedes:
            return None
        old_anchor = self.get_anchor(new_anchor.supersedes)
        if old_anchor is None:
            return None
        rolled_back = new_anchor.model_copy(update={"status": "rolled_back"})
        restored = old_anchor.model_copy(update={"status": "active", "superseded_by": None})
        with self.db.atomic():
            try:
                self._conn.execute(
                    "UPDATE anchor SET payload_json = ?, status = ? WHERE id = ?",
                    (rolled_back.model_dump_json(), rolled_back.status, rolled_back.id),
                )
                self._conn.execute(
                    "UPDATE anchor SET payload_json = ?, status = ? WHERE id = ?",
                    (restored.model_dump_json(), restored.status, restored.id),
                )
            except Exception:
                self._conn.rollback()
                raise
        return restored, rolled_back

    def save_anchor_replacement(self, old_id: str, new_anchor: Anchor) -> bool:
        """Atomically insert replacement and mark the old anchor superseded."""
        with self.db.atomic():
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
            except Exception:
                self._conn.rollback()
                raise
        return True

    def supersede_anchor(self, old_id: str, new_id: str) -> None:
        anchor = self.get_anchor(old_id)
        if anchor is None:
            return
        updated = anchor.model_copy(update={"status": "superseded", "superseded_by": new_id})
        with self.db.write():
            self._conn.execute(
                "UPDATE anchor SET payload_json = ?, status = ? WHERE id = ?",
                (updated.model_dump_json(), updated.status, old_id),
            )
