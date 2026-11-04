"""Claim-level Freshness verdict evaluation.

This evaluates the deterministic scorer directly against fixed evidence and
explicit gold statuses. It intentionally does not call Tavily or an LLM, so the
result is reproducible and can distinguish "answer was right" from "freshness
judgement was right".
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from ..domain.models import (
    Claim,
    ClaimType,
    EvidenceRef,
    FreshnessStatus,
    TemporalSensitivity,
)
from .freshness import as_of_datetime, score_claim

VERDICT_DATASET_VERSION = "freshness-verdicts/1.0"
VERDICT_STATUSES: tuple[str, ...] = (
    FreshnessStatus.FRESH.value,
    FreshnessStatus.STALE.value,
    FreshnessStatus.CONFLICTED.value,
    FreshnessStatus.INSUFFICIENT.value,
    FreshnessStatus.UNKNOWN.value,
)


def default_cases_path() -> Path:
    return Path(__file__).resolve().parents[3] / "benchmarks" / "freshness_verdicts.json"


class VerdictClaim(BaseModel):
    text: str
    type: ClaimType = ClaimType.OTHER
    temporal_sensitivity: TemporalSensitivity = TemporalSensitivity.SENSITIVE
    target_time: str | None = None


class VerdictCase(BaseModel):
    id: str
    claim: VerdictClaim
    evidence: list[EvidenceRef] = Field(default_factory=list)
    expected_status: FreshnessStatus | None = None
    case_type: str = "standard"
    tags: list[str] = Field(default_factory=list)
    notes: str = ""


@dataclass
class CaseResult:
    id: str
    expected: str
    predicted: str
    matched: bool
    score: int | None
    confidence: float
    rationale: str
    evidence_count: int
    case_type: str = "standard"


@dataclass
class VerdictEvalReport:
    dataset_version: str
    total: int
    matched: int
    accuracy: float
    abstention_rate: float
    status_support: dict[str, int] = field(default_factory=dict)
    status_predicted: dict[str, int] = field(default_factory=dict)
    precision: dict[str, float] = field(default_factory=dict)
    recall: dict[str, float] = field(default_factory=dict)
    f1: dict[str, float] = field(default_factory=dict)
    confusion: dict[str, dict[str, int]] = field(default_factory=dict)
    scored_cases: int = 0
    mean_score: float | None = None
    case_type_support: dict[str, int] = field(default_factory=dict)
    case_type_matched: dict[str, int] = field(default_factory=dict)
    case_type_accuracy: dict[str, float] = field(default_factory=dict)
    cases: list[CaseResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_verdict_cases(path: str | Path | None = None) -> tuple[str, list[VerdictCase]]:
    target = Path(path) if path else default_cases_path()
    payload = json.loads(target.read_text(encoding="utf-8"))
    version = str(payload.get("version") or "unknown")
    cases = [VerdictCase.model_validate(item) for item in payload.get("cases", [])]
    if not cases:
        raise ValueError(f"no verdict cases in {target}")
    return version, cases


def evaluate_verdict_cases(
    cases: list[VerdictCase], *, as_of: str = "2026-11-01",
    dataset_version: str = VERDICT_DATASET_VERSION,
) -> VerdictEvalReport:
    results: list[CaseResult] = []
    support = {status: 0 for status in VERDICT_STATUSES}
    predicted_count = {status: 0 for status in VERDICT_STATUSES}
    confusion = {
        expected: {predicted: 0 for predicted in VERDICT_STATUSES}
        for expected in VERDICT_STATUSES
    }
    scores: list[int] = []
    type_support: dict[str, int] = {}
    type_matched: dict[str, int] = {}

    for case in cases:
        if case.expected_status is None:
            raise ValueError(f"case {case.id} has no expected_status")
        claim = Claim(
            id=case.id,
            text=case.claim.text,
            type=case.claim.type,
            temporal_sensitivity=case.claim.temporal_sensitivity,
            target_time=case.claim.target_time or as_of,
        )
        verdict = score_claim(
            claim,
            case.evidence,
            as_of=as_of_datetime(as_of),
        )
        expected = case.expected_status.value
        predicted = verdict.status.value
        support[expected] += 1
        predicted_count[predicted] += 1
        confusion[expected][predicted] += 1
        is_match = expected == predicted
        type_support[case.case_type] = type_support.get(case.case_type, 0) + 1
        if is_match:
            type_matched[case.case_type] = type_matched.get(case.case_type, 0) + 1
        if verdict.score is not None:
            scores.append(verdict.score)
        results.append(CaseResult(
            id=case.id,
            expected=expected,
            predicted=predicted,
            matched=is_match,
            score=verdict.score,
            confidence=verdict.confidence,
            rationale=verdict.rationale,
            evidence_count=len(case.evidence),
            case_type=case.case_type,
        ))

    total = len(results)
    matched = sum(1 for result in results if result.matched)
    precision: dict[str, float] = {}
    recall: dict[str, float] = {}
    f1: dict[str, float] = {}
    for status in VERDICT_STATUSES:
        true_positive = confusion[status][status]
        predicted_for_status = predicted_count[status]
        support_for_status = support[status]
        precision[status] = (
            round(true_positive / predicted_for_status, 4)
            if predicted_for_status else 0.0
        )
        recall[status] = (
            round(true_positive / support_for_status, 4)
            if support_for_status else 0.0
        )
        denominator = precision[status] + recall[status]
        f1[status] = (
            round(2 * precision[status] * recall[status] / denominator, 4)
            if denominator else 0.0
        )

    abstained = predicted_count[FreshnessStatus.INSUFFICIENT.value] + predicted_count[
        FreshnessStatus.UNKNOWN.value
    ]
    return VerdictEvalReport(
        dataset_version=dataset_version,
        total=total,
        matched=matched,
        accuracy=round(matched / total, 4) if total else 0.0,
        abstention_rate=round(abstained / total, 4) if total else 0.0,
        status_support=support,
        status_predicted=predicted_count,
        precision=precision,
        recall=recall,
        f1=f1,
        confusion=confusion,
        scored_cases=len(scores),
        mean_score=round(sum(scores) / len(scores), 1) if scores else None,
        case_type_support=type_support,
        case_type_matched=type_matched,
        case_type_accuracy={
            name: round(type_matched.get(name, 0) / total, 4)
            for name, total in type_support.items()
        },
        cases=results,
    )


def render_text(report: VerdictEvalReport) -> str:
    lines = [
        f"dataset={report.dataset_version}",
        f"accuracy={report.accuracy:.2%} ({report.matched}/{report.total})",
        f"abstention_rate={report.abstention_rate:.2%}",
        f"scored_cases={report.scored_cases} mean_score={report.mean_score}",
        "case_type=" + ", ".join(
            f"{name}:{report.case_type_accuracy[name]:.2%}"
            for name in sorted(report.case_type_accuracy)
        ),
        "",
        "status       support  predicted  precision  recall  f1",
    ]
    for status in VERDICT_STATUSES:
        lines.append(
            f"{status:<12} {report.status_support[status]:>7} "
            f"{report.status_predicted[status]:>10} "
            f"{report.precision[status]:>10.2%} "
            f"{report.recall[status]:>6.2%} {report.f1[status]:>6.2%}"
        )
    mismatches = [case for case in report.cases if not case.matched]
    if mismatches:
        lines.extend(["", "mismatches:"])
        for case in mismatches:
            lines.append(
                f"  {case.id}: expected={case.expected} predicted={case.predicted} "
                f"score={case.score} evidence={case.evidence_count}"
            )
    return "\n".join(lines)



def load_verdict_worksheet(path: str | Path) -> tuple[str, list[VerdictCase]]:
    """Load a worksheet whose cases intentionally have no gold status."""
    target = Path(path)
    payload = json.loads(target.read_text(encoding="utf-8"))
    version = str(payload.get("version") or "unknown")
    cases = [VerdictCase.model_validate(item) for item in payload.get("cases", [])]
    if not cases:
        raise ValueError(f"no verdict cases in {target}")
    return version, cases


def load_verdict_labels(path: str | Path) -> dict[str, str]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    labels = payload.get("labels")
    if not isinstance(labels, dict):
        raise ValueError("labels file must contain a labels object")
    return {str(key): str(value).lower() for key, value in labels.items()}


def evaluate_labeled_worksheet(
    worksheet_path: str | Path,
    labels_path: str | Path,
    *,
    as_of: str | None = None,
    dataset_version: str | None = None,
) -> VerdictEvalReport:
    version, cases = load_verdict_worksheet(worksheet_path)
    labels = load_verdict_labels(labels_path)
    labeled: list[VerdictCase] = []
    missing: list[str] = []
    for case in cases:
        raw = labels.get(case.id)
        if raw is None:
            missing.append(case.id)
            continue
        try:
            status = FreshnessStatus(raw)
        except ValueError as exc:
            raise ValueError(f"invalid label for {case.id}: {raw!r}") from exc
        labeled.append(case.model_copy(update={"expected_status": status}))
    if missing:
        raise ValueError("missing labels for: " + ", ".join(missing))
    effective_version = dataset_version or version
    return evaluate_verdict_cases(
        labeled,
        as_of=as_of or "2026-11-01",
        dataset_version=effective_version,
    )
