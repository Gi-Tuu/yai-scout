from __future__ import annotations

import pytest

from yai_scout.detector.verify import ClaimVerifier
from yai_scout.domain.models import Claim, ClaimType
from yai_scout.retrieval.tavily import SearchResult


def _claim(text: str, claim_type: ClaimType, numbers: list[str]) -> Claim:
    return Claim(id="c", text=text, type=claim_type, numbers=numbers)


def _relation(
    claim_text: str,
    claim_type: ClaimType,
    numbers: list[str],
    evidence_text: str,
) -> str:
    claim = _claim(claim_text, claim_type, numbers)
    result = SearchResult(
        title=evidence_text,
        url="https://example.com/source",
        content=evidence_text,
    )
    return ClaimVerifier._relation(claim, result)


@pytest.mark.parametrize(
    ("claim", "ctype", "numbers", "evidence", "expected"),
    [
        (
            "Tavily 免费计划每月提供 500 credits",
            ClaimType.PRICING,
            ["500"],
            "Tavily 免费计划每月提供 1000 credits",
            "contradicts",
        ),
        (
            "Tavily 免费计划每月 500 美元",
            ClaimType.PRICING,
            ["500"],
            "Tavily 免费计划每月 500 欧元",
            "contradicts",
        ),
        (
            "Tavily 免费计划每月 500 credits / month",
            ClaimType.PRICING,
            ["500"],
            "Tavily 免费计划每月 500 credits / year",
            "contradicts",
        ),
        (
            "YAI Agent Core 当前版本是 1.2",
            ClaimType.VERSION,
            ["1.2"],
            "YAI Agent Core 当前版本是 1.3",
            "contradicts",
        ),
        (
            "YAI Agent Core 当前版本是 1.2",
            ClaimType.VERSION,
            ["1.2"],
            "YAI Agent Core 当前版本是 1.2",
            "supports",
        ),
        (
            "公司 CEO 是 Alice",
            ClaimType.LEADERSHIP,
            [],
            "公司 CEO 是 Bob",
            "mentions",
        ),
        (
            "Python 3.12 于 2026 年发布",
            ClaimType.DATE,
            ["2026"],
            "Python 3.12 于 2026 年发布",
            "mentions",
        ),
        (
            "Tavily 免费计划每月提供 500 credits",
            ClaimType.PRICING,
            ["500"],
            "Tavily 免费计划每月提供 500 credits",
            "supports",
        ),
        (
            "Tavily 免费计划每月提供 500 credits",
            ClaimType.PRICING,
            ["500"],
            "Tavily 免费计划每月提供 $500",
            "contradicts",
        ),
    ],
)
def test_relation_requires_value_and_unit_agreement(
    claim: str,
    ctype: ClaimType,
    numbers: list[str],
    evidence: str,
    expected: str,
):
    assert _relation(claim, ctype, numbers, evidence) == expected

