"""Row to domain-model mappers."""

from __future__ import annotations

import json
import sqlite3

from ..domain.models import (
    DetectorReport,
    EvidenceSnapshot,
    ResearchTask,
    RunEvent,
    SourceRecord,
    TaskStatus,
)


def _row_to_task(row: sqlite3.Row) -> ResearchTask:
    return ResearchTask(
        id=row["id"],
        owner_id=row["owner_id"] or "",
        question=row["question"],
        as_of=row["as_of"],
        status=TaskStatus(row["status"]),
        created_at=row["created_at"],
        finished_at=row["finished_at"],
        error=row["error"],
        report_md=row["report_md"],
        stats=json.loads(row["stats_json"] or "{}"),
    )


def _row_to_source(row: sqlite3.Row) -> SourceRecord:
    return SourceRecord(
        id=row["id"],
        task_id=row["task_id"],
        url=row["url"],
        canonical_url=row["canonical_url"],
        domain=row["domain"],
        title=row["title"],
        published_at=row["published_at"],
        fetched_at=row["fetched_at"],
        content_hash=row["content_hash"],
        tier=row["tier"],
        tier_reason=row["tier_reason"],
        score=row["score"],
        snippet=row["snippet"],
    )


def _row_to_event(row: sqlite3.Row) -> RunEvent:
    return RunEvent(
        seq=row["seq"],
        task_id=row["task_id"],
        stage=row["stage"],
        type=row["type"],
        payload=json.loads(row["payload_json"] or "{}"),
        ts=row["ts"],
    )


def _row_to_snapshot(row: sqlite3.Row) -> EvidenceSnapshot:
    return EvidenceSnapshot(
        id=row["id"],
        url=row["url"],
        title=row["title"],
        origin=row["origin"],
        content_hash=row["content_hash"],
        raw_path=row["raw_path"],
        text_path=row["text_path"],
        published_at=row["published_at"],
        updated_at=row["updated_at"],
        fetched_at=row["fetched_at"],
        tier=row["tier"],
        notes=row["notes"],
    )


def _parse_detector_report(payload: str) -> DetectorReport:
    """兼容旧报告：uncertain/unverifiable → insufficient。"""
    data = json.loads(payload)
    for verdict in data.get("verdicts", []):
        status = str(verdict.get("status") or "")
        if status in {"uncertain", "unverifiable"}:
            verdict["status"] = "insufficient"
    return DetectorReport.model_validate(data)
