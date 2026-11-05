from __future__ import annotations

from yai_scout.detector.freshness import as_of_datetime, score_claim
from yai_scout.domain.models import (
    Claim,
    ClaimType,
    EvidenceRef,
    FreshnessStatus,
    TemporalSensitivity,
)


def _claim() -> Claim:
    return Claim(
        id="c",
        text="YAI 当前版本是 0.24.0",
        type=ClaimType.VERSION,
        numbers=["0.24.0"],
        temporal_sensitivity=TemporalSensitivity.SENSITIVE,
    )


def test_cross_source_authority_conflict_is_not_collapsed() -> None:
    evidence = [
        EvidenceRef(
            url="https://official.example/releases",
            domain="official.example",
            published_at="2026-11-01T00:00:00Z",
            tier=1,
            relation="contradicts",
        ),
        EvidenceRef(
            url="https://other.example/releases",
            domain="other.example",
            published_at="2026-11-04T00:00:00Z",
            tier=1,
            relation="supports",
        ),
    ]
    verdict = score_claim(
        _claim(), evidence, as_of=as_of_datetime("2026-11-05"), allow_future=False
    )
    assert verdict.status is FreshnessStatus.CONFLICTED


def test_same_host_different_github_repos_are_not_merged() -> None:
    evidence = [
        EvidenceRef(
            url="https://github.com/acme/widget/releases/tag/v1.0.0",
            domain="github.com",
            published_at="2026-11-01T00:00:00Z",
            tier=2,
            relation="contradicts",
        ),
        EvidenceRef(
            url="https://github.com/other/widget/releases/tag/v1.0.0",
            domain="github.com",
            published_at="2026-11-04T00:00:00Z",
            tier=2,
            relation="supports",
        ),
    ]
    verdict = score_claim(
        _claim(), evidence, as_of=as_of_datetime("2026-11-05"), allow_future=False
    )
    assert verdict.status is FreshnessStatus.CONFLICTED


def test_same_source_same_timestamp_is_order_independent() -> None:
    first = EvidenceRef(
        url="https://github.com/acme/widget/releases/tag/v1.0.0",
        domain="github.com",
        published_at="2026-11-04T00:00:00Z",
        tier=1,
        relation="contradicts",
    )
    second = EvidenceRef(
        url="https://github.com/acme/widget/releases/tag/v1.0.0",
        domain="github.com",
        published_at="2026-11-04T00:00:00Z",
        tier=1,
        relation="supports",
    )
    first_order = score_claim(
        _claim(), [first, second], as_of=as_of_datetime("2026-11-05"), allow_future=False
    )
    second_order = score_claim(
        _claim(), [second, first], as_of=as_of_datetime("2026-11-05"), allow_future=False
    )
    assert first_order.status is FreshnessStatus.CONFLICTED
    assert second_order.status is FreshnessStatus.CONFLICTED


async def test_release_and_issue_in_same_repo_do_not_collapse() -> None:
    from yai_scout.detector.verify import ClaimVerifier
    from yai_scout.retrieval.tavily import SearchResult

    class Searcher:
        async def search(self, query: str, *, depth=None, max_results=None):
            return [
                SearchResult(
                    title="release v2.0.0",
                    url="https://github.com/acme/widget/releases/tag/v2.0.0",
                    content="Widget latest version is 2.0.0",
                    published_date="2026-11-01T00:00:00Z",
                ),
                SearchResult(
                    title="issue 42",
                    url="https://github.com/acme/widget/issues/42",
                    content="Widget latest version is 1.2.3",
                    published_date="2026-11-04T00:00:00Z",
                ),
            ], 0.0

    claim = Claim(
        id="c",
        text="Widget latest version is 1.2.3",
        type=ClaimType.VERSION,
        numbers=["1.2.3"],
    )
    verifier = ClaimVerifier(Searcher(), as_of="2026-11-05")
    verdict, _, _ = await verifier.verify(claim)
    assert verdict.status is FreshnessStatus.CONFLICTED
