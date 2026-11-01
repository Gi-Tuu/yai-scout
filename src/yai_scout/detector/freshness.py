"""Freshness 评分与判定（规则版，可解释）。

评分不是"概率"，而是证据强度的确定性合成：
- 近 120 天内支持证据 +30
- 近 120 天内矛盾证据 -40
- 完全没有近一年内证据 -20
- 一手/权威来源分别 +10/+5
- 基础分 50，clamp 到 0–100
状态：stale（矛盾且低分）/ fresh（高分且有支持）/ unverifiable（无证据）/ uncertain（其余）
"""

from __future__ import annotations

from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

from ..domain.models import Claim, ClaimType, EvidenceRef, FreshnessStatus, FreshnessVerdict

RECENT_DAYS = 120
YEAR_DAYS = 365


def parse_published(value: str | None) -> datetime | None:
    """尽量解析 Tavily 的 published_date（RFC 2822 / ISO / 纯日期）。"""
    if not value:
        return None
    raw = value.strip()
    for parser in (parsedate_to_datetime, datetime.fromisoformat):
        try:
            dt = parser(raw)
        except (TypeError, ValueError):
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    return None


def days_between(published: datetime | None, as_of: datetime) -> int | None:
    if published is None:
        return None
    return max(0, (as_of - published).days)


def score_claim(
    claim: Claim,
    evidence: list[EvidenceRef],
    *,
    as_of: datetime,
    recent_days: int = RECENT_DAYS,
) -> FreshnessVerdict:
    score = 50
    supports_any = False
    supports_recent = False
    contradicts_any = False
    contradicts_recent = False
    best_tier = 4
    support_tiers: list[int] = []

    for item in evidence:
        published = parse_published(item.published_at)
        days = days_between(published, as_of)
        is_recent = days is not None and days <= recent_days
        is_within_year = days is not None and days <= YEAR_DAYS
        if is_within_year:
            best_tier = min(best_tier, item.tier)
        if item.relation == "supports":
            supports_any = True
            support_tiers.append(item.tier)
            if is_recent:
                supports_recent = True
        if item.relation == "contradicts":
            contradicts_any = True
            if is_recent:
                contradicts_recent = True

    if supports_recent:
        score += 30
    elif supports_any:
        score += 15
    if contradicts_recent:
        score -= 40
    elif contradicts_any:
        score -= 25
    if evidence and not any(
        (days_between(parse_published(e.published_at), as_of) or 10_000) <= YEAR_DAYS
        for e in evidence
    ):
        score -= 20
    if best_tier == 1:
        score += 10
    elif best_tier == 2:
        score += 5
    score = max(0, min(100, score))

    if not evidence:
        status = FreshnessStatus.UNVERIFIABLE
        rationale = "没有检索到可核验来源"
    elif contradicts_any and score < 55:
        status = FreshnessStatus.STALE
        rationale = "检索到的来源给出了不同的值/事实，判定可能过时"
    elif supports_any and score >= 65:
        status = FreshnessStatus.FRESH
        rationale = "权威/一般来源支持该说法"
    else:
        status = FreshnessStatus.UNCERTAIN
        rationale = "证据不足或时效性无法确认，建议人工复核"

    # 价格/版本/法规类 claim：只有非权威来源支持时，不能判 fresh（防止"博客说新就是新"）。
    strict_types = {ClaimType.PRICING, ClaimType.VERSION, ClaimType.LAW}
    if (
        status is FreshnessStatus.FRESH
        and claim.type in strict_types
        and not any(tier <= 2 for tier in support_tiers)
    ):
        status = FreshnessStatus.UNCERTAIN
        score = min(score, 60)
        rationale = "仅非权威来源支持，时效性存疑"

    return FreshnessVerdict(
        claim_id=claim.id,
        status=status,
        score=score,
        rationale=rationale,
        evidence=evidence[:5],
    )


def overall_score(verdicts: list[FreshnessVerdict]) -> int:
    if not verdicts:
        return 0
    return round(sum(v.score for v in verdicts) / len(verdicts))


def as_of_datetime(value: str) -> datetime:
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        dt = datetime(2026, 11, 1, tzinfo=UTC)
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt
