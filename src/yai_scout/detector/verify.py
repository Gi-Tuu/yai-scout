"""Claim 核验器：对每条 claim 做一次 Tavily 检索，构建支持/矛盾证据。"""

from __future__ import annotations

import asyncio
import re
from typing import Literal, Protocol

from ..domain.models import Claim, ClaimType, EvidenceRef, FreshnessStatus, FreshnessVerdict
from ..retrieval.quality import classify_source
from ..retrieval.tavily import SearchResult, TavilyError
from .claims import extract_numbers
from .freshness import as_of_datetime, score_claim

VERIFY_QUERY_LIMIT = 380
VERIFY_TIMEOUT_S = 20.0
PREAMBLE_RE = re.compile(r"^(?:旧资料显示|根据[^，,。]*[，,])")
UNIT_TOKENS = (
    "$", "€", "£", "¥", "usd", "eur", "cny",
    "credit", "version", "%", "million", "billion",
)


def build_query(claim: Claim) -> str:
    """把 claim 变成检索查询：去掉"旧资料显示"这类前缀与答案值，保留主题词。"""
    text = PREAMBLE_RE.sub("", claim.text).strip()
    if " 为 " in text:
        text = text.split(" 为 ", 1)[0]
    text = text.strip("，,。 .")
    return (text or claim.text)[:VERIFY_QUERY_LIMIT] + " latest 2026"


class Searcher(Protocol):
    async def search(
        self, query: str, *, depth: str | None = None, max_results: int | None = None
    ) -> tuple[list[SearchResult], float]: ...


class ClaimVerifier:
    def __init__(
        self,
        searcher: Searcher,
        *,
        as_of: str = "2026-11-01",
        max_results: int = 4,
        timeout_s: float = VERIFY_TIMEOUT_S,
    ) -> None:
        self.searcher = searcher
        self.as_of = as_of_datetime(as_of)
        self.max_results = max_results
        self.timeout_s = timeout_s

    async def verify(self, claim: Claim) -> tuple[FreshnessVerdict, float]:
        query = build_query(claim)
        try:
            results, credits = await asyncio.wait_for(
                self.searcher.search(query, max_results=self.max_results),
                timeout=self.timeout_s,
            )
        except (TimeoutError, TavilyError) as exc:
            verdict = FreshnessVerdict(
                claim_id=claim.id,
                status=FreshnessStatus.UNVERIFIABLE,
                score=0,
                rationale=f"检索失败：{type(exc).__name__}",
            )
            return verdict, 0.0

        evidence = [self._to_evidence(claim, item) for item in results[: self.max_results]]
        verdict = score_claim(claim, evidence, as_of=self.as_of)
        return verdict, credits

    def _to_evidence(self, claim: Claim, result: SearchResult) -> EvidenceRef:
        tier, _ = classify_source(result.url)
        relation = self._relation(claim, result)
        return EvidenceRef(
            url=result.url,
            title=result.title,
            domain=self._domain(result.url),
            published_at=result.published_date,
            tier=tier,
            snippet=result.content[:400],
            relation=relation,
        )

    @staticmethod
    def _domain(url: str) -> str:
        from urllib.parse import urlsplit

        host = (urlsplit(url).hostname or "").lower()
        return host[4:] if host.startswith("www.") else host

    @staticmethod
    def _relation(
        claim: Claim, result: SearchResult
    ) -> Literal["supports", "contradicts", "mentions"]:
        """支持 / 矛盾 / 仅提及。规则版：只对数字型 claim 做值比较。"""
        text = f"{result.title} {result.content}".lower()
        if not claim.numbers:
            return "mentions"
        result_numbers = extract_numbers(text)
        if any(num in result_numbers for num in claim.numbers):
            return "supports"
        if claim.type in {ClaimType.PRICING, ClaimType.VERSION, ClaimType.STATISTIC}:
            shares_unit = any(token in text for token in UNIT_TOKENS) and any(
                token in claim.text.lower() for token in UNIT_TOKENS
            )
            if result_numbers and shares_unit:
                return "contradicts"
        return "mentions"


