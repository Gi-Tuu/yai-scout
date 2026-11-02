from datetime import UTC, datetime, timedelta

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
    TemporalSensitivity,
)

TARGET = "2026-11-01"


def claim(
    text: str = "Tavily 免费计划每月提供 500 credits。",
    claim_type: ClaimType = ClaimType.PRICING,
    sensitivity: TemporalSensitivity = TemporalSensitivity.SENSITIVE,
    window: int = 180,
    numbers: list[str] | None = None,
) -> Claim:
    return Claim(
        id="c1",
        text=text,
        type=claim_type,
        numbers=numbers if numbers is not None else ["500"],
        target_time=TARGET,
        temporal_sensitivity=sensitivity,
        validity_window_days=window,
    )


def evidence(
    relation: str,
    days_ago: int,
    tier: int = 1,
    *,
    url: str = "https://example.com/x",
) -> EvidenceRef:
    published = datetime(2026, 11, 1, tzinfo=UTC) - timedelta(days=days_ago)
    return EvidenceRef(
        url=url,
        title="source",
        domain="example.com",
        published_at=published.isoformat(),
        tier=tier,
        relation=relation,  # type: ignore[arg-type]
    )


def score(items: list[EvidenceRef], c: Claim | None = None, *, allow_future: bool = True):
    return score_claim(
        c or claim(), items, as_of=as_of_datetime(TARGET), allow_future=allow_future
    )


def test_parse_published_handles_rfc2822():
    parsed = parse_published("Tue, 04 Feb 2025 00:00:00 GMT")
    assert parsed is not None and parsed.year == 2025


def test_t1_stable_fact_with_old_source_is_fresh():
    c = claim(
        "Python 3.12 于 2023 年发布。",
        ClaimType.DATE,
        TemporalSensitivity.STABLE,
        3650,
        ["2023"],
    )
    verdict = score([evidence("supports", 1000, tier=1)], c)
    assert verdict.status is FreshnessStatus.FRESH
    assert verdict.score is not None and verdict.score >= 65


def test_t2_weak_source_only_is_insufficient():
    verdict = score([evidence("supports", 2, tier=4)])
    assert verdict.status is FreshnessStatus.INSUFFICIENT


def test_t3_mentions_only_is_insufficient():
    verdict = score([evidence("mentions", 2, tier=1)])
    assert verdict.status is FreshnessStatus.INSUFFICIENT
    assert verdict.score is None


def test_t4_authoritative_contradiction_is_stale():
    verdict = score([evidence("contradicts", 3, tier=1)])
    assert verdict.status is FreshnessStatus.STALE
    assert verdict.score is not None and verdict.score < 55


def test_t5_authoritative_conflict_is_conflicted():
    verdict = score(
        [evidence("supports", 3, tier=1), evidence("contradicts", 4, tier=1)]
    )
    assert verdict.status is FreshnessStatus.CONFLICTED


def test_t6_no_evidence_is_insufficient_with_null_score():
    verdict = score([])
    assert verdict.status is FreshnessStatus.INSUFFICIENT
    assert verdict.score is None
    assert verdict.confidence <= 0.3


def test_slow_law_with_weak_support_is_insufficient():
    c = claim(
        "Bifrost 使用 AGPL-3.0 许可证。",
        ClaimType.LAW,
        TemporalSensitivity.SLOW,
        730,
        [],
    )
    verdict = score([evidence("supports", 2, tier=4)], c)
    assert verdict.status is FreshnessStatus.INSUFFICIENT


def test_t7_support_is_fresh_and_explainable():
    verdict = score([evidence("supports", 1, tier=1)])
    assert verdict.status is FreshnessStatus.FRESH
    assert set(verdict.breakdown) == {
        "relation",
        "recency",
        "authority",
        "coverage",
        "date_coverage",
    }
    assert 0 <= verdict.confidence <= 1


def test_t8_version_mismatch_is_stale():
    c = claim(
        "YAI Agent Core 当前版本是 0.25.0。",
        ClaimType.VERSION,
        TemporalSensitivity.SENSITIVE,
        180,
        ["0.25.0"],
    )
    verdict = score([evidence("contradicts", 2, tier=1)], c)
    assert verdict.status is FreshnessStatus.STALE


def test_t9_replay_excludes_future_evidence():
    future = evidence("supports", -10, tier=1)  # published after target
    verdict = score([future], allow_future=False)
    assert verdict.status is FreshnessStatus.INSUFFICIENT


def test_t10_stable_fact_old_support_not_penalized():
    c = claim(
        "光速约为 299792 km/s。",
        ClaimType.STATISTIC,
        TemporalSensitivity.STABLE,
        3650,
        ["299792"],
    )
    verdict = score([evidence("supports", 2000, tier=2)], c)
    assert verdict.status is FreshnessStatus.FRESH


def test_overall_score_ignores_nulls():
    c = claim()
    fresh = score([evidence("supports", 1, tier=1)], c)
    unknown = score([], c)
    assert overall_score([fresh, unknown]) == fresh.score

def test_version_claim_uses_only_newest_release_timestamp():
    c = claim(
        "YAI Agent Core 当前版本是 0.24.0",
        ClaimType.VERSION,
        TemporalSensitivity.SENSITIVE,
        180,
        ["0.24.0"],
    )
    newest = EvidenceRef(
        url="https://github.com/Gi-Tuu/yai-agent-core/releases/tag/v0.24.0",
        domain="github.com",
        published_at="2026-10-27T08:11:51Z",
        tier=2,
        relation="supports",
    )
    older = EvidenceRef(
        url="https://github.com/Gi-Tuu/yai-agent-core/releases/tag/v0.23.0",
        domain="github.com",
        published_at="2026-10-27T04:30:43Z",
        tier=2,
        relation="contradicts",
    )
    verdict = score_claim(
        c,
        [newest, older],
        as_of=datetime(2026, 10, 28, tzinfo=UTC),
    )
    assert verdict.status is FreshnessStatus.FRESH

def test_old_authoritative_support_is_not_fresh():
    verdict = score([evidence("supports", 1000, tier=1)])
    assert verdict.status is FreshnessStatus.INSUFFICIENT
    assert verdict.score is None


def test_undated_authoritative_support_is_not_fresh():
    ev = EvidenceRef(
        url="https://example.com/x",
        title="official",
        domain="example.com",
        tier=1,
        relation="supports",
    )
    verdict = score([ev])
    assert verdict.status is FreshnessStatus.INSUFFICIENT

def test_old_contradiction_is_not_current_stale():
    verdict = score([evidence("contradicts", 1000, tier=1)])
    assert verdict.status is FreshnessStatus.INSUFFICIENT


def test_old_support_plus_new_contradiction_is_stale_not_conflicted():
    verdict = score(
        [evidence("supports", 1000, tier=1), evidence("contradicts", 2, tier=1)]
    )
    assert verdict.status is FreshnessStatus.STALE


def test_old_contradiction_plus_new_support_is_fresh():
    verdict = score(
        [evidence("contradicts", 1000, tier=1), evidence("supports", 2, tier=1)]
    )
    assert verdict.status is FreshnessStatus.FRESH


def test_future_support_never_proves_current():
    verdict = score([evidence("supports", -10, tier=1)])
    assert verdict.status is FreshnessStatus.INSUFFICIENT


def test_undated_contradiction_is_not_current_stale():
    ev = EvidenceRef(
        url="https://example.com/x",
        title="official",
        domain="example.com",
        tier=1,
        relation="contradicts",
    )
    verdict = score([ev])
    assert verdict.status is FreshnessStatus.INSUFFICIENT


def test_stable_old_contradiction_is_insufficient():
    c = claim(
        "光速约为 299792 km/s。",
        ClaimType.STATISTIC,
        TemporalSensitivity.STABLE,
        3650,
        ["299792"],
    )
    verdict = score([evidence("contradicts", 4000, tier=1)], c)
    assert verdict.status is FreshnessStatus.INSUFFICIENT


