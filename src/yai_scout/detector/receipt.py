"""Versioned evidence receipt MVP (no signatures, no blockchain)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..domain.models import (
    ClaimAssessment,
    DetectorReport,
    EvidenceRef,
)
from .versions import POLICY_VERSION, WEIGHTS_VERSION

RECEIPT_VERSION = "yai_scout.receipt.v1"


class ClaimReceipt(BaseModel):
    claim_id: str
    claim_text: str = ""
    status: str
    score: int | None = None
    rationale: str = ""
    claim_assessment: ClaimAssessment | None = None
    evidence: list[EvidenceRef] = Field(default_factory=list)


class ReportReceipt(BaseModel):
    receipt_version: str = RECEIPT_VERSION
    report_id: str
    as_of: str
    mode: str
    policy_version: str
    weights_version: str
    coverage: float = 0.0
    claims: list[ClaimReceipt] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


def _limitations(report: DetectorReport) -> list[str]:
    items = [
        "content hashes identify the recorded evidence text, not source authenticity",
        "AUTO_UPDATE remains disabled; this receipt is not an automatic fact update",
    ]
    evidence = [item for verdict in report.verdicts for item in verdict.evidence]
    if any(item.evidence_kind.value == "search_snippet" for item in evidence):
        items.append("search snippets are not full-page verification")
    if any(item.published_at is None for item in evidence):
        items.append("publication time is unknown for some evidence")
    if report.coverage < 1.0:
        items.append("not every claim was scored; see coverage")
    if report.mode == "replay":
        items.append("replay uses archived snapshots available at the target time")
    return items


def build_report_receipt(report: DetectorReport) -> ReportReceipt:
    claims = [
        ClaimReceipt(
            claim_id=verdict.claim_id,
            claim_text=next(
                (claim.text for claim in report.claims if claim.id == verdict.claim_id),
                "",
            ),
            status=verdict.status.value,
            score=verdict.score,
            rationale=verdict.rationale,
            claim_assessment=verdict.claim_assessment,
            evidence=verdict.evidence,
        )
        for verdict in report.verdicts
    ]
    return ReportReceipt(
        report_id=report.id,
        as_of=report.as_of,
        mode=report.mode,
        policy_version=report.policy_version or POLICY_VERSION,
        weights_version=report.weights_version or WEIGHTS_VERSION,
        coverage=report.coverage,
        claims=claims,
        limitations=_limitations(report),
    )

