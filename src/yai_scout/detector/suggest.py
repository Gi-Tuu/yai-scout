"""用 LLM 为 stale/uncertain claim 生成修正建议（逐条，带来源）。"""

from __future__ import annotations

from ..domain.models import Claim, FreshnessStatus, FreshnessVerdict
from ..llm import LLMClient

SYSTEM = (
    "You correct outdated factual claims using the provided evidence. "
    "Write one short, concrete sentence per claim "
    "(what the current value/fact is, with source name). "
    'Return ONLY JSON: {"suggestions":[{"claim_id":"...","suggestion":"..."}]}'
)

USER_TEMPLATE = """Claims and evidence:
{blocks}
"""

MAX_TARGETS = 3


async def generate_suggestions(
    claims: list[Claim],
    verdicts: list[FreshnessVerdict],
    llm: LLMClient | None,
) -> tuple[dict[str, str], float]:
    if llm is None or not llm.available:
        return {}, 0.0
    by_id = {claim.id: claim for claim in claims}
    targets = [
        (by_id[v.claim_id], v)
        for v in verdicts
        if v.claim_id in by_id
        and v.status
        in {
            FreshnessStatus.STALE,
            FreshnessStatus.CONFLICTED,
            FreshnessStatus.INSUFFICIENT,
        }
        and v.evidence
    ][:MAX_TARGETS]
    if not targets:
        return {}, 0.0

    blocks: list[str] = []
    for claim, verdict in targets:
        evidence = "\n".join(
            f"  - {item.title or item.url} ({item.published_at or 'date unknown'}): "
            f"{item.snippet[:220]}"
            for item in verdict.evidence[:2]
        )
        blocks.append(
            f"- claim_id={claim.id}\n  claim: {claim.text}\n  evidence:\n{evidence}"
        )
    payload = await llm.chat_json(
        SYSTEM, USER_TEMPLATE.format(blocks="\n".join(blocks)), max_tokens=500
    )
    if payload is None:
        return {}, 0.0
    data, result = payload
    raw = data.get("suggestions")
    if not isinstance(raw, list):
        return {}, result.cost_usd
    valid_ids = {claim.id for claim, _ in targets}
    suggestions: dict[str, str] = {}
    for item in raw:
        if not isinstance(item, dict):
            continue
        claim_id = str(item.get("claim_id") or "")
        suggestion = " ".join(str(item.get("suggestion") or "").split())
        if claim_id in valid_ids and suggestion:
            suggestions[claim_id] = suggestion[:240]
    return suggestions, result.cost_usd

