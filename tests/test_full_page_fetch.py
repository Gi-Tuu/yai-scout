from __future__ import annotations

import httpx

from yai_scout.detector.verify import ClaimVerifier
from yai_scout.domain.models import Claim, ClaimType, EvidenceKind
from yai_scout.retrieval.tavily import SearchResult
from yai_scout.sources.page import fetch_page


async def test_full_page_fetch_marks_page_kind():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text="<html><body>full official page</body></html>",
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = await fetch_page(
        "https://docs.example.com/pricing",
        {"docs.example.com"},
        client=client,
        resolver=lambda host: "93.184.216.34",
    )
    await client.aclose()
    assert result is not None
    assert result.evidence_kind is EvidenceKind.FETCHED_PAGE
    assert "full official page" in result.content


class FakeSearcher:
    async def search(self, *args: object, **kwargs: object):
        return [
            SearchResult(
                title="snippet",
                url="https://docs.example.com/pricing",
                content="snippet only",
            )
        ], 1.0


async def test_verifier_replaces_snippet_with_fetched_page():
    async def page_fetcher(item: SearchResult) -> SearchResult:
        return SearchResult(
            title=item.title,
            url=item.url,
            content="full page content",
            evidence_kind=EvidenceKind.FETCHED_PAGE,
            fetch_status="ok",
        )

    verifier = ClaimVerifier(
        FakeSearcher(),
        as_of="2026-11-01",
        page_fetcher=page_fetcher,
    )
    claim = Claim(
        id="c1",
        text="Bifrost uses MIT license",
        type=ClaimType.LAW,
        numbers=[],
    )
    verdict, _, _ = await verifier.verify(claim)
    assert verdict.evidence
    assert verdict.evidence[0].evidence_kind is EvidenceKind.FETCHED_PAGE
    assert verdict.evidence[0].snippet == "full page content"
