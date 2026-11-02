"""Stale-answer Detector 门面：答案 → claim → 时间敏感性 → 核验 → Freshness 报告。"""

from __future__ import annotations

import asyncio
import uuid

from ..domain.models import Anchor, DetectorReport, FreshnessStatus, FreshnessVerdict
from ..llm import LLMClient
from .anchor_policy import select_anchors
from .claims import extract_claims
from .compare import claim_key
from .extract_llm import extract_claims_llm
from .freshness import WEIGHTS_VERSION, coverage_stats, overall_score
from .suggest import generate_suggestions
from .temporal import apply_temporal_classification
from .verify import AnchorFetcher, ClaimVerifier, Searcher
from .versions import POLICY_VERSION


class StaleAnswerDetector:
    def __init__(
        self,
        searcher: Searcher,
        *,
        as_of: str = "2026-11-01",
        max_claims: int = 6,
        concurrency: int = 3,
        llm: LLMClient | None = None,
        mode: str = "live",
        anchor_fetcher: AnchorFetcher | None = None,
    ) -> None:
        self.searcher = searcher
        self.as_of = as_of
        self.max_claims = max_claims
        self.concurrency = concurrency
        self.llm = llm
        self.mode = "replay" if mode == "replay" else "live"
        self.anchor_fetcher = anchor_fetcher

    async def detect(
        self,
        answer: str,
        *,
        as_of: str | None = None,
        max_claims: int | None = None,
        anchors: list[Anchor] | None = None,
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
        claims = [
            apply_temporal_classification(claim, target_time=effective_as_of) for claim in claims
        ]

        verifier = ClaimVerifier(
            self.searcher,
            as_of=effective_as_of,
            llm=self.llm,
            mode="replay" if self.mode == "replay" else "live",
            anchor_fetcher=self.anchor_fetcher,
        )
        anchors_by_key: dict[str, list[Anchor]] = {}
        for anchor in anchors or []:
            if anchor.status != "active":
                continue
            anchors_by_key.setdefault(anchor.claim_key, []).append(anchor)
        semaphore = asyncio.Semaphore(self.concurrency)

        async def one(claim_index: int) -> tuple[FreshnessVerdict, float, float]:
            claim = claims[claim_index]
            async with semaphore:
                candidates = anchors_by_key.get(claim_key(claim.text), [])
                selected = select_anchors(candidates) if candidates else []
                verdict, credits, relation_cost = await verifier.verify(claim, selected)
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

        def count(status: FreshnessStatus) -> int:
            return sum(1 for v in verdicts if v.status is status)

        stats = coverage_stats(verdicts, len(claims))
        return DetectorReport(
            id=f"det_{uuid.uuid4().hex[:12]}",
            answer=answer,
            as_of=effective_as_of,
            claims=claims,
            verdicts=verdicts,
            overall_score=overall_score(verdicts),
            total_claims=int(stats["total_claims"]),
            scored_claims=int(stats["scored_claims"]),
            unknown_claims=int(stats["unknown_claims"]),
            coverage=float(stats["coverage"]),
            abstention_rate=float(stats["abstention_rate"]),
            stale_claims=count(FreshnessStatus.STALE),
            conflicted_claims=count(FreshnessStatus.CONFLICTED),
            insufficient_claims=count(FreshnessStatus.INSUFFICIENT),
            credits=round(credits, 2),
            llm_cost_usd=round(llm_cost, 6),
            mode="replay" if self.mode == "replay" else "live",
            policy_version=POLICY_VERSION,
            weights_version=WEIGHTS_VERSION,
        )





