from __future__ import annotations

from yai_scout.detector.freshness import coverage_stats, date_coverage_stats
from yai_scout.domain.models import EvidenceRef, FreshnessStatus, FreshnessVerdict


def _verdict(status: FreshnessStatus, score: int | None) -> FreshnessVerdict:
    return FreshnessVerdict(claim_id="c", status=status, score=score)


def test_coverage_counts_scored_and_insufficient_claims():
    verdicts = [
        _verdict(FreshnessStatus.FRESH, 80),
        _verdict(FreshnessStatus.INSUFFICIENT, None),
        _verdict(FreshnessStatus.UNKNOWN, None),
        _verdict(FreshnessStatus.STALE, 40),
    ]
    stats = coverage_stats(verdicts, 4)
    assert stats["total_claims"] == 4
    assert stats["scored_claims"] == 2
    assert stats["insufficient_claims"] == 1
    assert stats["unknown_claims"] == 1
    assert stats["coverage"] == 0.5
    assert stats["abstention_rate"] == 0.5


def test_coverage_is_zero_for_empty_report():
    stats = coverage_stats([], 0)
    assert stats["coverage"] == 0.0
    assert stats["abstention_rate"] == 0.0

def test_publication_date_coverage_counts_dated_evidence():
    dated = EvidenceRef(url="https://a", published_at="2026-10-01T00:00:00Z")
    undated = EvidenceRef(url="https://b")
    verdicts = [
        FreshnessVerdict(
            claim_id="c",
            status=FreshnessStatus.FRESH,
            score=80,
            evidence=[dated, undated],
        )
    ]
    stats = date_coverage_stats(verdicts)
    assert stats["dated_evidence"] == 1
    assert stats["undated_evidence"] == 1
    assert stats["publication_date_coverage"] == 0.5
