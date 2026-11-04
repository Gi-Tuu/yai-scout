from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from ..domain.models import (
    Anchor,
    Claim,
    ClaimAssessment,
    EvidenceKind,
    EvidenceRef,
    FreshnessStatus,
    FreshnessVerdict,
)
from ..retrieval.tavily import SearchResult
from ..sources.page import merge_fetched_page
from .anchor_policy import needs_revalidation
from .freshness import as_of_datetime, parse_published, score_claim
from .query import build_query

if TYPE_CHECKING:
    from .verify import ClaimVerifier


@dataclass
class AnchorFetchResult:
    results: list[SearchResult]
    pairs: list[tuple[Anchor, SearchResult]]
    ids: list[str]
    status: Literal["used", "changed", "needs_revalidation", "unreachable"] | None


async def fetch_anchors(
    verifier: ClaimVerifier, claim: Claim, anchors: list[Anchor]
) -> AnchorFetchResult:
    results: list[SearchResult] = []
    pairs: list[tuple[Anchor, SearchResult]] = []
    ids: list[str] = []
    status: Literal[
        "used", "changed", "needs_revalidation", "unreachable"
    ] | None = None
    if not anchors:
        return AnchorFetchResult(results, pairs, ids, status)
    status = "unreachable"
    target = as_of_datetime(claim.target_time or verifier.as_of.isoformat()).isoformat()
    stale = False
    changed = False
    for anchor in anchors:
        if verifier.anchor_fetcher is None:
            continue
        result = await verifier.anchor_fetcher(anchor, target)
        if result is None:
            continue
        results.append(result)
        pairs.append((anchor, result))
        ids.append(anchor.id)
        if (
            anchor.content_hash
            and result.content_hash
            and anchor.content_hash != result.content_hash
        ):
            changed = True
        if needs_revalidation(anchor, claim.temporal_sensitivity):
            stale = True
    if results:
        status = "changed" if changed else ("needs_revalidation" if stale else "used")
    return AnchorFetchResult(results, pairs, ids, status)


async def search(verifier: ClaimVerifier, claim: Claim) -> tuple[list[SearchResult], float]:
    query = build_query(claim, verifier.as_of.isoformat())
    return await asyncio.wait_for(
        verifier.searcher.search(query, max_results=verifier.max_results),
        timeout=verifier.timeout_s,
    )


def failure_verdict(claim: Claim, exc: Exception) -> FreshnessVerdict:
    return FreshnessVerdict(
        claim_id=claim.id,
        status=FreshnessStatus.INSUFFICIENT,
        score=None,
        rationale=f"检索失败：{type(exc).__name__}",
    )


async def prepare_results(
    verifier: ClaimVerifier,
    claim: Claim,
    results: list[SearchResult],
    fetched: AnchorFetchResult,
) -> list[SearchResult]:
    if verifier.mode == "replay":
        target = as_of_datetime(claim.target_time or verifier.as_of.isoformat())
        results = [
            item
            for item in results
            if (parse_published(item.published_date) or target) <= target
        ]
    if fetched.results:
        results = [*fetched.results, *results]
    results = await upgrade_pages(verifier, results)
    return dedupe(results)


async def upgrade_pages(
    verifier: ClaimVerifier, results: list[SearchResult]
) -> list[SearchResult]:
    if verifier.page_fetcher is None:
        return results
    upgraded: list[SearchResult] = []
    for item in results[: verifier.max_results]:
        if item.evidence_kind is EvidenceKind.SEARCH_SNIPPET:
            try:
                fetched = await verifier.page_fetcher(item)
                if fetched is not None:
                    fetched = merge_fetched_page(item, fetched)
            except Exception:  # noqa: BLE001 - page fetch is optional
                fetched = None
            upgraded.append(fetched or item)
        else:
            upgraded.append(item)
    return upgraded


def dedupe(results: list[SearchResult]) -> list[SearchResult]:
    seen: set[str] = set()
    unique: list[SearchResult] = []
    for item in results:
        if item.url in seen:
            continue
        seen.add(item.url)
        unique.append(item)
    return unique


def build_evidence(
    verifier: ClaimVerifier,
    claim: Claim,
    results: list[SearchResult],
    fetched: AnchorFetchResult,
) -> list[EvidenceRef]:
    anchor_by_url = {result.url: anchor for anchor, result in fetched.pairs}
    evidence: list[EvidenceRef] = []
    for item in results[: verifier.max_results]:
        ev = verifier._to_evidence(claim, item)
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
    return evidence


async def score(
    verifier: ClaimVerifier, claim: Claim, evidence: list[EvidenceRef]
) -> tuple[FreshnessVerdict, float]:
    llm_cost = 0.0
    claim_assessment: ClaimAssessment | None = None
    if verifier._should_use_llm(claim, evidence):
        relation, reason, llm_cost = await verifier._llm_relation(claim, evidence)
        if relation is not None:
            claim_assessment = ClaimAssessment(
                relation=relation,
                reason=reason,
                confidence=0.8,
            )
    verdict = score_claim(
        claim, evidence, as_of=verifier.as_of, allow_future=False
    )
    if claim_assessment is not None:
        verdict = verdict.model_copy(
            update={
                "claim_assessment": claim_assessment,
                "rationale": (
                    f"{verdict.rationale}"
                    f"（LLM claim-level 判定：{claim_assessment.reason}）"
                ),
            }
        )
    return verdict, llm_cost


def attach_anchor(
    verdict: FreshnessVerdict,
    anchors: list[Anchor] | None,
    fetched: AnchorFetchResult,
) -> None:
    if anchors:
        verdict.anchor_id = fetched.ids[0] if fetched.ids else anchors[0].id
        verdict.anchor_status = fetched.status
