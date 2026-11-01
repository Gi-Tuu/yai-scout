from yai_scout.detector.service import StaleAnswerDetector
from yai_scout.detector.verify import build_query
from yai_scout.domain.models import Claim, ClaimType, FreshnessStatus
from yai_scout.retrieval.tavily import SearchResult


def test_build_query_strips_preamble_and_answer_value():
    claim = Claim(
        id="c1",
        text="旧资料显示，Tavily 免费计划每月包含多少 API credits 为 500",
        type=ClaimType.PRICING,
        numbers=["500"],
    )
    query = build_query(claim)
    assert "旧资料显示" not in query
    assert "为 500" not in query
    assert "credits" in query


class FakeSearcher:
    def __init__(self, results: list[SearchResult]) -> None:
        self.results = results
        self.calls = 0

    async def search(
        self, query: str, *, depth: str | None = None, max_results: int | None = None
    ) -> tuple[list[SearchResult], float]:
        self.calls += 1
        return self.results, 1.0


async def test_detector_flags_stale_pricing_claim():
    results = [
        SearchResult(
            title="Tavily Credits & Pricing",
            url="https://docs.tavily.com/documentation/api-credits",
            content="You get 1,000 free API Credits every month. Advanced search costs 2 credits.",
            score=0.9,
            published_date="Tue, 28 Oct 2026 00:00:00 GMT",
        )
    ]
    detector = StaleAnswerDetector(FakeSearcher(results), as_of="2026-11-01", max_claims=3)
    report = await detector.detect("Tavily 免费计划每月提供 500 credits。")
    assert report.claims
    assert report.verdicts
    assert any(v.status is FreshnessStatus.STALE for v in report.verdicts)
    assert report.credits == 1.0


async def test_detector_fresh_when_value_matches():
    results = [
        SearchResult(
            title="Tavily Credits & Pricing",
            url="https://docs.tavily.com/documentation/api-credits",
            content="You get 1,000 free API Credits every month.",
            score=0.9,
            published_date="Tue, 28 Oct 2026 00:00:00 GMT",
        )
    ]
    detector = StaleAnswerDetector(FakeSearcher(results), as_of="2026-11-01", max_claims=3)
    report = await detector.detect("Tavily 免费计划每月提供 1,000 credits。")
    assert report.verdicts[0].status in {FreshnessStatus.FRESH, FreshnessStatus.UNCERTAIN}
    assert report.verdicts[0].score >= 50
