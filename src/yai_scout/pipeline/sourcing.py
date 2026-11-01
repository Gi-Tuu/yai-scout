"""把检索结果转成可落库的来源记录（归一化 URL、分级、内容哈希）。"""

from __future__ import annotations

import hashlib
import uuid

from ..domain.models import SourceRecord
from ..retrieval.dedupe import canonicalize_url
from ..retrieval.quality import classify_source, domain_of
from ..retrieval.tavily import SearchResult

SNIPPET_LIMIT = 600


def to_source_record(task_id: str, result: SearchResult) -> SourceRecord:
    canonical = canonicalize_url(result.url)
    tier, reason = classify_source(result.url)
    digest = hashlib.sha256(result.content.encode("utf-8")).hexdigest()[:32]
    return SourceRecord(
        id=f"src_{uuid.uuid4().hex[:12]}",
        task_id=task_id,
        url=result.url,
        canonical_url=canonical,
        domain=domain_of(result.url),
        title=result.title[:300],
        published_at=result.published_date,
        content_hash=digest,
        tier=tier,
        tier_reason=reason,
        score=result.score,
        snippet=result.content[:SNIPPET_LIMIT],
    )
