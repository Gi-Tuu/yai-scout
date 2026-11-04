"""Claim 核验器：对每条 claim 做一次 Tavily 检索，构建支持/矛盾证据。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Literal, Protocol

from ..domain.models import (
    Anchor,
    Claim,
    EvidenceRef,
    FreshnessVerdict,
)
from ..llm import LLMClient
from ..retrieval.tavily import SearchResult
from .freshness import as_of_datetime
from .query import build_query
from .relation.classify import classify_relation
from .verify_steps import (
    attach_anchor,
    build_evidence,
    failure_verdict,
    fetch_anchors,
    prepare_results,
    score,
    search,
)

AnchorFetcher = Callable[[Anchor, str], Awaitable[SearchResult | None]]
PageFetcher = Callable[[SearchResult], Awaitable[SearchResult | None]]

VERIFY_TIMEOUT_S = 20.0

__all__ = ["ClaimVerifier", "Searcher", "build_query"]


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
        llm: LLMClient | None = None,
        use_llm_relations: bool = True,
        mode: Literal["live", "replay"] = "live",
        anchor_fetcher: AnchorFetcher | None = None,
        page_fetcher: PageFetcher | None = None,
    ) -> None:
        self.searcher = searcher
        self.as_of = as_of_datetime(as_of)
        self.max_results = max_results
        self.timeout_s = timeout_s
        self.llm = llm
        self.use_llm_relations = use_llm_relations
        self.mode = mode
        self.anchor_fetcher = anchor_fetcher
        self.page_fetcher = page_fetcher

    async def verify(
        self, claim: Claim, anchors: list[Anchor] | None = None
    ) -> tuple[FreshnessVerdict, float, float]:
        fetched = await fetch_anchors(self, claim, anchors or [])
        try:
            results, credits = await search(self, claim)
        except Exception as exc:  # noqa: BLE001 - evidence failure must abstain
            return failure_verdict(claim, exc), 0.0, 0.0
        selected = await prepare_results(self, claim, results, fetched)
        evidence = build_evidence(self, claim, selected, fetched)
        verdict, llm_cost = await score(self, claim, evidence)
        attach_anchor(verdict, anchors, fetched)
        return verdict, credits, llm_cost

    def _should_use_llm(self, claim: Claim, evidence: list[EvidenceRef]) -> bool:
        if not self.use_llm_relations or not evidence:
            return False
        from .llm_relation import should_use_llm

        return should_use_llm(claim, evidence, self.llm)

    async def _llm_relation(
        self, claim: Claim, evidence: list[EvidenceRef]
    ) -> tuple[Literal["supports", "contradicts", "mentions"] | None, str, float]:
        from .llm_relation import llm_relation

        if self.llm is None:
            return None, "", 0.0
        return await llm_relation(claim, evidence, self.llm)

    def _to_evidence(self, claim: Claim, result: SearchResult) -> EvidenceRef:
        from .evidence import to_evidence

        return to_evidence(claim, result)

    @staticmethod
    def _domain(url: str) -> str:
        from .evidence import domain

        return domain(url)

    @staticmethod
    def _relation(
        claim: Claim, result: SearchResult
    ) -> Literal["supports", "contradicts", "mentions"]:
        """Compatibility proxy for the pure relation classifier."""
        return classify_relation(claim, result)

