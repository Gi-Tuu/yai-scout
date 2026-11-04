from __future__ import annotations

from ..domain.models import Claim, EvidenceRef
from ..retrieval.quality import classify_source
from ..retrieval.tavily import SearchResult
from .relation.classify import classify_relation


def relation_reason(relation: str) -> str:
    if relation == "supports":
        return "规则：值匹配"
    if relation == "contradicts":
        return "规则：值不一致"
    return "规则：仅提及"


def domain(url: str) -> str:
    from urllib.parse import urlsplit

    host = (urlsplit(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def to_evidence(claim: Claim, result: SearchResult) -> EvidenceRef:
    tier, _ = classify_source(result.url)
    relation = classify_relation(claim, result)
    return EvidenceRef(
        url=result.url,
        title=result.title,
        domain=domain(result.url),
        published_at=result.published_date,
        updated_at=result.updated_date,
        retrieved_at=result.retrieved_at or result.published_date,
        published_at_source=result.published_date_source or "unknown",
        tier=tier,
        snippet=result.content[:400],
        evidence_kind=result.evidence_kind,
        fetch_status=result.fetch_status,
        content_hash=result.content_hash,
        relation=relation,
        relation_reason=relation_reason(relation),
        relation_confidence=0.7 if relation != "mentions" else 0.4,
    )
