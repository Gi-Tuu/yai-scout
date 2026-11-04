from __future__ import annotations

from ...domain.models import Claim, ClaimType
from ...retrieval.tavily import SearchResult
from .dates import classify_date_relation
from .numeric import classify_numeric_relation
from .types import Relation
from .versions import classify_version_relation


def classify_relation(claim: Claim, result: SearchResult) -> Relation:
    if not claim.numbers and claim.type is not ClaimType.VERSION:
        return "mentions"
    if claim.type is ClaimType.VERSION:
        return classify_version_relation(claim, result)
    if claim.type is ClaimType.DATE:
        return classify_date_relation(claim, result)
    return classify_numeric_relation(claim, result)
