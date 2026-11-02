"""Claim 核验器：对每条 claim 做一次 Tavily 检索，构建支持/矛盾证据。"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Literal, Protocol

from ..domain.models import (
    Anchor,
    Claim,
    ClaimType,
    EvidenceRef,
    FreshnessStatus,
    FreshnessVerdict,
)
from ..llm import LLMClient
from ..retrieval.quality import classify_source
from ..retrieval.tavily import SearchResult, TavilyError
from .anchor_policy import needs_revalidation
from .claims import extract_numbers
from .freshness import as_of_datetime, parse_published, score_claim

AnchorFetcher = Callable[[Anchor, str], Awaitable[SearchResult | None]]

VERIFY_QUERY_LIMIT = 380
VERIFY_TIMEOUT_S = 20.0
PREAMBLE_RE = re.compile(r"^(?:旧资料显示|根据[^，,。]*[，,])")
UNIT_TOKENS = (
    "$", "€", "£", "¥", "usd", "eur", "cny",
    "credit", "version", "版本", "许可证", "端口",
    "%", "million", "billion",
)


def build_query(claim: Claim, as_of: str | None = None) -> str:
    """生成检索查询：去掉前缀/答案值，年份随目标时间变化，不硬编码。"""
    text = PREAMBLE_RE.sub("", claim.text).strip()
    if " 为 " in text:
        text = text.split(" 为 ", 1)[0]
    text = text.strip("，,。 .")
    year = (as_of or datetime.now(UTC).isoformat())[:4]
    return (text or claim.text)[:VERIFY_QUERY_LIMIT] + f" latest official {year}"


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
        mode: Literal["live", "replay"] = "live",
        anchor_fetcher: AnchorFetcher | None = None,
    ) -> None:
        self.searcher = searcher
        self.as_of = as_of_datetime(as_of)
        self.max_results = max_results
        self.timeout_s = timeout_s
        self.llm = llm
        self.use_llm_relations = use_llm_relations
        self.mode = mode
        self.anchor_fetcher = anchor_fetcher

    async def verify(
        self, claim: Claim, anchors: list[Anchor] | None = None
    ) -> tuple[FreshnessVerdict, float, float]:
        anchor_results: list[SearchResult] = []
        anchor_pairs: list[tuple[Anchor, SearchResult]] = []
        anchor_ids: list[str] = []
        anchor_status: Literal[
            "used", "changed", "needs_revalidation", "unreachable"
        ] | None = None
        if anchors:
            anchor_status = "unreachable"
            anchor_target = as_of_datetime(
                claim.target_time or self.as_of.isoformat()
            ).isoformat()
            stale = False
            changed = False
            for anchor in anchors:
                if self.anchor_fetcher is None:
                    continue
                result = await self.anchor_fetcher(anchor, anchor_target)
                if result is None:
                    continue
                anchor_results.append(result)
                anchor_pairs.append((anchor, result))
                anchor_ids.append(anchor.id)
                if (
                    anchor.content_hash
                    and result.content_hash
                    and anchor.content_hash != result.content_hash
                ):
                    changed = True
                if needs_revalidation(anchor, claim.temporal_sensitivity):
                    stale = True
            if anchor_results:
                anchor_status = (
                    "changed" if changed else ("needs_revalidation" if stale else "used")
                )
        query = build_query(claim, self.as_of.isoformat())
        try:
            results, credits = await asyncio.wait_for(
                self.searcher.search(query, max_results=self.max_results),
                timeout=self.timeout_s,
            )
        except (TimeoutError, TavilyError) as exc:
            verdict = FreshnessVerdict(
                claim_id=claim.id,
                status=FreshnessStatus.INSUFFICIENT,
                score=None,
                rationale=f"检索失败：{type(exc).__name__}",
            )
            return verdict, 0.0, 0.0

        if self.mode == "replay":
            target = as_of_datetime(claim.target_time or self.as_of.isoformat())
            results = [
                item
                for item in results
                if (parse_published(item.published_date) or target) <= target
            ]

        if anchor_results:
            results = [*anchor_results, *results]
        seen_urls: set[str] = set()
        unique_results: list[SearchResult] = []
        for item in results:
            if item.url in seen_urls:
                continue
            seen_urls.add(item.url)
            unique_results.append(item)
        anchor_meta = {
            anchor.id: (anchor, result) for anchor, result in anchor_pairs
        }
        anchor_by_url = {result.url: anchor for anchor, result in anchor_meta.values()}
        evidence = []
        for item in unique_results[: self.max_results]:
            ev = self._to_evidence(claim, item)
            matched_anchor = anchor_by_url.get(item.url)
            if matched_anchor is not None:
                ev = ev.model_copy(
                    update={
                        "anchor_id": matched_anchor.id,
                        "content_changed": bool(
                            matched_anchor.content_hash
                            and item.content_hash
                            and matched_anchor.content_hash != item.content_hash
                        ),
                    }
                )
            evidence.append(ev)
        llm_cost = 0.0
        llm_reason = ""
        if self._should_use_llm(claim, evidence):
            relation, reason, llm_cost = await self._llm_relation(claim, evidence)
            if relation is not None:
                evidence[0] = evidence[0].model_copy(
                    update={
                        "relation": relation,
                        "relation_reason": reason,
                        "relation_confidence": 0.8,
                    }
                )
                llm_reason = reason
        verdict = score_claim(
            claim,
            evidence,
            as_of=self.as_of,
            allow_future=self.mode == "live",
        )
        if llm_reason:
            verdict.rationale = f"{verdict.rationale}（LLM 判定：{llm_reason}）"
        if anchors:
            verdict.anchor_id = anchor_ids[0] if anchor_ids else anchors[0].id
            verdict.anchor_status = anchor_status
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
        reason = "规则：值匹配" if relation == "supports" else (
            "规则：值不一致" if relation == "contradicts" else "规则：仅提及"
        )
        return EvidenceRef(
            url=result.url,
            title=result.title,
            domain=self._domain(result.url),
            published_at=result.published_date,
            updated_at=None,
            retrieved_at=result.retrieved_at or result.published_date,
            tier=tier,
            snippet=result.content[:400],
            relation=relation,
            relation_reason=reason,
            relation_confidence=0.7 if relation != "mentions" else 0.4,
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
        """Rule relation: structured numbers + units + versions only.

        Any-number overlap is not evidence of support. If units/periods conflict,
        the result is a contradiction; if the value is absent or ambiguous, it is
        only a mention.
        """
        text = f"{result.title} {result.content}".lower()
        claim_text = claim.text.lower()
        if not claim.numbers and claim.type is not ClaimType.VERSION:
            return "mentions"

        claim_versions = _versions(claim_text)
        result_versions = _versions(text)
        if claim.type is ClaimType.VERSION:
            if claim_versions and result_versions:
                if claim_versions & result_versions:
                    return "supports"
                return "contradicts"
            if claim_versions:
                return "mentions"

        if claim.type is ClaimType.DATE:
            # A year alone cannot establish support; require explicit relation.
            return "mentions"

        claim_numbers = [
            number for number in claim.numbers if not YEAR_TOKEN_RE.fullmatch(number)
        ]
        result_numbers = [
            number
            for number in extract_numbers(text)
            if not YEAR_TOKEN_RE.fullmatch(number)
        ]
        if not claim_numbers:
            return "mentions"

        claim_units = _units(claim_text)
        result_units = _units(text)
        if _units_conflict(claim_units, result_units):
            return "contradicts"

        if all(number in result_numbers for number in claim_numbers):
            if claim_units and not (claim_units & result_units):
                return "mentions"
            return "supports"
        if (
            claim.type in {ClaimType.PRICING, ClaimType.VERSION, ClaimType.STATISTIC}
            and result_numbers
        ):
            return "contradicts"
        return "mentions"


VERSION_TOKEN_RE = re.compile(r"v?\d+\.\d+(?:\.\d+)?", re.I)


def _versions(text: str) -> set[str]:
    return {match.lstrip("vV").lower() for match in VERSION_TOKEN_RE.findall(text)}
YEAR_TOKEN_RE = re.compile(r"(?:19|20)\d{2}")
CURRENCY_CODES = {"usd": "usd", "eur": "eur", "gbp": "gbp", "cny": "cny", "jpy": "jpy"}
CURRENCY_SYMBOLS = {"$": "usd", "€": "eur", "£": "gbp", "¥": "cny"}
CURRENCY_WORDS = {"美元": "usd", "欧元": "eur", "英镑": "gbp", "人民币": "cny"}
PERIODS = {"month", "year", "day", "week", "quarter"}


def _units(text: str) -> set[str]:
    units: set[str] = set()
    for symbol, code in CURRENCY_SYMBOLS.items():
        if symbol in text:
            units.add(code)
    for code in CURRENCY_CODES:
        if re.search(rf"\b{code}\b", text):
            units.add(code)
    for word, code in CURRENCY_WORDS.items():
        if word in text:
            units.add(code)
    if re.search(r"\bcredits?\b", text):
        units.add("credits")
    if "%" in text:
        units.add("pct")
    for period in PERIODS:
        if re.search(rf"\b{period}\b", text):
            units.add(f"period:{period}")
    return units


def _units_conflict(claim_units: set[str], result_units: set[str]) -> bool:
    if not claim_units or not result_units:
        return False
    if claim_units.isdisjoint(result_units):
        return True
    claim_periods = {unit for unit in claim_units if unit.startswith("period:")}
    result_periods = {unit for unit in result_units if unit.startswith("period:")}
    if claim_periods and result_periods and claim_periods != result_periods:
        return True
    claim_currencies = {unit for unit in claim_units if unit in CURRENCY_CODES}
    result_currencies = {unit for unit in result_units if unit in CURRENCY_CODES}
    if claim_currencies and result_currencies and claim_currencies != result_currencies:
        return True
    if "credits" in claim_units and result_currencies:
        return True
    return bool(claim_currencies) and "credits" in result_units

