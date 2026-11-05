from __future__ import annotations

from yai_scout.detector.freshness import as_of_datetime, score_claim
from yai_scout.domain.models import (
    Claim,
    ClaimType,
    EvidenceRef,
    FreshnessStatus,
    TemporalSensitivity,
)


def _claim() -> Claim:
    return Claim(
        id="c",
        text="YAI 当前版本是 0.24.0",
        type=ClaimType.VERSION,
        numbers=["0.24.0"],
        temporal_sensitivity=TemporalSensitivity.SENSITIVE,
    )


def test_cross_source_authority_conflict_is_not_collapsed() -> None:
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
        _claim(), evidence, as_of=as_of_datetime("2026-11-05"), allow_future=False
    )
    assert verdict.status is FreshnessStatus.CONFLICTED


def test_same_host_different_github_repos_are_not_merged() -> None:
    evidence = [
        EvidenceRef(
            url="https://github.com/acme/widget/releases/tag/v1.0.0",
            domain="github.com",
            published_at="2026-11-01T00:00:00Z",
            tier=2,
            relation="contradicts",
        ),
        EvidenceRef(
            url="https://github.com/other/widget/releases/tag/v1.0.0",
            domain="github.com",
            published_at="2026-11-04T00:00:00Z",
            tier=2,
            relation="supports",
        ),
    ]
    verdict = score_claim(
        _claim(), evidence, as_of=as_of_datetime("2026-11-05"), allow_future=False
    )
    assert verdict.status is FreshnessStatus.CONFLICTED


def test_same_source_same_timestamp_is_order_independent() -> None:
    first = EvidenceRef(
        url="https://github.com/acme/widget/releases/tag/v1.0.0",
        domain="github.com",
        published_at="2026-11-04T00:00:00Z",
        tier=1,
        relation="contradicts",
    )
    second = EvidenceRef(
        url="https://github.com/acme/widget/releases/tag/v1.0.0",
        domain="github.com",
        published_at="2026-11-04T00:00:00Z",
        tier=1,
        relation="supports",
    )
    first_order = score_claim(
        _claim(), [first, second], as_of=as_of_datetime("2026-11-05"), allow_future=False
    )
    second_order = score_claim(
        _claim(), [second, first], as_of=as_of_datetime("2026-11-05"), allow_future=False
    )
    assert first_order.status is FreshnessStatus.CONFLICTED
    assert second_order.status is FreshnessStatus.CONFLICTED
