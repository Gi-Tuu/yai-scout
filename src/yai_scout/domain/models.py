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


# --------------------------------------------------------------------------- detector
class ClaimType(StrEnum):
    PRICING = "pricing"
    VERSION = "version"
    LAW = "law"
    LEADERSHIP = "leadership"
    STATISTIC = "statistic"
    DATE = "date"
    OTHER = "other"


class FreshnessStatus(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    UNCERTAIN = "uncertain"
    UNVERIFIABLE = "unverifiable"


class EvidenceRef(BaseModel):
    url: str
    title: str = ""
    domain: str = ""
    published_at: str | None = None
    tier: int = 3
    snippet: str = ""
    relation: Literal["supports", "contradicts", "mentions"] = "mentions"


class Claim(BaseModel):
    id: str
    text: str
    type: ClaimType = ClaimType.OTHER
    numbers: list[str] = Field(default_factory=list)
    signals: list[str] = Field(default_factory=list)


class FreshnessVerdict(BaseModel):
    claim_id: str
    status: FreshnessStatus
    score: int = Field(ge=0, le=100)
    rationale: str = ""
    suggestion: str = ""
    evidence: list[EvidenceRef] = Field(default_factory=list)
    checked_at: str = Field(default_factory=utcnow_iso)


class DetectorReport(BaseModel):
    id: str
    answer: str
    as_of: str
    claims: list[Claim] = Field(default_factory=list)
    verdicts: list[FreshnessVerdict] = Field(default_factory=list)
    overall_score: int = Field(default=0, ge=0, le=100)
    stale_claims: int = 0
    credits: float = 0.0
    llm_cost_usd: float = 0.0
    created_at: str = Field(default_factory=utcnow_iso)


# --------------------------------------------------------------------------- benchmark
class BenchmarkTask(BaseModel):
    id: str
    question: str
    as_of: str
    category: ClaimType = ClaimType.OTHER
    gold_values: list[str] = Field(default_factory=list)
    gold_sources: list[str] = Field(default_factory=list)
    notes: str = ""


class AgentSpec(BaseModel):
    id: str
    name: str
    kind: Literal["mock", "retrieval_baseline", "scout", "http", "llm"] = "mock"
    description: str = ""
    config: dict[str, Any] = Field(default_factory=dict)


class AgentAnswer(BaseModel):
    text: str
    citations: list[str] = Field(default_factory=list)
    tokens: int = 0
    latency_s: float = 0.0
    cost_usd: float = 0.0
    error: str | None = None


class TaskResult(BaseModel):
    task_id: str
    agent_id: str
    answer: AgentAnswer
    numeric_accuracy: float = 0.0
    has_citations: bool = False
    citation_count: int = 0
    freshness_score: int | None = None
    stale_claim_rate: float | None = None
    score: float = 0.0
    error: str | None = None


class BenchSession(BaseModel):
    id: str
    status: Literal["running", "done", "failed"] = "running"
    agent_ids: list[str] = Field(default_factory=list)
    task_ids: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=utcnow_iso)
    finished_at: str | None = None
    error: str | None = None
