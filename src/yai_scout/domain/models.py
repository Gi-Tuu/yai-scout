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
    owner_id: str = ""
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


class EvidenceKind(StrEnum):
    SEARCH_SNIPPET = "search_snippet"
    FETCHED_PAGE = "fetched_page"
    OFFICIAL_DOCUMENT = "official_document"
    VERSION_HISTORY = "version_history"
    ARCHIVED_SOURCE = "archived_source"
    USER_PROVIDED_EVIDENCE = "user_provided_evidence"


class TemporalSensitivity(StrEnum):
    STABLE = "stable"
    SLOW = "slow"
    SENSITIVE = "sensitive"
    VOLATILE = "volatile"


class FreshnessStatus(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    CONFLICTED = "conflicted"
    INSUFFICIENT = "insufficient"
    UNKNOWN = "unknown"


class EvidenceRef(BaseModel):
    url: str
    title: str = ""
    domain: str = ""
    published_at: str | None = None
    updated_at: str | None = None
    retrieved_at: str | None = None
    tier: int = 3
    snippet: str = ""
    evidence_kind: EvidenceKind = EvidenceKind.SEARCH_SNIPPET
    fetch_status: str = ""
    content_hash: str = ""
    relation: Literal["supports", "contradicts", "mentions", "insufficient"] = "mentions"
    relation_reason: str = ""
    relation_confidence: float = 0.5
    snapshot_id: str | None = None
    anchor_id: str | None = None
    content_changed: bool = False


class Claim(BaseModel):
    id: str
    text: str
    type: ClaimType = ClaimType.OTHER
    numbers: list[str] = Field(default_factory=list)
    signals: list[str] = Field(default_factory=list)
    target_time: str | None = None
    temporal_sensitivity: TemporalSensitivity | None = None
    validity_window_days: int | None = None


class Anchor(BaseModel):
    """来源锚点：用于定向核验，不是当前值的证明。"""

    id: str
    claim_key: str
    claim_text: str = ""
    url: str
    source_tier: int = Field(default=3, ge=1, le=4)
    last_value: str = ""
    content_hash: str = ""
    published_at: str | None = None
    updated_at: str | None = None
    last_verified_at: str = Field(default_factory=utcnow_iso)
    last_checked_at: str | None = None
    valid_from: str | None = None
    temporal_sensitivity: TemporalSensitivity | None = None
    supersedes: str | None = None
    status: Literal["active", "superseded", "unreachable", "rolled_back"] = "active"


class AnchorObservation(BaseModel):
    id: str
    anchor_id: str
    status: Literal["verified", "changed", "unreachable"]
    content_changed: bool = False
    observed_hash: str = ""
    observed_at: str = Field(default_factory=utcnow_iso)
    url: str = ""
    source_tier: int = 3
    independent_group: str = ""
    value: str = ""
    published_at: str | None = None
    note: str = ""


class CandidateEvidence(BaseModel):
    url: str
    source_tier: int = Field(default=3, ge=1, le=4)
    independent_group: str = ""
    value: str = ""
    published_at: str | None = None
    content_hash: str = ""


class AnchorCandidate(BaseModel):
    id: str
    anchor_id: str
    claim_key: str
    old_value: str = ""
    new_value: str = ""
    normalized_old: str = ""
    normalized_new: str = ""
    evidence: list[CandidateEvidence] = Field(default_factory=list)
    gate_decision: Literal["auto_update", "review", "reject", "no_change"] = "review"
    gate_reason: str = ""
    gate_version: str = ""
    confidence: float = 0.0
    accuracy_status: Literal[
        "pending",
        "approved",
        "rejected",
        "auto_applied",
        "no_change",
        "rolled_back",
    ] = "pending"
    created_at: str = Field(default_factory=utcnow_iso)
    decided_at: str | None = None
    decided_by: str = ""
    applied_anchor_id: str | None = None


class FreshnessVerdict(BaseModel):
    claim_id: str
    status: FreshnessStatus
    score: int | None = Field(default=None, ge=0, le=100)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    rationale: str = ""
    suggestion: str = ""
    breakdown: dict[str, float] = Field(default_factory=dict)
    evidence: list[EvidenceRef] = Field(default_factory=list)
    anchor_id: str | None = None
    anchor_status: Literal[
        "used", "changed", "needs_revalidation", "unreachable", "not_found"
    ] | None = None
    checked_at: str = Field(default_factory=utcnow_iso)


class DetectorReport(BaseModel):
    id: str
    owner_id: str = ""
    answer: str
    as_of: str
    claims: list[Claim] = Field(default_factory=list)
    verdicts: list[FreshnessVerdict] = Field(default_factory=list)
    overall_score: float | None = None
    stale_claims: int = 0
    conflicted_claims: int = 0
    insufficient_claims: int = 0
    credits: float = 0.0
    llm_cost_usd: float = 0.0
    mode: Literal["live", "replay"] = "live"
    # 新建报告由 detector 显式写入实际版本；缺失（历史报告）保持 unknown，不静默回填。
    policy_version: str = "unknown"
    weights_version: str = "unknown"
    created_at: str = Field(default_factory=utcnow_iso)


class EvidenceSnapshot(BaseModel):
    id: str
    url: str
    canonical_url: str = ""
    title: str = ""
    origin: Literal["wayback", "manual", "official_history", "live"] = "live"
    content_hash: str = ""
    raw_path: str = ""
    text_path: str = ""
    published_at: str | None = None
    updated_at: str | None = None
    fetched_at: str = Field(default_factory=utcnow_iso)
    tier: int = 3
    notes: str = ""


# --------------------------------------------------------------------------- benchmark
class TaskCategory(StrEnum):
    STABLE = "stable"
    TIME_SENSITIVE = "time_sensitive"
    CHANGED = "changed"
    CONFLICTING = "conflicting"


class ExpectedClaim(BaseModel):
    text: str
    claim_type: ClaimType = ClaimType.OTHER
    temporal_sensitivity: TemporalSensitivity | None = None
    expected_relation: Literal["supports", "contradicts", "mentions", "insufficient"] = "supports"
    gold_values: list[str] = Field(default_factory=list)
    notes: str = ""


class BenchmarkTask(BaseModel):
    id: str
    question: str
    as_of: str
    category: TaskCategory = TaskCategory.TIME_SENSITIVE
    expected_claims: list[ExpectedClaim] = Field(default_factory=list)
    reference_evidence: list[str] = Field(default_factory=list)
    gold_values: list[str] = Field(default_factory=list)
    gold_sources: list[str] = Field(default_factory=list)
    hidden: bool = False
    # 已提交到公开 Git 历史的 hidden 题目必须标记为 compromised（无法再视为保密）。
    compromised: bool = False
    notes: str = ""



class AgentSpec(BaseModel):
    id: str
    name: str
    kind: Literal["mock", "retrieval_baseline", "scout", "http", "llm", "python", "cli"] = "mock"
    description: str = ""
    config: dict[str, Any] = Field(default_factory=dict)


class AgentAnswer(BaseModel):
    text: str
    citations: list[str] = Field(default_factory=list)
    tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = ""
    provider: str = ""
    price_table_version: str = ""
    estimated: bool = True
    latency_s: float = 0.0
    cost_usd: float = 0.0
    trace: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None


class TaskResult(BaseModel):
    task_id: str
    agent_id: str
    answer: AgentAnswer
    numeric_accuracy: float = 0.0
    has_citations: bool = False
    citation_count: int = 0
    freshness_score: float | None = None
    stale_claim_rate: float | None = None
    claim_coverage: float = 0.0
    supported_claim_rate: float | None = None
    stable_fact_integrity: float | None = None
    evidence_quality: float | None = None
    score: float = 0.0
    error: str | None = None


class ExperimentManifest(BaseModel):
    """一次 Benchmark 实验的完整、可哈希配置快照（不含秘密明文）。"""

    experiment_id: str
    dataset_id: str = ""
    dataset_version: str = ""
    dataset_hash: str = ""
    task_ids: list[str] = Field(default_factory=list)
    agent_manifest: list[dict[str, Any]] = Field(default_factory=list)
    model_provider: str = ""
    model_name: str = ""
    model_version: str = ""
    adapter_protocol_version: str = ""
    tool_configuration: dict[str, Any] = Field(default_factory=dict)
    retrieval_configuration: dict[str, Any] = Field(default_factory=dict)
    budget_configuration: dict[str, Any] = Field(default_factory=dict)
    timeout_configuration: dict[str, Any] = Field(default_factory=dict)
    evaluator_version: str = ""
    policy_version: str = ""
    weights_version: str = ""
    prompt_version: str = ""
    code_commit: str = "unknown"
    dependency_lock_hash: str = ""
    snapshot_ids: list[str] = Field(default_factory=list)
    config_hash: str = ""
    result_hash: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    status: str = "running"


class BenchSession(BaseModel):
    id: str
    status: Literal["running", "done", "failed"] = "running"
    agent_ids: list[str] = Field(default_factory=list)
    task_ids: list[str] = Field(default_factory=list)
    dataset_version: str = ""
    config_hash: str = ""
    manifest: ExperimentManifest | None = None
    result_hash: str | None = None
    supersedes: str | None = None
    created_at: str = Field(default_factory=utcnow_iso)
    finished_at: str | None = None
    error: str | None = None

















