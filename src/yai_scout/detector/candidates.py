"""Candidate creation from anchor observations (shared by API and revalidation)."""

from __future__ import annotations

import re
import uuid

from ..domain.models import Anchor, AnchorCandidate, AnchorObservation, utcnow_iso
from ..store import Store
from .accuracy_gate import GateDecision, GateObservation, evaluate_gate

VERSION_RE = re.compile(r"v?(\d+(?:\.\d+){1,3}(?:[-+][A-Za-z0-9.]+)?)", re.I)
CREDIT_RE = re.compile(r"([\d][\d,]*(?:\.\d+)?)\s*credits?", re.I)
LICENSE_RE = re.compile(r"\b(apache(?:[ -]?2(?:\.0)?)?|mit|agpl(?:[ -]?3(?:\.0)?)?)\b", re.I)


def extract_value_hint(text: str, old_value: str) -> str:
    """Heuristic value extraction for revalidation; ambiguous results go to review."""
    if not text:
        return ""
    if "license" in text.lower() or "许可证" in text:
        match = LICENSE_RE.search(text)
        if match:
            return match.group(1)
    old_is_version = bool(re.fullmatch(r"v?\d+(?:\.\d+){1,3}", old_value.strip(), re.I))
    if old_is_version:
        versions = VERSION_RE.findall(text)
        if versions:

            def version_key(item: str) -> list[int]:
                return [int(part) for part in re.findall(r"\d+", item)]

            return "v" + str(max(versions, key=version_key))
    credit = CREDIT_RE.search(text)
    if credit:
        return str(credit.group(1))
    numbers = [str(item) for item in re.findall(r"\d[\d,]*(?:\.\d+)?", text)]
    old_digits = set(re.findall(r"\d[\d,\.]*", old_value))
    for number in numbers:
        if number not in old_digits:
            return number
    return ""


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
    candidate = AnchorCandidate(
        id=f"cand_{uuid.uuid4().hex[:12]}",
        anchor_id=anchor.id,
        claim_key=anchor.claim_key,
        old_value=anchor.last_value,
        new_value=best.value,
        normalized_old=gate.normalized_old,
        normalized_new=gate.normalized_new,
        evidence=[
            {
                "url": item.url,
                "source_tier": item.source_tier,
                "independent_group": item.independent_group,
                "value": item.value,
                "published_at": item.published_at,
                "content_hash": item.observed_hash,
            }
            for item in observations
        ],
        gate_decision=gate.decision.value,
        gate_reason=gate.reason,
        gate_version="accuracy-gate-v0",
        confidence=gate.confidence,
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
    best = max(
        candidate.evidence,
        key=lambda item: (
            int(item.get("source_tier") or 4) * -1,
            str(item.get("published_at") or ""),
        ),
    )
    new_anchor = Anchor(
        id=f"anc_{uuid.uuid4().hex[:12]}",
        claim_key=anchor.claim_key,
        claim_text=anchor.claim_text,
        url=str(best.get("url") or anchor.url),
        source_tier=int(best.get("source_tier") or anchor.source_tier),
        last_value=str(best.get("value") or candidate.new_value),
        content_hash=str(best.get("content_hash") or ""),
        published_at=str(best.get("published_at") or "") or None,
        last_verified_at=utcnow_iso(),
        supersedes=anchor.id,
        temporal_sensitivity=anchor.temporal_sensitivity,
    )
    store.save_anchor(new_anchor)
    store.supersede_anchor(anchor.id, new_anchor.id)
    updated = candidate.model_copy(
        update={
            "accuracy_status": status,
            "decided_at": utcnow_iso(),
            "decided_by": decided_by,
            "applied_anchor_id": new_anchor.id,
        }
    )
    store.update_anchor_candidate(updated)
    return updated



