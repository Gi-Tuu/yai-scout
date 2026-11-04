from __future__ import annotations

import re
from dataclasses import dataclass

from ...domain.models import Claim, TemporalSensitivity
from ...retrieval.tavily import SearchResult
from .patterns import (
    CURRENT_CLAIM_RE,
    HISTORICAL_CLAIM_RE,
    HISTORICAL_RE,
    HISTORICAL_RELEASE_RE,
    LATEST_RE,
    RELEASE_TITLE_RE,
    RELEASE_URL_RE,
    VERSION_TOKEN_RE,
)
from .types import Relation


@dataclass(frozen=True)
class VersionContexts:
    latest: set[str]
    historical: set[str]
    unmarked: set[str]


def evidence_text(result: SearchResult) -> str:
    return f"{result.title} {result.content}".lower()


def version_tokens(text: str) -> set[str]:
    return {match.lstrip("vV").lower() for match in VERSION_TOKEN_RE.findall(text)}


def version_tuple(value: str) -> tuple[int, ...]:
    parts = [int(part) for part in value.lstrip("vV").split(".") if part.isdigit()]
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def _last_marker(segment: str) -> str | None:
    latest = list(LATEST_RE.finditer(segment))
    historical = list(HISTORICAL_RE.finditer(segment))
    if not latest and not historical:
        return None
    if latest and (not historical or latest[-1].start() > historical[-1].start()):
        return "latest"
    return "historical"


def version_contexts(text: str) -> VersionContexts:
    matches = list(VERSION_TOKEN_RE.finditer(text))
    latest: set[str] = set()
    historical: set[str] = set()
    unmarked: set[str] = set()
    cursor = 0
    for index, match in enumerate(matches):
        version = match.group(0).lstrip("vV").lower()
        prefix = text[cursor:match.start()]
        next_start = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        suffix = text[match.end():next_start]
        kind = _last_marker(prefix) or _last_marker(suffix)
        if kind == "latest":
            latest.add(version)
        elif kind == "historical":
            historical.add(version)
        else:
            unmarked.add(version)
        cursor = match.end()
    return VersionContexts(latest=latest, historical=historical, unmarked=unmarked)


def release_target_version(result: SearchResult) -> str | None:
    for value in (result.url, result.title):
        match = RELEASE_URL_RE.search(value)
        if match:
            return match.group(1).lstrip("vV").lower()
        if RELEASE_TITLE_RE.fullmatch(value.strip()):
            match = VERSION_TOKEN_RE.search(value)
            if match:
                return match.group(0).lstrip("vV").lower()
    return None


def is_historical_release_claim(claim: Claim) -> bool:
    if CURRENT_CLAIM_RE.search(claim.text) or LATEST_RE.search(claim.text):
        return False
    if claim.temporal_sensitivity is TemporalSensitivity.STABLE:
        return True
    return bool(HISTORICAL_RELEASE_RE.search(claim.text))


def _historical_release_relation(
    claim: Claim, result_versions: set[str], result_years: set[str]
) -> Relation:
    claim_versions = version_tokens(claim.text)
    claim_years = set(re.findall(r"(?:19|20)\d{2}", claim.text))
    if claim_versions & result_versions:
        if claim_years & result_years:
            return "supports"
        return "mentions"
    return "mentions"


def _latest_relation(
    claim_versions: set[str], contexts: VersionContexts, claim_text: str
) -> Relation:
    if claim_versions & contexts.latest:
        return "supports"
    if HISTORICAL_CLAIM_RE.search(claim_text) and claim_versions & contexts.historical:
        return "supports"
    return "contradicts"


def _historical_context_relation(
    claim_versions: set[str], contexts: VersionContexts, claim_text: str
) -> Relation:
    if contexts.historical and claim_versions & contexts.historical:
        return "contradicts" if CURRENT_CLAIM_RE.search(claim_text) else "mentions"
    return "mentions"


def _release_target_relation(
    claim: Claim, claim_versions: set[str], result: SearchResult
) -> Relation:
    release_version = release_target_version(result)
    if not release_version or not CURRENT_CLAIM_RE.search(claim.text):
        return "mentions"
    from .project import same_project

    if not same_project(claim.text, result):
        return "mentions"
    claim_max = max(
        (version_tuple(version) for version in claim_versions), default=(0, 0, 0)
    )
    return "contradicts" if version_tuple(release_version) > claim_max else "mentions"


def _same_version_relation(
    claim_versions: set[str], result_versions: set[str]
) -> Relation:
    if result_versions == claim_versions:
        return "supports"
    if len(result_versions) == 1 and claim_versions & result_versions:
        return "supports"
    return "mentions"


def _classify_current_version(
    claim: Claim, result: SearchResult, claim_versions: set[str], text: str
) -> Relation:
    contexts = version_contexts(text)
    if contexts.latest:
        return _latest_relation(claim_versions, contexts, claim.text)
    if contexts.historical:
        return _historical_context_relation(claim_versions, contexts, claim.text)
    target_relation = _release_target_relation(claim, claim_versions, result)
    if target_relation == "contradicts":
        return "contradicts"
    return _same_version_relation(claim_versions, version_tokens(text))


def classify_version_relation(claim: Claim, result: SearchResult) -> Relation:
    text = evidence_text(result)
    claim_versions = version_tokens(claim.text)
    result_versions = version_tokens(text)
    if not (claim_versions and result_versions):
        return "mentions"
    if is_historical_release_claim(claim):
        return _historical_release_relation(
            claim,
            result_versions,
            set(re.findall(r"(?:19|20)\d{2}", text)),
        )
    return _classify_current_version(claim, result, claim_versions, text)
