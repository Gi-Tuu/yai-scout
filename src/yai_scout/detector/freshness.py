"""Freshness 判定与评分（v2：先分类、再关系、后评分）。

决策表与分数公式见 docs/spec-freshness-scoring.md。
原则：无证据 = INSUFFICIENT；低权威单源不判 FRESH；稳定事实不因来源旧扣分；
有权威冲突判 CONFLICTED；分数必须可拆解。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime

from ..domain.models import (
    Claim,
    ClaimType,
    EvidenceRef,
    FreshnessStatus,
    FreshnessVerdict,
    TemporalSensitivity,
)
from .temporal import DEFAULT_WINDOWS
from .versions import POLICY_VERSION, WEIGHTS_VERSION

DEFAULT_WEIGHTS = {"relation": 0.6, "recency": 0.1, "authority": 0.3}
TIER_WEIGHTS = {1: 1.0, 2: 0.8, 3: 0.5, 4: 0.25}
RECENT_DAYS = 120
YEAR_DAYS = 365


def parse_published(value: str | None) -> datetime | None:
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
    return (as_of - published).days


def as_of_datetime(value: str) -> datetime:
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        dt = datetime(2026, 11, 1, tzinfo=UTC)
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt


def _target_time(claim: Claim, fallback: datetime) -> datetime:
    return as_of_datetime(claim.target_time) if claim.target_time else fallback


def _sensitivity(claim: Claim) -> TemporalSensitivity:
    return claim.temporal_sensitivity or TemporalSensitivity.SENSITIVE


def _window(claim: Claim, sensitivity: TemporalSensitivity) -> int:
    return claim.validity_window_days or DEFAULT_WINDOWS[sensitivity]


def score_claim(
    claim: Claim,
    evidence: list[EvidenceRef],
    *,
    as_of: datetime | None = None,
    allow_future: bool = True,
    weights: dict[str, float] | None = None,
) -> FreshnessVerdict:
    """按决策表给出状态 + 可空分数 + 拆解。"""
    fallback = as_of or datetime.now(UTC)
    target = _target_time(claim, fallback)
    sensitivity = _sensitivity(claim)
    window = _window(claim, sensitivity)
    strict = sensitivity in {TemporalSensitivity.SENSITIVE, TemporalSensitivity.VOLATILE}

    usable: list[EvidenceRef] = []
    for item in evidence:
        published = parse_published(item.updated_at or item.published_at)
        if published is None:
            usable.append(item)  # 时间未知：仅当 mentions 使用，不参与时效判断
            continue
        age = (target - published).days
        if age < 0 and not allow_future:
            continue  # 历史回放：未来证据不可用
        usable.append(item)

    # 版本类 claim：只比较"最新一次发布"，旧版本不是矛盾证据。
    if claim.type is ClaimType.VERSION and usable:
        dated = [
            (parse_published(item.updated_at or item.published_at), item) for item in usable
        ]
        known = [when for when, _ in dated if when is not None]
        if known:
            newest = max(known)
            cutoff = newest - timedelta(days=1)
            usable = [item for when, item in dated if when is None or when >= cutoff]

    effective = [e for e in usable if e.relation in {"supports", "contradicts"}]
    supports = [e for e in effective if e.relation == "supports"]
    contradicts = [e for e in effective if e.relation == "contradicts"]
    auth_supports = [e for e in supports if e.tier <= 2]
    auth_contradicts = [e for e in contradicts if e.tier <= 2]

    status: FreshnessStatus
    if not effective:
        status = FreshnessStatus.INSUFFICIENT
        rationale = "没有足够证据（仅提及或检索为空），不能判断是否过时"
    elif auth_contradicts and auth_supports:
        status = FreshnessStatus.CONFLICTED
        rationale = "权威来源之间存在冲突，并列展示，不强行给出单一结论"
    elif auth_contradicts:
        status = FreshnessStatus.STALE
        rationale = "权威来源给出了不同的值/事实，判定可能过时"
    elif auth_supports:
        status = FreshnessStatus.FRESH
        rationale = "权威来源支持该说法"
    elif supports and sensitivity is TemporalSensitivity.STABLE:
        status = FreshnessStatus.FRESH
        rationale = "稳定事实，一般来源支持即可（不因来源旧扣分）"
    elif strict and supports and _only_expired(supports, target, window):
        status = FreshnessStatus.STALE
        rationale = f"仅有超出有效期（{window} 天）的旧证据，判定过时"
    else:
        status = FreshnessStatus.INSUFFICIENT
        rationale = "只有非权威来源支持，证据强度不足"

    relation_raw = sum(
        (1.0 if e.relation == "supports" else -1.0) * TIER_WEIGHTS.get(e.tier, 0.25)
        for e in effective
    )
    relation_norm = max(0.0, min(1.0, (relation_raw + 1.0) / 2.0))
    recency = (
        1.0
        if sensitivity is TemporalSensitivity.STABLE
        else _recency(supports, target, window)
    )
    authority = max((TIER_WEIGHTS.get(e.tier, 0.25) for e in effective), default=0.0)
    coverage = 1.0 if effective else 0.0
    score: int | None = None
    if coverage:
        w = weights or DEFAULT_WEIGHTS
        score = round(
            100
            * (
                w["relation"] * relation_norm
                + w["recency"] * recency
                + w["authority"] * authority
            )
        )
        if status is FreshnessStatus.STALE:
            score = min(score, 50)
        elif status is FreshnessStatus.CONFLICTED:
            score = min(score, 60)

    n_eff = len(effective)
    agreement = 1.0 - (len(contradicts) / max(1, n_eff))
    confidence = round(
        0.4 * authority + 0.3 * min(1.0, n_eff / 2.0) + 0.3 * agreement,
        2,
    )
    if status in {FreshnessStatus.INSUFFICIENT, FreshnessStatus.UNKNOWN}:
        confidence = min(confidence, 0.3)

    return FreshnessVerdict(
        claim_id=claim.id,
        status=status,
        score=score,
        confidence=confidence,
        rationale=rationale,
        breakdown={
            "relation": round(relation_norm, 3),
            "recency": round(recency, 3),
            "authority": round(authority, 3),
            "coverage": coverage,
        },
        evidence=usable[:5],
    )


def _age_days(item: EvidenceRef, target: datetime) -> int | None:
    published = parse_published(item.updated_at or item.published_at)
    return None if published is None else (target - published).days


def _only_expired(supports: list[EvidenceRef], target: datetime, window: int) -> bool:
    known: list[int] = []
    for item in supports:
        age = _age_days(item, target)
        if age is not None:
            known.append(age)
    return bool(known) and all(age > window for age in known)


def _recency(supports: list[EvidenceRef], target: datetime, window: int) -> float:
    ages: list[int] = []
    for item in supports:
        age = _age_days(item, target)
        if age is not None:
            ages.append(max(0, age))
    if not ages:
        return 0.0
    return max(0.0, min(1.0, 1.0 - min(ages) / max(1, window)))


def overall_score(verdicts: list[FreshnessVerdict]) -> float | None:
    scored = [v.score for v in verdicts if v.score is not None]
    if not scored:
        return None
    return round(sum(scored) / len(scored), 1)


__all__ = [
    "POLICY_VERSION",
    "WEIGHTS_VERSION",
    "as_of_datetime",
    "days_between",
    "overall_score",
    "parse_published",
    "score_claim",
]






