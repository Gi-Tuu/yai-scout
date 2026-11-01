"""Stale-answer Detector 门面：答案 → claim → 核验 → Freshness 报告。"""

from __future__ import annotations

import asyncio
import uuid

from ..domain.models import DetectorReport, FreshnessStatus, FreshnessVerdict
from .claims import extract_claims
from .freshness import overall_score
from .verify import ClaimVerifier, Searcher


class StaleAnswerDetector:
    def __init__(
        self,
        searcher: Searcher,
        *,
        as_of: str = "2026-11-01",
        max_claims: int = 6,
        concurrency: int = 3,
    ) -> None:
        self.searcher = searcher
        self.as_of = as_of
        self.max_claims = max_claims
        self.concurrency = concurrency

    async def detect(
        self,
        answer: str,
        *,
        as_of: str | None = None,
        max_claims: int | None = None,
    ) -> DetectorReport:
        effective_as_of = as_of or self.as_of
        claims = extract_claims(answer, max_claims=max_claims or self.max_claims)
        verifier = ClaimVerifier(self.searcher, as_of=effective_as_of)
        semaphore = asyncio.Semaphore(self.concurrency)

        async def one(claim_index: int) -> tuple[int, FreshnessVerdict, float]:
            claim = claims[claim_index]
            async with semaphore:
                verdict, credits = await verifier.verify(claim)
            return claim_index, verdict, credits

        outcomes = await asyncio.gather(*(one(i) for i in range(len(claims))))
        verdicts = [outcome[1] for outcome in outcomes]
        credits = sum(outcome[2] for outcome in outcomes)
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
        )
