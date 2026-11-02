from __future__ import annotations

from yai_scout.detector.verify import ClaimVerifier
from yai_scout.domain.models import Claim, ClaimType, EvidenceKind
from yai_scout.retrieval.tavily import SearchResult


class FakeSearcher:
    async def search(self, query: str, *, depth=None, max_results=None):
        return [], 0.0


def test_evidence_kind_is_preserved():
    verifier = ClaimVerifier(FakeSearcher())
    claim = Claim(id="c", text="Tavily 500 credits", type=ClaimType.PRICING, numbers=["500"])
    result = SearchResult(
        title="T",
        url="https://docs.tavily.com/x",
        content="500 credits",
        evidence_kind=EvidenceKind.FETCHED_PAGE,
        fetch_status="ok",
        content_hash="h1",
        retrieved_at="2026-11-02T00:00:00Z",
    )
    evidence = verifier._to_evidence(claim, result)
    assert evidence.evidence_kind is EvidenceKind.FETCHED_PAGE
    assert evidence.fetch_status == "ok"
    assert evidence.content_hash == "h1"
    assert evidence.retrieved_at == "2026-11-02T00:00:00Z"


def test_search_results_default_to_snippet():
    result = SearchResult(title="T", url="https://example.com", content="500 credits")
    assert result.evidence_kind is EvidenceKind.SEARCH_SNIPPET
    assert result.fetch_status == "snippet"
