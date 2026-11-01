"""LLM 版 claim 抽取（结构化输出 + 严格校验 + 规则兜底）。"""

from __future__ import annotations

import uuid

from ..domain.models import Claim, ClaimType
from ..llm import LLMClient
from .claims import extract_numbers

VALID_TYPES = {
    "pricing": ClaimType.PRICING,
    "version": ClaimType.VERSION,
    "law": ClaimType.LAW,
    "leadership": ClaimType.LEADERSHIP,
    "statistic": ClaimType.STATISTIC,
    "date": ClaimType.DATE,
    "other": ClaimType.OTHER,
}

SYSTEM_PROMPT = (
    "You extract factual claims from an LLM answer that may become outdated over time. "
    "Return ONLY a JSON object. Each claim text MUST be an exact substring of the answer. "
    "Focus on: prices, API versions, laws/regulations, leadership roles, dates, statistics. "
    "Skip opinions, questions, and stable general knowledge."
)

USER_TEMPLATE = (
    "Answer:\n<<<\n{answer}\n>>>\n\n"
    "Extract up to {max_claims} time-sensitive claims as JSON:\n"
    '{{"claims":[{{"text":"<exact substring>",'
    '"type":"pricing|version|law|leadership|date|statistic|other",'
    '"numbers":["<number>"],"time_sensitive":true}}]}}'
)


def _normalize(text: str) -> str:
    return " ".join(text.lower().split()).strip(" .,;:!?。，；：！？")


async def extract_claims_llm(
    answer: str, llm: LLMClient | None, *, max_claims: int = 8
) -> tuple[list[Claim], float] | None:
    """返回 (claims, cost_usd)；LLM 不可用/失败/结果不可信时返回 None，由调用方回退规则版。"""
    if llm is None or not llm.available:
        return None
    payload = await llm.chat_json(
        SYSTEM_PROMPT,
        USER_TEMPLATE.format(answer=answer[:6000], max_claims=max_claims),
        max_tokens=900,
    )
    if payload is None:
        return None
    data, result = payload
    raw_claims = data.get("claims")
    if not isinstance(raw_claims, list):
        return None
    normalized_answer = _normalize(answer)
    claims: list[Claim] = []
    seen: set[str] = set()
    for item in raw_claims:
        if not isinstance(item, dict):
            continue
        text = " ".join(str(item.get("text") or "").split()).strip()
        if not text or len(text) > 400:
            continue
        norm = _normalize(text)
        if not norm or norm not in normalized_answer:
            continue  # 防模型改写/编造：必须是原文子串
        if norm in seen:
            continue
        seen.add(norm)
        claim_type = VALID_TYPES.get(str(item.get("type") or "other").lower(), ClaimType.OTHER)
        if claim_type is ClaimType.OTHER:
            continue
        claims.append(
            Claim(
                id=f"cl_{uuid.uuid4().hex[:8]}",
                text=text,
                type=claim_type,
                numbers=extract_numbers(text),
                signals=["llm"],
            )
        )
        if len(claims) >= max_claims:
            break
    if not claims:
        return None
    return claims, result.cost_usd

