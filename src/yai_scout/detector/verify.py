"""Claim 核验器：对每条 claim 做一次 Tavily 检索，构建支持/矛盾证据。"""

from __future__ import annotations

import asyncio
import re
from typing import Literal, Protocol

from ..domain.models import Claim, ClaimType, EvidenceRef, FreshnessStatus, FreshnessVerdict
from ..llm import LLMClient
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


RELATION_SYSTEM = (
    "You are a fact-checking judge. Given one claim and up to three web sources, decide whether "
    "the sources support the claim, contradict it, or merely mention it. Return ONLY JSON: "
    '{"relation":"supports|contradicts|mentions","reason":"<short>"}. '
    "If the values/dates/roles differ, use contradicts. "
    "If the sources do not address it, use mentions."
)
RELATION_USER = """Claim: {claim}

Sources:
{sources}
"""


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
    ) -> None:
        self.searcher = searcher
        self.as_of = as_of_datetime(as_of)
        self.max_results = max_results
        self.timeout_s = timeout_s
        self.llm = llm
        self.use_llm_relations = use_llm_relations

    async def verify(self, claim: Claim) -> tuple[FreshnessVerdict, float, float]:
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
            return verdict, 0.0, 0.0

        evidence = [self._to_evidence(claim, item) for item in results[: self.max_results]]
        llm_cost = 0.0
        llm_reason = ""
        if self._should_use_llm(claim, evidence):
            relation, reason, llm_cost = await self._llm_relation(claim, evidence)
            if relation is not None:
                evidence[0].relation = relation
                llm_reason = reason
        verdict = score_claim(claim, evidence, as_of=self.as_of)
        if llm_reason:
            verdict.rationale = f"{verdict.rationale}（LLM 判定：{llm_reason}）"
        return verdict, credits, llm_cost

    def _should_use_llm(self, claim: Claim, evidence: list[EvidenceRef]) -> bool:
        if self.llm is None or not self.llm.available or not self.use_llm_relations:
            return False
        if not evidence:
            return False
        special = {ClaimType.LAW, ClaimType.LEADERSHIP, ClaimType.DATE}
        return claim.type in special or not claim.numbers

    async def _llm_relation(
        self, claim: Claim, evidence: list[EvidenceRef]
    ) -> tuple[Literal["supports", "contradicts", "mentions"] | None, str, float]:
        sources = "\n".join(
            f"- [{i + 1}] {item.title or item.url} ({item.published_at or 'date unknown'}): "
            f"{item.snippet[:280]}"
            for i, item in enumerate(evidence[:3])
        )
        payload = await self.llm.chat_json(  # type: ignore[union-attr]
            RELATION_SYSTEM,
            RELATION_USER.format(claim=claim.text, sources=sources),
            max_tokens=200,
        )
        if payload is None:
            return None, "", 0.0
        data, result = payload
        relation = str(data.get("relation") or "").lower()
        if relation not in {"supports", "contradicts", "mentions"}:
            return None, "", result.cost_usd
        valid: Literal["supports", "contradicts", "mentions"] = relation  # type: ignore[assignment]
        return valid, str(data.get("reason") or "")[:160], result.cost_usd

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


