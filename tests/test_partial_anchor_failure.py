from __future__ import annotations

from yai_scout.detector.verify import ClaimVerifier
from yai_scout.domain.models import Anchor, Claim, ClaimType
from yai_scout.retrieval.tavily import SearchResult


class FailingSearcher:
    async def search(self, query: str, *, depth=None, max_results=None):
        raise RuntimeError("search down")


async def test_failed_search_keeps_anchor_evidence() -> None:
    anchor = Anchor(
        id="a1",
        claim_key="k",
        claim_key_v2="v",
        claim_key_version=2,
        claim_text="price is 1000",
        url="https://example.com/price",
        last_value="1000",
        content_hash="h1",
        published_at="2026-10-01T00:00:00Z",
    )

    async def fetch(_anchor, _target):
        return SearchResult(
            title="price",
            url="https://example.com/price",
            content="price is 1000",
            published_date="2026-10-01T00:00:00Z",
            content_hash="h1",
        )

    verifier = ClaimVerifier(
        FailingSearcher(),  # type: ignore[arg-type]
        as_of="2026-11-01",
        anchor_fetcher=fetch,
    )
    claim = Claim(
        id="c",
        text="price is 1000",
        type=ClaimType.PRICING,
        numbers=["1000"],
    )
    verdict, credits, cost = await verifier.verify(claim, [anchor])
    assert credits == 0
    assert cost == 0
    assert verdict.evidence
    assert "anchor" in verdict.rationale
    assert verdict.anchor_status in {"used", "needs_revalidation"}
