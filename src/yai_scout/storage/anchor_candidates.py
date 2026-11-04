from __future__ import annotations

from typing import Any

from ..domain.models import (
    Anchor,
    AnchorCandidate,
    utcnow_iso,
)
from .db import Repository


class AnchorCandidateRepository(Repository):
    def save_anchor_candidate(self, candidate: AnchorCandidate) -> AnchorCandidate:
        with self.db.write():
            self._conn.execute(
                """INSERT INTO anchor_candidate (id, anchor_id, status, payload_json, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    candidate.id,
                    candidate.anchor_id,
                    candidate.accuracy_status,
                    candidate.model_dump_json(),
                    candidate.created_at,
                ),
            )
        return candidate

    def update_anchor_candidate(self, candidate: AnchorCandidate) -> AnchorCandidate:
        with self.db.write():
            self._conn.execute(
                "UPDATE anchor_candidate SET status = ?, payload_json = ? WHERE id = ?",
                (candidate.accuracy_status, candidate.model_dump_json(), candidate.id),
            )
        return candidate

    def apply_candidate_transaction(
        self,
        candidate_id: str,
        new_anchor: Anchor,
        *,
        status: str,
        decided_by: str,
    ) -> AnchorCandidate | None:
        """Atomically claim a pending candidate, insert its replacement, supersede the old anchor.

        The candidate status check makes concurrent approvals single-winner.
        """
        with self.db.atomic():
            candidate_row = self._conn.execute(
                "SELECT payload_json FROM anchor_candidate WHERE id = ?",
                (candidate_id,),
            ).fetchone()
            if candidate_row is None:
                return None
            candidate = AnchorCandidate.model_validate_json(candidate_row["payload_json"])
            if candidate.accuracy_status != "pending":
                return None
            anchor_row = self._conn.execute(
                "SELECT payload_json FROM anchor WHERE id = ?",
                (new_anchor.supersedes,),
            ).fetchone()
            if anchor_row is None:
                return None
            old_anchor = Anchor.model_validate_json(anchor_row["payload_json"])
            if old_anchor.status != "active":
                return None
            superseded = old_anchor.model_copy(
                update={"status": "superseded", "superseded_by": new_anchor.id}
            )
            updated = candidate.model_copy(
                update={
                    "accuracy_status": status,
                    "decided_at": utcnow_iso(),
                    "decided_by": decided_by,
                    "applied_anchor_id": new_anchor.id,
                }
            )
            try:
                self._conn.execute(
                    """INSERT INTO anchor
                       (id, claim_key, claim_key_v2, claim_key_version, url,
                        status, payload_json, created_at)
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
                    (
                        superseded.model_dump_json(),
                        superseded.status,
                        old_anchor.id,
                    ),
                )
                self._conn.execute(
                    "UPDATE anchor_candidate SET status = ?, payload_json = ? WHERE id = ?",
                    (updated.accuracy_status, updated.model_dump_json(), candidate_id),
                )
            except Exception:
                self._conn.rollback()
                raise
        return updated

    def get_anchor_candidate(self, candidate_id: str) -> AnchorCandidate | None:
        with self.db.read():
            row = self._conn.execute(
                "SELECT payload_json FROM anchor_candidate WHERE id = ?", (candidate_id,)
            ).fetchone()
        return AnchorCandidate.model_validate_json(row["payload_json"]) if row else None

    def list_anchor_candidates(
        self, status: str | None = None, limit: int = 100
    ) -> list[AnchorCandidate]:
        query = "SELECT payload_json FROM anchor_candidate"
        vals: list[Any] = []
        if status:
            query += " WHERE status = ?"
            vals.append(status)
        query += " ORDER BY created_at DESC LIMIT ?"
        vals.append(limit)
        with self.db.read():
            rows = self._conn.execute(query, vals).fetchall()
        return [AnchorCandidate.model_validate_json(row["payload_json"]) for row in rows]

    def find_anchor_candidate(
        self,
        anchor_id: str,
        normalized_new: str,
        gate_decision: str,
        *,
        statuses: tuple[str, ...] = ("pending", "rejected"),
    ) -> AnchorCandidate | None:
        placeholders = ",".join("?" for _ in statuses)
        query = (
            "SELECT payload_json FROM anchor_candidate "
            f"WHERE anchor_id = ? AND status IN ({placeholders}) "
            "ORDER BY created_at DESC"
        )
        with self.db.read():
            rows = self._conn.execute(query, (anchor_id, *statuses)).fetchall()
        for row in rows:
            candidate = AnchorCandidate.model_validate_json(row["payload_json"])
            if (
                candidate.normalized_new == normalized_new
                and candidate.gate_decision == gate_decision
            ):
                return candidate
        return None

    def mark_candidates_rolled_back(self, applied_anchor_id: str) -> int:
        count = 0
        for candidate in self.list_anchor_candidates(limit=1000):
            if candidate.applied_anchor_id == applied_anchor_id and candidate.accuracy_status in {
                "approved",
                "auto_applied",
            }:
                updated = candidate.model_copy(
                    update={
                        "accuracy_status": "rolled_back",
                        "decided_at": utcnow_iso(),
                        "decided_by": "rollback",
                    }
                )
                self.update_anchor_candidate(updated)
                count += 1
        return count
