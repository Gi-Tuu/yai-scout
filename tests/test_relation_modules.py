from __future__ import annotations

from yai_scout.detector.relation import classify_relation
from yai_scout.domain.models import Claim, ClaimType, TemporalSensitivity
from yai_scout.retrieval.tavily import SearchResult


def _claim(text: str, claim_type: ClaimType, numbers: list[str]) -> Claim:
    return Claim(id="c", text=text, type=claim_type, numbers=numbers)


def test_direct_version_classifier_historical_table() -> None:
    claim = _claim(
        "Python 3.12 于 2023 年发布",
        ClaimType.VERSION,
        ["3.12"],
    ).model_copy(update={"temporal_sensitivity": TemporalSensitivity.STABLE})
    evidence = SearchResult(
        title="Python End-of-Life Dates",
        url="https://endoflife.date/python",
        content="3.12 | 2023\n3.15 | latest",
    )
    assert classify_relation(claim, evidence) == "supports"


def test_direct_version_classifier_current_release() -> None:
    claim = _claim("YAI 当前版本是 0.24.0", ClaimType.VERSION, ["0.24.0"])
    evidence = SearchResult(
        title="v0.25.0",
        url="https://github.com/Gi-Tuu/yai-agent-core/releases/tag/v0.25.0",
        content="release v0.25.0",
    )
    assert classify_relation(claim, evidence) == "contradicts"


def test_direct_numeric_classifier_currency_conflict() -> None:
    claim = _claim("价格是 $20", ClaimType.PRICING, ["20"])
    evidence = SearchResult(
        title="price",
        url="https://example.com/price",
        content="price is €20",
    )
    assert classify_relation(claim, evidence) == "contradicts"


def test_direct_date_classifier_is_mentions() -> None:
    claim = _claim("发布于 2023 年", ClaimType.DATE, ["2023"])
    evidence = SearchResult(
        title="release",
        url="https://example.com/release",
        content="released in 2023",
    )
    assert classify_relation(claim, evidence) == "mentions"
