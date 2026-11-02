from __future__ import annotations

import httpx
import pytest

from yai_scout.detector.service import StaleAnswerDetector
from yai_scout.retrieval.tavily import TavilyClient, TavilyError


def test_tavily_malformed_json_becomes_tavily_error():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>not json</html>")

    client = TavilyClient("test", transport=httpx.MockTransport(handler))
    with pytest.raises(TavilyError):
        import asyncio

        asyncio.run(client.search("q"))


class ExplodingSearcher:
    async def search(self, *args: object, **kwargs: object):
        raise ValueError("malformed provider payload")


async def test_one_claim_failure_becomes_insufficient_not_500():
    detector = StaleAnswerDetector(ExplodingSearcher(), as_of="2026-11-01")
    report = await detector.detect("Tavily 免费计划每月提供 500 credits。")
    assert report.claims
    assert report.verdicts[0].status.value == "insufficient"
    assert report.verdicts[0].score is None
