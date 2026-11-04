from __future__ import annotations

from yai_scout.detector.verify import ClaimVerifier
from yai_scout.domain.models import Claim, ClaimType, TemporalSensitivity
from yai_scout.retrieval.tavily import SearchResult


def _relation(claim_text: str, evidence_text: str) -> str:
    claim = Claim(id="c", text=claim_text, type=ClaimType.VERSION, numbers=["0.24.0"])
    result = SearchResult(
        title="Releases",
        url="https://example.com/releases",
        content=evidence_text,
    )
    return ClaimVerifier._relation(claim, result)


def test_historical_version_does_not_support_current_claim():
    assert (
        _relation(
            "YAI Agent Core 当前版本是 0.24.0",
            "Latest version: 0.25.0; Previous version: 0.24.0",
        )
        == "contradicts"
    )


def test_latest_version_supports_current_claim():
    assert (
        _relation(
            "YAI Agent Core 当前版本是 0.25.0",
            "Latest version: 0.25.0; Previous version: 0.24.0",
        )
        == "supports"
    )


def test_single_unmarked_version_supports():
    assert _relation("当前版本是 0.24.0", "Release 0.24.0") == "supports"


def test_multiple_unmarked_versions_are_ambiguous():
    assert (
        _relation("当前版本是 0.24.0", "0.24.0 and 0.25.0 are available")
        == "mentions"
    )


def test_latest_suffix_marker_supports():
    assert _relation("当前版本是 0.24.0", "version 0.24.0 (latest)") == "supports"


def test_newer_release_url_contradicts_current_claim():
    claim = Claim(
        id="c",
        text="YAI Agent Core 当前版本是 0.24.0",
        type=ClaimType.VERSION,
        numbers=["0.24.0"],
    )
    result = SearchResult(
        title="v0.25.0",
        url="https://github.com/Gi-Tuu/yai-agent-core/releases/tag/v0.25.0",
        content="release v0.25.0",
    )
    assert ClaimVerifier._relation(claim, result) == "contradicts"


def test_other_project_release_url_is_not_a_contradiction():
    claim = Claim(
        id="c",
        text="YAI Agent Core 当前版本是 0.24.0",
        type=ClaimType.VERSION,
        numbers=["0.24.0"],
    )
    result = SearchResult(
        title="v9.0.0",
        url="https://github.com/other/project/releases/tag/v9.0.0",
        content="release v9.0.0",
    )
    assert ClaimVerifier._relation(claim, result) == "mentions"


def test_generic_version_claim_does_not_borrow_other_project_release():
    claim = Claim(
        id="c",
        text="当前版本是 0.24.0",
        type=ClaimType.VERSION,
        numbers=["0.24.0"],
    )
    result = SearchResult(
        title="v9.0.0",
        url="https://github.com/other/project/releases/tag/v9.0.0",
        content="release v9.0.0",
    )
    assert ClaimVerifier._relation(claim, result) == "mentions"


def test_stable_release_date_claim_supported_by_version_table():
    claim = Claim(
        id="c",
        text="Python 3.12 于 2023 年发布",
        type=ClaimType.VERSION,
        numbers=["3.12"],
        temporal_sensitivity=TemporalSensitivity.STABLE,
    )
    result = SearchResult(
        title="Python End-of-Life Dates",
        url="https://endoflife.date/python",
        content="3.12 | 2023\n3.15 | latest",
    )
    assert ClaimVerifier._relation(claim, result) == "supports"


def test_stable_release_date_claim_not_contradicted_by_latest_only():
    claim = Claim(
        id="c",
        text="Python 3.12 于 2023 年发布",
        type=ClaimType.VERSION,
        numbers=["3.12"],
        temporal_sensitivity=TemporalSensitivity.STABLE,
    )
    result = SearchResult(
        title="Python End-of-Life Dates",
        url="https://endoflife.date/python",
        content="Latest version: 3.15",
    )
    assert ClaimVerifier._relation(claim, result) == "mentions"
