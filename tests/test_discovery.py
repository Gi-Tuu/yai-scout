from __future__ import annotations

from yai_scout.detector.candidates import extract_value_hint
from yai_scout.detector.discovery import CachedDiscovery
from yai_scout.retrieval.tavily import SearchResult


class FakeSearcher:
    def __init__(self) -> None:
        self.calls = 0

    async def search(self, query: str, *, depth=None, max_results=None):
        self.calls += 1
        return [
            SearchResult(title=query, url=f"https://example.com/{self.calls}", content="x")
        ], 1.0


def test_extract_value_hint_is_type_aware():
    assert (
        extract_value_hint(
            "Tavily 免费计划每月提供 1,000 credits",
            "500",
            "Tavily 免费计划每月提供 500 credits",
        )
        == "1,000"
    )
    assert (
        extract_value_hint(
            "release version v0.25.0",
            "0.24.0",
            "YAI Agent Core 当前版本是",
        )
        == "v0.25.0"
    )
    assert (
        extract_value_hint(
            "Licensed under Apache-2.0", "AGPL-3.0", "Bifrost 使用什么许可证"
        )
        == "Apache-2.0"
    )
    assert extract_value_hint("listens on port 8080", "8000", "默认端口") == "8080"


def test_extract_value_hint_rejects_ambiguous_prices():
    assert (
        extract_value_hint(
            "price is $0.30 or maybe $0.50", "0.20", "价格是多少"
        )
        == ""
    )


async def test_discovery_cache_hits_do_not_call_searcher_twice():
    searcher = FakeSearcher()
    discovery = CachedDiscovery(searcher, ttl_seconds=3600, daily_budget=10)
    first, _ = await discovery.search("q", max_results=3)
    second, _ = await discovery.search("q", max_results=3)
    assert first == second
    assert searcher.calls == 1
    assert discovery.usage()["cache_hits"] == 1


async def test_discovery_daily_budget_blocks_calls():
    searcher = FakeSearcher()
    discovery = CachedDiscovery(searcher, ttl_seconds=3600, daily_budget=1)
    await discovery.search("q1", max_results=3)
    results, _ = await discovery.search("q2", max_results=3)
    assert results == []
    assert searcher.calls == 1
    assert discovery.usage()["budget_denied"] == 1

async def test_discovery_cache_is_bounded():
    searcher = FakeSearcher()
    discovery = CachedDiscovery(
        searcher, ttl_seconds=3600, daily_budget=10, max_cache_entries=2
    )
    await discovery.search("q1", max_results=3)
    await discovery.search("q2", max_results=3)
    await discovery.search("q3", max_results=3)
    assert discovery.usage()["cache_size"] == 2
    await discovery.search("q1", max_results=3)
    assert searcher.calls == 4
