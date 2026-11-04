from __future__ import annotations

from ...domain.models import Claim
from ...retrieval.tavily import SearchResult
from .types import Relation


def classify_date_relation(claim: Claim, result: SearchResult) -> Relation:
    # A year alone cannot establish support; require an explicit relation.
    return "mentions"
