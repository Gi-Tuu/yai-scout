from __future__ import annotations

from yai_scout.detector.receipt import build_report_receipt
from yai_scout.detector.verify import ClaimVerifier
from yai_scout.domain.models import (
    Claim,
    ClaimType,
    DetectorReport,
    EvidenceKind,
    FreshnessStatus,
    FreshnessVerdict,
)
from yai_scout.retrieval.tavily import SearchResult
from yai_scout.sources.page import merge_fetched_page


def _original() -> SearchResult:
    return SearchResult(
        title="official docs",
        url="https://docs.example.com/pricing",
        content="snippet",
        score=0.9,
        published_date="2026-01-01T00:00:00Z",
        updated_date="2026-02-01T00:00:00Z",
        published_date_source="tavily_search",
        retrieved_at="2026-03-01T00:00:00Z",
        content_hash="old-hash",
    )


def _fetched() -> SearchResult:
    return SearchResult(
        title="anchor live docs.example.com",
        url="https://docs.example.com/pricing",
        content="full page",
        published_date=None,
        published_date_source="unknown",
        retrieved_at="2026-03-02T00:00:00Z",
        content_hash="new-hash",
        evidence_kind=EvidenceKind.FETCHED_PAGE,
        fetch_status="ok",
    )


def test_merge_preserves_original_publication_metadata():
    merged = merge_fetched_page(_original(), _fetched())
    assert merged.published_date == "2026-01-01T00:00:00Z"
    assert merged.published_date_source == "tavily_search"
    assert merged.updated_date == "2026-02-01T00:00:00Z"
    assert merged.retrieved_at == "2026-03-02T00:00:00Z"
    assert merged.content_hash == "new-hash"
    assert merged.evidence_kind is EvidenceKind.FETCHED_PAGE


def test_merge_keeps_publication_unknown_when_original_is_unknown():
    original = _original()
    original.published_date = None
    original.published_date_source = "unknown"
    merged = merge_fetched_page(original, _fetched())
    assert merged.published_date is None
    assert merged.published_date_source == "unknown"


class FakeSearcher:
    async def search(self, *args: object, **kwargs: object):
        return [_original()], 1.0


async def test_verifier_keeps_date_after_page_fetch():
    async def page_fetcher(_item: SearchResult) -> SearchResult:
        return _fetched()

    verifier = ClaimVerifier(
        FakeSearcher(), as_of="2026-11-01", page_fetcher=page_fetcher
    )
    claim = Claim(id="c1", text="Bifrost uses MIT license", type=ClaimType.LAW)
    verdict, _, _ = await verifier.verify(claim)
    evidence = verdict.evidence[0]
    assert evidence.published_at == "2026-01-01T00:00:00Z"
    assert evidence.published_at_source == "tavily_search"
    assert evidence.retrieved_at == "2026-03-02T00:00:00Z"
    assert evidence.content_hash == "new-hash"
    assert evidence.evidence_kind is EvidenceKind.FETCHED_PAGE


async def test_page_fetch_failure_keeps_original_evidence():
    async def page_fetcher(_item: SearchResult) -> SearchResult:
        raise RuntimeError("fetch failed")

    verifier = ClaimVerifier(
        FakeSearcher(), as_of="2026-11-01", page_fetcher=page_fetcher
    )
    claim = Claim(id="c1", text="Bifrost uses MIT license", type=ClaimType.LAW)
    verdict, _, _ = await verifier.verify(claim)
    evidence = verdict.evidence[0]
    assert evidence.snippet == "snippet"
    assert evidence.published_at == "2026-01-01T00:00:00Z"
    assert evidence.published_at_source == "tavily_search"


def test_receipt_serializes_time_provenance():
    from yai_scout.domain.models import EvidenceRef

    claim = Claim(id="c1", text="Bifrost uses MIT license", type=ClaimType.LAW)
    evidence = EvidenceRef(
        url="https://docs.example.com/pricing",
        published_at="2026-01-01T00:00:00Z",
        updated_at="2026-02-01T00:00:00Z",
        retrieved_at="2026-03-02T00:00:00Z",
        published_at_source="tavily_search",
        evidence_kind=EvidenceKind.FETCHED_PAGE,
        content_hash="new-hash",
    )
    verdict = FreshnessVerdict(
        claim_id="c1",
        status=FreshnessStatus.INSUFFICIENT,
        evidence=[evidence],
    )
    report = DetectorReport(
        id="r1",
        answer="a",
        as_of="2026-11-01",
        claims=[claim],
        verdicts=[verdict],
    )
    receipt = build_report_receipt(report)
    stored = receipt.claims[0].evidence[0]
    assert stored.published_at == "2026-01-01T00:00:00Z"
    assert stored.updated_at == "2026-02-01T00:00:00Z"
    assert stored.retrieved_at == "2026-03-02T00:00:00Z"
    assert stored.published_at_source == "tavily_search"
