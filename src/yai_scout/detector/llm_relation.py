from __future__ import annotations

from ..domain.models import Claim, ClaimType, EvidenceRef
from ..llm import LLMClient
from .relation.types import Relation

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


def should_use_llm(
    claim: Claim, evidence: list[EvidenceRef], llm: LLMClient | None
) -> bool:
    if llm is None or not llm.available or not evidence:
        return False
    special = {ClaimType.LAW, ClaimType.LEADERSHIP, ClaimType.DATE}
    return claim.type in special or not claim.numbers


async def llm_relation(
    claim: Claim, evidence: list[EvidenceRef], llm: LLMClient
) -> tuple[Relation | None, str, float]:
    sources = "\n".join(
        f"- [{i + 1}] {item.title or item.url} ({item.published_at or 'date unknown'}): "
        f"{item.snippet[:280]}"
        for i, item in enumerate(evidence[:3])
    )
    payload = await llm.chat_json(
        RELATION_SYSTEM,
        RELATION_USER.format(claim=claim.text, sources=sources),
        max_tokens=200,
    )
    if payload is None:
        return None, "", 0.0
    data, result = payload
    raw = str(data.get("relation") or "").lower()
    if raw not in {"supports", "contradicts", "mentions"}:
        return None, "", result.cost_usd
    return raw, str(data.get("reason") or "")[:160], result.cost_usd  # type: ignore[return-value]
