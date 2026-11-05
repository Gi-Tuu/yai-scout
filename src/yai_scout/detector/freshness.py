"""Freshness 判定与评分（v2：先分类、再关系、后评分）。

决策表与分数公式见 docs/spec-freshness-scoring.md。
原则：无证据 = INSUFFICIENT；低权威单源不判 FRESH；稳定事实不因来源旧扣分；
有权威冲突判 CONFLICTED；分数必须可拆解。
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit

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
_STABLE_RELEASE_RE = re.compile(
    r"(?:于|在)\s*(?:19|20)\d{2}\s*年[^。；;]{0,24}(?:发布|推出|上线|成立)"
    r"|(?:released?|release date)\s*(?:in|:)?\s*(?:19|20)\d{2}",
    re.I,
)


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


def evidence_published(item: EvidenceRef) -> datetime | None:
    """Prefer updated_at, but fall back to published_at if it is malformed."""
    updated = parse_published(item.updated_at)
    if updated is not None:
        return updated
    return parse_published(item.published_at)


def days_between(published: datetime | None, as_of: datetime) -> int | None:
    if published is None:
        return None
    return (as_of - published).days


def as_of_datetime(value: str) -> datetime:
    raw = value.strip()
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        dt = datetime(2026, 11, 1, tzinfo=UTC)
    dt = dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt
    if len(raw) == 10:
        # A date-only as_of means "through the end of that day", not midnight.
        return dt.replace(hour=23, minute=59, second=59, microsecond=999999)
    return dt


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
    allow_future: bool = False,
    weights: dict[str, float] | None = None,
) -> FreshnessVerdict:
    """按决策表给出状态 + 可空分数 + 拆解。"""
    fallback = as_of or datetime.now(UTC)
    target = _target_time(claim, fallback)
    sensitivity = _sensitivity(claim)
    window = _window(claim, sensitivity)

    usable: list[tuple[EvidenceRef, str]] = []
    for item in evidence:
        state = _temporal_state(item, target, window)
        if state == "future":
            # Future evidence can never prove the as_of fact. Keep it only for
            # display when explicitly requested; never use it in the verdict.
            if allow_future:
                usable.append((item, state))
            continue
        usable.append((item, state))

    # Expired support may establish a STABLE fact; expired contradictions never
    # make a current STALE verdict. Unknown dates are display-only.
    eligible: list[tuple[EvidenceRef, str]] = []
    stable_release = _is_stable_release_claim(claim)
    for item, state in usable:
        if state == "current" or state == "expired" and sensitivity is TemporalSensitivity.STABLE:
            eligible.append((item, state))
        elif (
            state == "unknown"
            and stable_release
            and item.relation == "supports"
        ):
            # A stable historical release fact may be supported by a version
            # table without a publication timestamp; the version/year match is
            # the evidence, not the fetch date.
            eligible.append((item, state))

    # Version evidence: keep the newest release per comparable source. GitHub
    # repos are keyed by owner/repo, not by host; other pages are keyed by URL,
    # so unrelated pages on a shared domain do not erase a conflict.
    if claim.type is ClaimType.VERSION and eligible:
        newest_by_source: dict[
            str, tuple[datetime | None, list[tuple[EvidenceRef, str]]]
        ] = {}
        for item, state in eligible:
            if item.relation not in {"supports", "contradicts"}:
                continue
            key = _version_source_key(item)
            when = evidence_published(item)
            current = newest_by_source.get(key)
            if current is None:
                newest_by_source[key] = (when, [(item, state)])
            elif when is None:
                if current[0] is None:
                    current[1].append((item, state))
            elif current[0] is None or when > current[0]:
                newest_by_source[key] = (when, [(item, state)])
            elif when == current[0]:
                current[1].append((item, state))
        eligible = [
            entry
            for _when, entries in newest_by_source.values()
            for entry in entries
        ]


    effective = [
        item
        for item, state in eligible
        if item.relation in {"supports", "contradicts"}
        and not (state == "expired" and item.relation == "contradicts")
    ]
    usable_items = [item for item, _ in usable]
    dated_count = sum(
        1
        for item in usable_items
        if evidence_published(item) is not None
    )
    date_coverage = round(dated_count / len(usable_items), 3) if usable_items else 0.0
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
        if sensitivity is TemporalSensitivity.STABLE:
            status = FreshnessStatus.FRESH
            rationale = "稳定事实，权威来源支持即可"
        elif _has_recent_support(auth_supports, target, window):
            status = FreshnessStatus.FRESH
            rationale = "权威来源在有效期内支持该说法"
        else:
            status = FreshnessStatus.INSUFFICIENT
            rationale = (
                "权威来源支持，但发布时间缺失或已超出有效期；"
                "不能仅凭来源权威判定仍新鲜"
            )
    elif supports and sensitivity is TemporalSensitivity.STABLE:
        status = FreshnessStatus.FRESH
        rationale = "稳定事实，一般来源支持即可（不因来源旧扣分）"
    else:
        status = FreshnessStatus.INSUFFICIENT
        rationale = "只有非权威或过期的支持证据，证据强度不足"

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
    confidence = round(confidence * (0.7 + 0.3 * date_coverage), 2)
    if status in {FreshnessStatus.INSUFFICIENT, FreshnessStatus.UNKNOWN}:
        confidence = min(confidence, 0.3)

    return FreshnessVerdict(
        claim_id=claim.id,
        status=status,
        score=score,
        confidence=confidence,
        rationale=rationale,
        date_coverage=date_coverage,
        breakdown={
            "relation": round(relation_norm, 3),
            "recency": round(recency, 3),
            "authority": round(authority, 3),
            "coverage": coverage,
            "date_coverage": date_coverage,
        },
        evidence=usable_items[:5],
    )


def _version_source_key(item: EvidenceRef) -> str:
    """A conservative identity for comparable version-release evidence."""
    parsed = urlsplit(item.url)
    host = (parsed.hostname or "").lower()
    if host in {"github.com", "www.github.com"}:
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) >= 2:
            return (
                f"github:{parts[0].lower()}/"
                f"{parts[1].removesuffix('.git').lower()}"
            )
    return f"url:{item.url}"


def _is_stable_release_claim(claim: Claim) -> bool:
    return (
        claim.type is ClaimType.VERSION
        and claim.temporal_sensitivity is TemporalSensitivity.STABLE
        and bool(_STABLE_RELEASE_RE.search(claim.text))
    )


def _temporal_state(item: EvidenceRef, target: datetime, window: int) -> str:
    published = evidence_published(item)
    if published is None:
        return "unknown"
    age = (target - published).days
    if age < 0:
        return "future"
    if age > window:
        return "expired"
    return "current"


def _age_days(item: EvidenceRef, target: datetime) -> int | None:
    published = evidence_published(item)
    return None if published is None else (target - published).days


def _has_recent_support(
    supports: list[EvidenceRef], target: datetime, window: int
) -> bool:
    """At least one support with a known publication date inside the window."""
    for item in supports:
        age = _age_days(item, target)
        if age is not None and age <= window:
            return True
    return False


def _recency(supports: list[EvidenceRef], target: datetime, window: int) -> float:
    ages: list[int] = []
    for item in supports:
        age = _age_days(item, target)
        if age is not None:
            ages.append(max(0, age))
    if not ages:
        return 0.0
    return max(0.0, min(1.0, 1.0 - min(ages) / max(1, window)))


def date_coverage_stats(
    verdicts: list[FreshnessVerdict],
) -> dict[str, float | int]:
    evidence = [item for verdict in verdicts for item in verdict.evidence]
    dated = sum(
        1
        for item in evidence
        if evidence_published(item) is not None
    )
    undated = len(evidence) - dated
    return {
        "dated_evidence": dated,
        "undated_evidence": undated,
        "publication_date_coverage": round(dated / len(evidence), 3)
        if evidence
        else 0.0,
    }


def coverage_stats(
    verdicts: list[FreshnessVerdict], total_claims: int | None = None
) -> dict[str, float | int]:
    total = total_claims if total_claims is not None else len(verdicts)
    scored = sum(1 for verdict in verdicts if verdict.score is not None)
    insufficient = sum(
        1 for verdict in verdicts if verdict.status is FreshnessStatus.INSUFFICIENT
    )
    unknown = sum(
        1 for verdict in verdicts if verdict.status is FreshnessStatus.UNKNOWN
    )
    return {
        "total_claims": total,
        "scored_claims": scored,
        "insufficient_claims": insufficient,
        "unknown_claims": unknown,
        "coverage": round(scored / total, 3) if total else 0.0,
        "abstention_rate": round((insufficient + unknown) / total, 3)
        if total
        else 0.0,
    }


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
    "coverage_stats",
    "date_coverage_stats",
    "parse_published",
    "score_claim",
]









