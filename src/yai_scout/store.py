"""Storage facade: SQLite repositories with a stable public API."""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any

from .domain.models import (
    Anchor,
    AnchorCandidate,
    AnchorObservation,
    BenchSession,
    CostEntry,
    DetectorReport,
    EvidenceSnapshot,
    Plan,
    ResearchTask,
    RunEvent,
    SourceRecord,
    TaskResult,
    TaskStatus,
)
from .storage.anchor_candidates import AnchorCandidateRepository
from .storage.anchors import AnchorRepository
from .storage.benchmark_prune import BenchmarkPruneRepository
from .storage.benchmarks import BenchmarkRepository
from .storage.consistency import ConsistencyChecker
from .storage.db import Database
from .storage.detector import DetectorRepository
from .storage.maintenance import MaintenanceRepository
from .storage.schema import initialize
from .storage.snapshots import SnapshotRepository
from .storage.tasks import TaskRepository


class Store:
    def __init__(self, path: str | Path = ":memory:") -> None:
        self.db = Database(path)
        initialize(self.db)
        self._tasks = TaskRepository(self.db)
        self._detector = DetectorRepository(self.db)
        self._benchmarks = BenchmarkRepository(self.db)
        self._prune = BenchmarkPruneRepository(self.db)
        self._anchors = AnchorRepository(self.db)
        self._candidates = AnchorCandidateRepository(self.db)
        self._snapshots = SnapshotRepository(self.db)
        self._consistency = ConsistencyChecker(self.db)
        self._maintenance = MaintenanceRepository(self.db)

    @property
    def path(self) -> str:
        return self.db.path

    @property
    def _conn(self) -> sqlite3.Connection:
        return self.db.conn

    @property
    def _lock(self) -> threading.RLock:
        return self.db.lock

    def close(self) -> None:
        self.db.close()

    def ping(self) -> None:
        self.db.ping()

    def add_bench_result(self, session_id: str, result: TaskResult) -> None:
        return self._benchmarks.add_bench_result(session_id=session_id, result=result)

    def add_cost(self, entry: CostEntry) -> CostEntry:
        return self._tasks.add_cost(entry=entry)

    def add_source(self, source: SourceRecord) -> bool:
        return self._tasks.add_source(source=source)

    def append_event(self, event: RunEvent) -> RunEvent:
        return self._tasks.append_event(event=event)

    def apply_candidate_transaction(
        self, candidate_id: str, new_anchor: Anchor, status: str, decided_by: str
    ) -> AnchorCandidate | None:
        return self._candidates.apply_candidate_transaction(
            candidate_id=candidate_id, new_anchor=new_anchor, status=status, decided_by=decided_by
        )

    def consistency_report(
        self,
    ) -> list[dict[str, str]]:
        return self._consistency.consistency_report()

    def cost_sum(self, task_id: str) -> tuple[float, float]:
        return self._tasks.cost_sum(task_id=task_id)

    def count_sources(self, task_id: str) -> int:
        return self._tasks.count_sources(task_id=task_id)

    def create_bench_session(self, session: BenchSession) -> BenchSession:
        return self._benchmarks.create_bench_session(session=session)

    def create_task(self, task: ResearchTask) -> ResearchTask:
        return self._tasks.create_task(task=task)

    def find_anchor_candidate(
        self,
        anchor_id: str,
        normalized_new: str,
        gate_decision: str,
        statuses: tuple[str, ...] = ("pending", "rejected"),
    ) -> AnchorCandidate | None:
        return self._candidates.find_anchor_candidate(
            anchor_id=anchor_id,
            normalized_new=normalized_new,
            gate_decision=gate_decision,
            statuses=statuses,
        )

    def get_anchor(self, anchor_id: str) -> Anchor | None:
        return self._anchors.get_anchor(anchor_id=anchor_id)

    def get_anchor_candidate(self, candidate_id: str) -> AnchorCandidate | None:
        return self._candidates.get_anchor_candidate(candidate_id=candidate_id)

    def get_bench_session(self, session_id: str) -> BenchSession | None:
        return self._benchmarks.get_bench_session(session_id=session_id)

    def get_detector_report(self, report_id: str) -> DetectorReport | None:
        return self._detector.get_detector_report(report_id=report_id)

    def get_plan(self, task_id: str) -> Plan | None:
        return self._tasks.get_plan(task_id=task_id)

    def get_snapshot(self, snapshot_id: str) -> EvidenceSnapshot | None:
        return self._snapshots.get_snapshot(snapshot_id=snapshot_id)

    def get_task(self, task_id: str) -> ResearchTask | None:
        return self._tasks.get_task(task_id=task_id)

    def list_anchor_audit(self, limit: int = 100) -> list[dict[str, Any]]:
        return self._anchors.list_anchor_audit(limit=limit)

    def list_anchor_candidates(
        self, status: str | None = None, limit: int = 100
    ) -> list[AnchorCandidate]:
        return self._candidates.list_anchor_candidates(status=status, limit=limit)

    def list_anchor_observations(
        self, anchor_id: str | None = None, limit: int = 100
    ) -> list[AnchorObservation]:
        return self._anchors.list_anchor_observations(anchor_id=anchor_id, limit=limit)

    def list_anchors(
        self, claim_key: str | None = None, active_only: bool = True, limit: int = 200
    ) -> list[Anchor]:
        return self._anchors.list_anchors(claim_key=claim_key, active_only=active_only, limit=limit)

    def list_bench_results(self, session_id: str) -> list[TaskResult]:
        return self._benchmarks.list_bench_results(session_id=session_id)

    def list_detector_reports(
        self, limit: int = 20, owner_id: str | None = None
    ) -> list[DetectorReport]:
        return self._detector.list_detector_reports(limit=limit, owner_id=owner_id)

    def list_events(self, task_id: str, after_seq: int = 0, limit: int = 1000) -> list[RunEvent]:
        return self._tasks.list_events(task_id=task_id, after_seq=after_seq, limit=limit)

    def list_snapshots(self, limit: int = 50) -> list[EvidenceSnapshot]:
        return self._snapshots.list_snapshots(limit=limit)

    def list_snapshots_for_url(self, url: str, limit: int = 500) -> list[EvidenceSnapshot]:
        return self._snapshots.list_snapshots_for_url(url=url, limit=limit)

    def list_snapshots_for_url_page(
        self, url: str, offset: int = 0, limit: int = 500
    ) -> list[EvidenceSnapshot]:
        return self._snapshots.list_snapshots_for_url_page(url=url, offset=offset, limit=limit)

    def list_snapshots_page(self, offset: int = 0, limit: int = 500) -> list[EvidenceSnapshot]:
        return self._snapshots.list_snapshots_page(offset=offset, limit=limit)

    def list_sources(self, task_id: str) -> list[SourceRecord]:
        return self._tasks.list_sources(task_id=task_id)

    def list_tasks(self, limit: int = 20, owner_id: str | None = None) -> list[ResearchTask]:
        return self._tasks.list_tasks(limit=limit, owner_id=owner_id)

    def mark_candidates_rolled_back(self, applied_anchor_id: str) -> int:
        return self._candidates.mark_candidates_rolled_back(applied_anchor_id=applied_anchor_id)

    def mark_interrupted_work(
        self,
    ) -> None:
        return self._maintenance.mark_interrupted_work()

    def prune_benchmarks(
        self,
        days: int = 30,
        dry_run: bool = False,
        audit_dir: str | Path | None = None,
        audit_keep_days: int = 30,
    ) -> dict[str, int | str | bool]:
        return self._prune.prune_benchmarks(
            days=days, dry_run=dry_run, audit_dir=audit_dir, audit_keep_days=audit_keep_days
        )

    def rollback_anchor(self, anchor_id: str) -> tuple[Anchor, Anchor] | None:
        return self._anchors.rollback_anchor(anchor_id=anchor_id)

    def save_anchor(self, anchor: Anchor) -> Anchor:
        return self._anchors.save_anchor(anchor=anchor)

    def save_anchor_audit(
        self,
        action: str,
        anchor_id: str,
        related_id: str = "",
        details: dict[str, Any] | None = None,
    ) -> int:
        return self._anchors.save_anchor_audit(
            action=action, anchor_id=anchor_id, related_id=related_id, details=details
        )

    def save_anchor_candidate(self, candidate: AnchorCandidate) -> AnchorCandidate:
        return self._candidates.save_anchor_candidate(candidate=candidate)

    def save_anchor_observation(self, observation: AnchorObservation) -> AnchorObservation:
        return self._anchors.save_anchor_observation(observation=observation)

    def save_anchor_replacement(self, old_id: str, new_anchor: Anchor) -> bool:
        return self._anchors.save_anchor_replacement(old_id=old_id, new_anchor=new_anchor)

    def save_detector_report(self, report: DetectorReport) -> DetectorReport:
        return self._detector.save_detector_report(report=report)

    def save_plan(self, task_id: str, plan: Plan) -> None:
        return self._tasks.save_plan(task_id=task_id, plan=plan)

    def save_snapshot(self, snapshot: EvidenceSnapshot) -> EvidenceSnapshot:
        return self._snapshots.save_snapshot(snapshot=snapshot)

    def supersede_anchor(self, old_id: str, new_id: str) -> None:
        return self._anchors.supersede_anchor(old_id=old_id, new_id=new_id)

    def update_anchor(self, anchor: Anchor) -> Anchor:
        return self._anchors.update_anchor(anchor=anchor)

    def update_anchor_candidate(self, candidate: AnchorCandidate) -> AnchorCandidate:
        return self._candidates.update_anchor_candidate(candidate=candidate)

    def update_bench_session(
        self,
        session_id: str,
        status: str | None = None,
        finished_at: str | None = None,
        error: str | None = None,
        result_hash: str | None = None,
        manifest_json: str | None = None,
    ) -> None:
        return self._benchmarks.update_bench_session(
            session_id=session_id,
            status=status,
            finished_at=finished_at,
            error=error,
            result_hash=result_hash,
            manifest_json=manifest_json,
        )

    def update_task(
        self,
        task_id: str,
        status: TaskStatus | None = None,
        finished_at: str | None = None,
        error: str | None = None,
        report_md: str | None = None,
        stats: dict[str, Any] | None = None,
    ) -> None:
        return self._tasks.update_task(
            task_id=task_id,
            status=status,
            finished_at=finished_at,
            error=error,
            report_md=report_md,
            stats=stats,
        )
