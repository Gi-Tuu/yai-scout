from datetime import UTC, datetime

from yai_scout.detector.freshness import (
    as_of_datetime,
    overall_score,
    parse_published,
    score_claim,
)
from yai_scout.domain.models import (
    Claim,
    ClaimType,
    EvidenceRef,
    FreshnessStatus,
)


def claim(value: str = "500") -> Claim:
    return Claim(
        id="c1",
        text=f"Tavily 免费计划每月提供 {value} credits。",
        type=ClaimType.PRICING,
        numbers=[value],
    )


def evidence(relation: str, days_ago: int, tier: int = 2) -> EvidenceRef:
    published = datetime.now(UTC).timestamp() - days_ago * 86400
    return EvidenceRef(
        url="https://example.com/x",
        title="source",
        domain="example.com",
        published_at=datetime.fromtimestamp(published, UTC).isoformat(),
        tier=tier,
        relation=relation,  # type: ignore[arg-type]
    )


def test_parse_published_handles_rfc2822():
    parsed = parse_published("Tue, 04 Feb 2025 00:00:00 GMT")
    assert parsed is not None and parsed.year == 2025


def test_stale_when_recent_contradiction():
    verdict = score_claim(
        claim(), [evidence("contradicts", 3)], as_of=datetime.now(UTC)
    )
    assert verdict.status is FreshnessStatus.STALE
    assert verdict.score < 45


def test_fresh_when_recent_support():
    verdict = score_claim(
        claim(), [evidence("supports", 2, tier=1)], as_of=datetime.now(UTC)
    )
    assert verdict.status is FreshnessStatus.FRESH
    assert verdict.score >= 65


def test_pricing_claim_with_only_weak_sources_is_uncertain():
    verdict = score_claim(
        claim(), [evidence("supports", 2, tier=4)], as_of=datetime.now(UTC)
    )
    assert verdict.status is FreshnessStatus.UNCERTAIN
    assert verdict.score <= 60


def test_stale_when_old_but_authoritative_contradiction():
    verdict = score_claim(
        claim(), [evidence("contradicts", 400, tier=1)], as_of=datetime.now(UTC)
    )
    assert verdict.status is FreshnessStatus.STALE
    assert verdict.score < 55


def test_unverifiable_without_evidence():
    verdict = score_claim(claim(), [], as_of=datetime.now(UTC))
    assert verdict.status is FreshnessStatus.UNVERIFIABLE


def test_overall_score_average():
    v1 = score_claim(claim(), [evidence("supports", 1)], as_of=datetime.now(UTC))
    v2 = score_claim(claim("900"), [evidence("contradicts", 1)], as_of=datetime.now(UTC))
    assert overall_score([v1, v2]) == round((v1.score + v2.score) / 2)


def test_as_of_datetime_defaults():
    assert as_of_datetime("2026-11-01").year == 2026
