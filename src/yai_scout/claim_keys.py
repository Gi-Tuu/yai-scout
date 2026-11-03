"""Versioned claim identity keys.

v1 is the historical all-numbers-to-`#` key.
v2 preserves dates/quarters/version context and normalizes values.
"""

from __future__ import annotations

import re

CLAIM_KEY_VERSION = 2
NUMBER_RE = re.compile(r"\d[\d,\.]*")
V2_TOKEN_RE = re.compile(
    r"(?P<date>\b\d{4}-\d{2}-\d{2}\b)"
    r"|(?P<cn_date>\d{4}\s*年(?:\s*\d{1,2}\s*月)?(?:\s*\d{1,2}\s*日)?)"
    r"|(?P<quarter>Q[1-4]|第[1-4一二三四]\s*季度|[1-4一二三四]\s*季度)"
    r"|(?P<version>v?\d+\.\d+(?:\.\d+)*)"
    r"|(?P<number>\d[\d,]*(?:\.\d+)?%?)",
    re.I,
)


def claim_key(text: str) -> str:
    """v1: replace every number, keeping historical anchor compatibility."""
    normalized = " ".join(text.lower().split())
    normalized = NUMBER_RE.sub("#", normalized)
    return normalized.strip("。 .")


def claim_key_v2(text: str, claim_type: str | None = None) -> str:
    """v2: periods/dates stay, values become '#'; additive to v1."""
    lower = " ".join(text.lower().split())
    parts: list[str] = []
    cursor = 0
    version_is_value = str(claim_type or "").lower() == "version"
    for match in V2_TOKEN_RE.finditer(lower):
        parts.append(lower[cursor : match.start()])
        token = match.group(0)
        if match.lastgroup in {"date", "cn_date", "quarter"}:
            parts.append(token)
        elif match.lastgroup == "version":
            parts.append("#" if version_is_value else token)
        else:
            parts.append("#")
        cursor = match.end()
    parts.append(lower[cursor:])
    return "".join(parts).strip("。 .")


def claim_keys(text: str, claim_type: str | None = None) -> tuple[str, str]:
    return claim_key(text), claim_key_v2(text, claim_type)
