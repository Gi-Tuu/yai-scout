"""领域模型：任务 / 计划 / 来源 / 事件 / 成本。

G0 只落"任务 → 计划 → 来源 → 事件"四类；claim / verdict / report 表在后续迭代补齐。
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


def utcnow_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class Stage(StrEnum):
    PLANNING = "planning"
    RETRIEVING = "retrieving"
    EXTRACTING = "extracting"
    VERIFYING = "verifying"
    REPORTING = "reporting"
    DONE = "done"


class TaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DELIVERED = "delivered"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SourceTier(StrEnum):
    """T1 一手 / T2 权威二手 / T3 行业 / T4 UGC（G0 只用简单域名规则）。"""

    T1 = "1"
    T2 = "2"
    T3 = "3"
    T4 = "4"


class SubQuestion(BaseModel):
    id: str
    question: str
    queries: list[str] = Field(default_factory=list)
    required_source_types: list[str] = Field(default_factory=list)


class Plan(BaseModel):
    sub_questions: list[SubQuestion]
    stop_criteria: str = ""
    generated_by: Literal["rules", "llm"] = "rules"


class SourceRecord(BaseModel):
    id: str
    task_id: str
    url: str
    canonical_url: str
    domain: str
    title: str = ""
    published_at: str | None = None
    fetched_at: str = Field(default_factory=utcnow_iso)
    content_hash: str = ""
    tier: int = 3
    tier_reason: str = ""
    score: float = 0.0
    snippet: str = ""


class ResearchTask(BaseModel):
    id: str
    question: str
    as_of: str
    status: TaskStatus = TaskStatus.PENDING
    created_at: str = Field(default_factory=utcnow_iso)
    finished_at: str | None = None
    error: str | None = None
    report_md: str | None = None
    stats: dict[str, Any] = Field(default_factory=dict)


class RunEvent(BaseModel):
    seq: int = 0
    task_id: str
    stage: Stage
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    ts: str = Field(default_factory=utcnow_iso)


class CostEntry(BaseModel):
    id: int = 0
    task_id: str
    provider: str
    unit: str
    amount: float
    credits: float = 0.0
    usd_estimate: float = 0.0
    ts: str = Field(default_factory=utcnow_iso)
