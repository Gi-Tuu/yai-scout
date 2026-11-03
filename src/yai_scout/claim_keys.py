from __future__ import annotations

import re

from .domain.models import ClaimType

CLAIM_KEY_VERSION = 2
NUMBER_RE = re.compile(r"\d[\d,\.]*")
VERSION_SPECIFIC_RE = re.compile(
    r"\b(?:requires?|required|supports?|supported|compatible|compatibility"
    r"|minimum|since|only works?|runs? on|works? with|released?)\b"
    r"|兼容|支持|需要|要求|依赖|发布",
    re.I,
)
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


def _type_value(claim_type: ClaimType | str) -> str:
    return str(claim_type.value if isinstance(claim_type, ClaimType) else claim_type).lower()


def claim_key_v2(text: str, claim_type: ClaimType | str) -> str:
    """v2: periods/dates stay, values become '#'.

    Claim type is required. Version tokens are treated as the value for
    rolling version claims, but preserved for compatibility/requirements
    claims (e.g. "Python 3.12 is supported").
    """
    lower = " ".join(text.lower().split())
    type_value = _type_value(claim_type)
    version_is_value = type_value == "version" and not VERSION_SPECIFIC_RE.search(lower)
    parts: list[str] = []
    cursor = 0
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


def claim_keys(text: str, claim_type: ClaimType | str) -> tuple[str, str]:
    return claim_key(text), claim_key_v2(text, claim_type)
