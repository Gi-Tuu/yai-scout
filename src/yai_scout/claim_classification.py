"""Shared claim-type classification (no detector/store dependencies).

This module is the single source of truth for turning claim text into a
ClaimType. Both the detector and persistence/migration code use it so that
identity keys cannot diverge.
"""

from __future__ import annotations

import re

from .domain.models import ClaimType

# 顺序即优先级：价格 > 版本 > 法规 > 人事 > 统计 > 日期
SIGNALS: list[tuple[ClaimType, re.Pattern[str], str]] = [
    (
        ClaimType.PRICING,
        re.compile(
            r"[$€£¥]\s?\d|\b(?:USD|EUR|CNY|RMB|dollars?|euros?)\b"
            r"|\b(?:pricing|price|cost|per month|/mo|subscription|billing|credits?)\b"
            r"|免费|价格|费用|收费|每月|每年|订阅|美元|人民币",
            re.I,
        ),
        "price",
    ),
    (
        ClaimType.VERSION,
        re.compile(r"\bv?\d+\.\d+(?:\.\d+)?\b|\bversion\b|\brelease\b|版本|发布|端口|port", re.I),
        "version",
    ),
    (
        ClaimType.LAW,
        re.compile(
            r"\b(?:law|act|regulation|directive|bill|policy|effective|compliance)\b"
            r"|\b(?:GDPR|AI Act|EU AI Act)\b|法律|法规|法案|生效|监管|合规|许可证|license",
            re.I,
        ),
        "law",
    ),
    (
        ClaimType.LEADERSHIP,
        re.compile(
            r"\b(?:CEO|CTO|CFO|COO|founder|president|chairman|head of"
            r"|appointed|resigned|steps down)\b|创始人|总裁|辞任|任命",
            re.I,
        ),
        "leadership",
    ),
    (
        ClaimType.STATISTIC,
        re.compile(
            r"\b\d+(?:\.\d+)?\s?(?:%|percent|million|billion|thousand"
            r"|users|customers|registrations|downloads)\b|用户|增长|占比",
            re.I,
        ),
        "statistic",
    ),
    (
        ClaimType.DATE,
        re.compile(
            r"\b(?:19|20)\d{2}\b|\b\d{4}年"
            r"|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\b"
            r"|\b\d{1,2}/\d{1,2}/\d{2,4}\b",
            re.I,
        ),
        "date",
    ),
]


def classify(text: str) -> tuple[ClaimType, list[str]]:
    for claim_type, pattern, label in SIGNALS:
        if pattern.search(text):
            return claim_type, [label]
    return ClaimType.OTHER, []


def resolve_claim_type(
    text: str, declared: ClaimType | str | None = None
) -> ClaimType:
    """Canonical claim-type resolution for identity generation.

    An explicit non-OTHER type wins; otherwise use the shared classifier.
    Never duplicate classification rules in callers.
    """
    if isinstance(declared, ClaimType) and declared is not ClaimType.OTHER:
        return declared
    if isinstance(declared, str) and declared:
        try:
            parsed = ClaimType(declared)
        except ValueError:
            parsed = ClaimType.OTHER
        if parsed is not ClaimType.OTHER:
            return parsed
    if not text.strip():
        return ClaimType.OTHER
    return classify(text)[0]
