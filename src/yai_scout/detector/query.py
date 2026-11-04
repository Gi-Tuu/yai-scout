from __future__ import annotations

import re
from datetime import UTC, datetime

from ..domain.models import Claim

VERIFY_QUERY_LIMIT = 380
PREAMBLE_RE = re.compile(r"^(?:旧资料显示|根据[^，,。]*[，,])")


def build_query(claim: Claim, as_of: str | None = None) -> str:
    """Generate a retrieval query without hard-coding the target year."""
    text = PREAMBLE_RE.sub("", claim.text).strip()
    if " 为 " in text:
        text = text.split(" 为 ", 1)[0]
    text = text.strip("，,。 .")
    year = (as_of or datetime.now(UTC).isoformat())[:4]
    return (text or claim.text)[:VERIFY_QUERY_LIMIT] + f" latest official {year}"
