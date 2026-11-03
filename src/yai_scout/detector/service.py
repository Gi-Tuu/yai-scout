"""Stale-answer Detector 门面：答案 → claim → 时间敏感性 → 核验 → Freshness 报告。"""

from __future__ import annotations

import asyncio
import uuid

from ..claim_keys import claim_key_v2, claim_keys
from ..domain.models import Anchor, DetectorReport, FreshnessStatus, FreshnessVerdict
from ..llm import LLMClient
from .anchor_policy import select_anchors
from .claims import extract_claims
from .extract_llm import extract_claims_llm
from .freshness import (
    WEIGHTS_VERSION,
    coverage_stats,
    date_coverage_stats,
    overall_score,
)
from .suggest import generate_suggestions
from .temporal import apply_temporal_classification
from .verify import AnchorFetcher, ClaimVerifier, PageFetcher, Searcher
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
        page_fetcher: PageFetcher | None = None,
    ) -> None:
        self.searcher = searcher
        self.as_of = as_of
        self.max_claims = max_claims
        self.concurrency = concurrency
        self.llm = llm
        self.mode = "replay" if mode == "replay" else "live"
        self.anchor_fetcher = anchor_fetcher
        self.page_fetcher = page_fetcher

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
            page_fetcher=self.page_fetcher,
        )
        anchors_by_v1: dict[str, list[Anchor]] = {}
        anchors_by_v2: dict[str, list[Anchor]] = {}
        for anchor in anchors or []:
            if anchor.status != "active":
                continue
            anchors_by_v1.setdefault(anchor.claim_key, []).append(anchor)
            v2 = anchor.claim_key_v2
            if not v2 and anchor.claim_text:
                v2 = claim_key_v2(anchor.claim_text, anchor.claim_type)
            if v2:
                anchors_by_v2.setdefault(v2, []).append(anchor)
        semaphore = asyncio.Semaphore(self.concurrency)

        async def one(claim_index: int) -> tuple[FreshnessVerdict, float, float]:
            claim = claims[claim_index]
            async with semaphore:
                try:
                    v1_key, v2_key = claim_keys(claim.text, claim.type)
                    candidates = list(anchors_by_v2.get(v2_key, []))
                    if not candidates:
                        candidates = [
                            anchor
                            for anchor in anchors_by_v1.get(v1_key, [])
                            if anchor.claim_key_version == 1
                        ]
                    seen: set[str] = set()
                    unique_candidates: list[Anchor] = []
                    for anchor in candidates:
                        if anchor.id in seen:
                            continue
                        seen.add(anchor.id)
                        unique_candidates.append(anchor)
                    selected = (
                        select_anchors(unique_candidates) if unique_candidates else []
                    )
                    verdict, credits, relation_cost = await verifier.verify(
                        claim, selected
                    )
                except Exception as exc:  # noqa: BLE001 - one claim must not kill the report
                    verdict = FreshnessVerdict(
                        claim_id=claim.id,
                        status=FreshnessStatus.INSUFFICIENT,
                        score=None,
                        rationale=f"单条核验失败：{type(exc).__name__}",
                    )
                    return verdict, 0.0, 0.0
            return verdict, credits, relation_cost

        outcomes = await asyncio.gather(*(one(i) for i in range(len(claims))))
        verdicts = [outcome[0] for outcome in outcomes]
        credits = sum(outcome[1] for outcome in outcomes)
        llm_cost += sum(outcome[2] for outcome in outcomes)

        try:
            suggestions, suggestion_cost = await generate_suggestions(
                claims, verdicts, self.llm
            )
        except Exception:  # noqa: BLE001 - suggestions are optional
            suggestions, suggestion_cost = {}, 0.0
        llm_cost += suggestion_cost
        if suggestions:
            verdicts = [
                v.model_copy(update={"suggestion": suggestions.get(v.claim_id, "")})
                for v in verdicts
            ]

        def count(status: FreshnessStatus) -> int:
            return sum(1 for v in verdicts if v.status is status)

        stats = coverage_stats(verdicts, len(claims))
        date_stats = date_coverage_stats(verdicts)
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
            dated_evidence=int(date_stats["dated_evidence"]),
            undated_evidence=int(date_stats["undated_evidence"]),
            publication_date_coverage=float(date_stats["publication_date_coverage"]),
            stale_claims=count(FreshnessStatus.STALE),
            conflicted_claims=count(FreshnessStatus.CONFLICTED),
            insufficient_claims=count(FreshnessStatus.INSUFFICIENT),
            credits=round(credits, 2),
            llm_cost_usd=round(llm_cost, 6),
            mode="replay" if self.mode == "replay" else "live",
            policy_version=POLICY_VERSION,
            weights_version=WEIGHTS_VERSION,
        )





