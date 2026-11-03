"""Candidate creation from anchor observations (shared by API and revalidation)."""

from __future__ import annotations

import ipaddress
import re
import uuid
from typing import Literal, cast
from urllib.parse import urlsplit

from ..claim_keys import claim_key_v2
from ..domain.models import (
    Anchor,
    AnchorCandidate,
    AnchorObservation,
    CandidateEvidence,
    utcnow_iso,
)
from ..store import Store
from .accuracy_gate import (
    GateDecision,
    GateObservation,
    evaluate_gate,
    normalize_value,
)

VERSION_RE = re.compile(r"v?(\d+(?:\.\d+){1,3}(?:[-+][A-Za-z0-9.]+)?)", re.I)
LICENSE_RE = re.compile(
    r"\b(apache(?:[ -]?2(?:\.0)?)?|mit|agpl(?:[ -]?3(?:\.0)?)?|gpl(?:[ -]?3(?:\.0)?)?)\b",
    re.I,
)
PRICE_SYMBOL_RE = re.compile(r"([$€£¥])\s?(\d[\d,]*(?:\.\d+)?)")
PRICE_UNIT_RE = re.compile(
    r"(\d[\d,]*(?:\.\d+)?)\s*(credits?|usd|eur|cny|美元|积分)", re.I
)
PORT_RE = re.compile(r"(?:port|端口)[^\d]{0,12}(\d{2,5})", re.I)
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}|\d{4}\s*年")


def _claim_kind(claim_text: str, old_value: str) -> str:
    lower = claim_text.lower()
    if PORT_RE.search(claim_text):
        return "port"
    if "许可证" in claim_text or "license" in lower:
        return "license"
    old_is_version = bool(
        re.fullmatch(r"v\d+(?:\.\d+){1,3}", old_value.strip(), re.I)
        or re.fullmatch(r"\d+(?:\.\d+){2,}", old_value.strip())
    )
    if old_is_version or "版本" in claim_text or "version" in lower:
        return "version"
    if any(
        token in lower
        for token in (
            "credits",
            "credit",
            "价格",
            "费用",
            "定价",
            "pricing",
            "price",
            "$",
            "€",
            "£",
            "¥",
            "usd",
        )
    ):
        return "pricing"
    if "年" in claim_text or "date" in lower or "发布" in claim_text:
        return "date"
    return "numeric"


PUBLIC_SUFFIXES = frozenset(
    {
        "co.uk", "org.uk", "ac.uk", "gov.uk",
        "com.au", "net.au", "org.au",
        "co.jp", "co.nz", "co.in", "co.za", "co.kr",
        "com.cn", "com.br", "com.sg", "com.hk", "com.tw",
        "com.mx", "com.tr", "com.ar",
    }
)


GITHUB_ORG_ALIASES = {
    "tavily-ai": "tavily.com",
    "deepseek-ai": "deepseek.com",
    "maximhq": "getbifrost.ai",
    "anthropic-ai": "anthropic.com",
    "openai": "openai.com",
}


def independent_group_from_url(url: str) -> str:
    """Publisher grouping: registrable domain + GitHub org aliases.

    Unknown GitHub orgs stay in their own ``github:<org>`` group; if another
    source cannot be proven to be the same publisher, the Gate should not
    auto-update on the pair without a known alias.
    """
    parts = urlsplit(url)
    host = (parts.hostname or "").lower().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    try:
        ipaddress.ip_address(host)
        return host
    except ValueError:
        pass
    if host == "github.com" or host.endswith(".github.com"):
        segments = [item for item in parts.path.split("/") if item]
        org = segments[0].lower() if segments else "unknown"
        return GITHUB_ORG_ALIASES.get(org, f"github:{org}")
    labels = host.split(".")
    if len(labels) >= 3 and ".".join(labels[-2:]) in PUBLIC_SUFFIXES:
        return ".".join(labels[-3:])
    if len(labels) >= 2:
        return ".".join(labels[-2:])
    return host


def _unique(values: list[str]) -> list[str]:
    seen: list[str] = []
    for value in values:
        if value not in seen:
            seen.append(value)
    return seen


def extract_value_hint(text: str, old_value: str, claim_text: str = "") -> str:
    """Typed value extraction; ambiguous results return "" and go to review."""
    if not text:
        return ""
    kind = _claim_kind(claim_text, old_value)

    if kind == "port":
        ports = _unique(PORT_RE.findall(text))
        return ports[0] if len(ports) == 1 else ""
    if kind == "license":
        licenses = _unique([item.group(1) for item in LICENSE_RE.finditer(text)])
        return licenses[0] if len(licenses) == 1 else ""
    if kind == "version":
        versions = _unique(VERSION_RE.findall(text))
        if not versions:
            return ""

        def version_key(item: str) -> list[int]:
            return [int(part) for part in re.findall(r"\d+", item)]

        return "v" + str(max(versions, key=version_key))
    if kind == "pricing":
        values = [f"{symbol}{number}" for symbol, number in PRICE_SYMBOL_RE.findall(text)]
        values += [number for number, _unit in PRICE_UNIT_RE.findall(text)]
        unique = _unique(values)
        return unique[0] if len(unique) == 1 else ""
    if kind == "date":
        dates = _unique(DATE_RE.findall(text))
        return dates[0] if len(dates) == 1 else ""

    numbers = _unique([str(item) for item in re.findall(r"\d[\d,]*(?:\.\d+)?", text)])
    old_digits = set(re.findall(r"\d[\d,\.]*", old_value))
    candidates = [number for number in numbers if number not in old_digits]
    return candidates[0] if len(candidates) == 1 else ""


def _best_observation(observations: list[GateObservation]) -> GateObservation | None:
    usable = [item for item in observations if item.reachable and item.value]
    if not usable:
        return None
    return max(usable, key=lambda item: (item.source_tier * -1, item.published_at or ""))


def create_candidate_from_observations(
    store: Store,
    anchor: Anchor,
    observations: list[AnchorObservation],
    *,
    auto_update: bool = False,
) -> AnchorCandidate | None:
    gate_observations = [
        GateObservation(
            url=item.url,
            source_tier=item.source_tier,
            independent_group=item.independent_group or item.url,
            value=item.value,
            published_at=item.published_at,
            content_hash=item.observed_hash,
            reachable=item.status != "unreachable",
        )
        for item in observations
    ]
    if not gate_observations:
        return None
    gate = evaluate_gate(
        anchor_value=anchor.last_value,
        anchor_published_at=anchor.published_at,
        observations=gate_observations,
        claim_text=anchor.claim_text,
    )
    if gate.decision is GateDecision.NO_CHANGE:
        return None
    best = _best_observation(gate_observations)
    if best is None:
        return None
    existing = store.find_anchor_candidate(
        anchor.id, gate.normalized_new, gate.decision.value
    )
    if existing is not None:
        return existing
    candidate = AnchorCandidate(
        id=f"cand_{uuid.uuid4().hex[:12]}",
        anchor_id=anchor.id,
        claim_key=anchor.claim_key,
        claim_key_v2=anchor.claim_key_v2,
        claim_key_version=anchor.claim_key_version,
        claim_type=anchor.claim_type,
        old_value=anchor.last_value,
        new_value=best.value,
        normalized_old=gate.normalized_old,
        normalized_new=gate.normalized_new,
        evidence=[
            CandidateEvidence(
                url=item.url,
                source_tier=item.source_tier,
                independent_group=item.independent_group,
                value=item.value,
                published_at=item.published_at,
                content_hash=item.observed_hash,
            )
            for item in observations
        ],
        gate_decision=cast(
            Literal["auto_update", "review", "reject", "no_change"],
            gate.decision.value,
        ),
        gate_reason=gate.reason,
        gate_version="accuracy-gate-v0",
        confidence=gate.confidence,
        accuracy_status=(
            "rejected" if gate.decision is GateDecision.REJECT else "pending"
        ),
        decided_at=(
            utcnow_iso() if gate.decision is GateDecision.REJECT else None
        ),
        decided_by="gate" if gate.decision is GateDecision.REJECT else "",
    )
    store.save_anchor_candidate(candidate)
    if gate.decision is GateDecision.AUTO_UPDATE and auto_update:
        return apply_candidate(store, candidate, status="auto_applied", decided_by="auto-gate")
    return candidate


def apply_candidate(
    store: Store,
    candidate: AnchorCandidate,
    *,
    status: str,
    decided_by: str,
) -> AnchorCandidate:
    anchor = store.get_anchor(candidate.anchor_id)
    if anchor is None:
        return candidate
    if not candidate.evidence:
        return candidate
    matching = [
        item
        for item in candidate.evidence
        if normalize_value(item.value, anchor.claim_text)[0]
        == candidate.normalized_new
    ]
    best = max(
        matching or candidate.evidence,
        key=lambda item: (item.source_tier * -1, item.published_at or ""),
    )
    new_anchor = Anchor(
        id=f"anc_{uuid.uuid4().hex[:12]}",
        claim_key=anchor.claim_key,
        claim_key_v2=anchor.claim_key_v2
        or claim_key_v2(anchor.claim_text, anchor.claim_type),
        claim_key_version=2 if (anchor.claim_key_v2 or anchor.claim_text) else 1,
        claim_type=anchor.claim_type,
        claim_text=anchor.claim_text,
        url=best.url or anchor.url,
        source_tier=best.source_tier or anchor.source_tier,
        last_value=best.value or candidate.new_value,
        content_hash=best.content_hash,
        published_at=best.published_at,
        last_verified_at=utcnow_iso(),
        supersedes=anchor.id,
        temporal_sensitivity=anchor.temporal_sensitivity,
    )
    updated = store.apply_candidate_transaction(
        candidate.id,
        new_anchor,
        status=status,
        decided_by=decided_by,
    )
    return updated or candidate










