from __future__ import annotations

from yai_scout.detector.freshness import as_of_datetime, score_claim
from yai_scout.domain.models import (
    Claim,
    ClaimType,
    EvidenceRef,
    FreshnessStatus,
    TemporalSensitivity,
)


def test_cross_source_authority_conflict_is_not_collapsed() -> None:
    claim = Claim(
        id="c",
        text="YAI 当前版本是 0.24.0",
        type=ClaimType.VERSION,
        numbers=["0.24.0"],
        temporal_sensitivity=TemporalSensitivity.SENSITIVE,
    )
    evidence = [
        EvidenceRef(
            url="https://official.example/releases",
            domain="official.example",
            published_at="2026-11-01T00:00:00Z",
            tier=1,
            relation="contradicts",
        ),
        EvidenceRef(
            url="https://other.example/releases",
            domain="other.example",
            published_at="2026-11-04T00:00:00Z",
            tier=1,
            relation="supports",
        ),
    ]
    verdict = score_claim(
        claim,
        evidence,
        as_of=as_of_datetime("2026-11-05"),
        allow_future=False,
    )
    assert verdict.status is FreshnessStatus.CONFLICTED
