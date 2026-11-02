from __future__ import annotations

from yai_scout.detector.freshness import coverage_stats
from yai_scout.domain.models import FreshnessStatus, FreshnessVerdict


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
