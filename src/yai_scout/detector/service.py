"""Stale-answer Detector 门面：答案 → claim → 核验 → Freshness 报告。"""

from __future__ import annotations

import asyncio
import uuid

from ..domain.models import DetectorReport, FreshnessStatus, FreshnessVerdict
from ..llm import LLMClient
from .claims import extract_claims
from .extract_llm import extract_claims_llm
from .freshness import overall_score
from .suggest import generate_suggestions
from .verify import ClaimVerifier, Searcher


class StaleAnswerDetector:
    def __init__(
        self,
        searcher: Searcher,
        *,
        as_of: str = "2026-11-01",
        max_claims: int = 6,
        concurrency: int = 3,
        llm: LLMClient | None = None,
    ) -> None:
        self.searcher = searcher
        self.as_of = as_of
        self.max_claims = max_claims
        self.concurrency = concurrency
        self.llm = llm

    async def detect(
        self,
        answer: str,
        *,
        as_of: str | None = None,
        max_claims: int | None = None,
    ) -> DetectorReport:
        effective_as_of = as_of or self.as_of
        limit = max_claims or self.max_claims
        llm_cost = 0.0

        claims = None
        if self.llm is not None and self.llm.available:
            extracted = await extract_claims_llm(answer, self.llm, max_claims=limit)
            if extracted is not None:
                claims, llm_cost = extracted
        if not claims:
            claims = extract_claims(answer, max_claims=limit)

        verifier = ClaimVerifier(self.searcher, as_of=effective_as_of, llm=self.llm)
        semaphore = asyncio.Semaphore(self.concurrency)

        async def one(claim_index: int) -> tuple[FreshnessVerdict, float, float]:
            claim = claims[claim_index]
            async with semaphore:
                verdict, credits, relation_cost = await verifier.verify(claim)
            return verdict, credits, relation_cost

        outcomes = await asyncio.gather(*(one(i) for i in range(len(claims))))
        verdicts = [outcome[0] for outcome in outcomes]
        credits = sum(outcome[1] for outcome in outcomes)
        llm_cost += sum(outcome[2] for outcome in outcomes)

        suggestions, suggestion_cost = await generate_suggestions(claims, verdicts, self.llm)
        llm_cost += suggestion_cost
        if suggestions:
            verdicts = [
                v.model_copy(update={"suggestion": suggestions.get(v.claim_id, "")})
                for v in verdicts
            ]

        stale = sum(1 for v in verdicts if v.status is FreshnessStatus.STALE)
        return DetectorReport(
            id=f"det_{uuid.uuid4().hex[:12]}",
            answer=answer,
            as_of=effective_as_of,
            claims=claims,
            verdicts=verdicts,
            overall_score=overall_score(verdicts),
            stale_claims=stale,
            credits=round(credits, 2),
            llm_cost_usd=round(llm_cost, 6),
        )
