"""Accuracy gate v0: deterministic rules over anchor + observations.

Design: docs/spec-accuracy-gate.md. No LLM decides correctness; no single-source
auto update; mirrors sharing an independent_group count as one source.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

GATE_VERSION = "accuracy-gate-v0"
TIER_WEIGHTS = {1: 1.0, 2: 0.8, 3: 0.5, 4: 0.25}


class GateDecision(StrEnum):
    AUTO_UPDATE = "auto_update"
    REVIEW = "review"
    REJECT = "reject"
    NO_CHANGE = "no_change"


@dataclass(slots=True)
class GateObservation:
    url: str
    source_tier: int
    independent_group: str
    value: str
    published_at: str | None = None
    content_hash: str = ""
    reachable: bool = True


@dataclass(slots=True)
class GateResult:
    decision: GateDecision
    reason: str
    confidence: float
    normalized_old: str = ""
    normalized_new: str = ""
    candidate_value: str = ""
    observations: list[GateObservation] = field(default_factory=list)


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed


def _date_only(value: str) -> bool:
    return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value.strip()))


def _ambiguous_thousands(value: str) -> bool:
    # 1.000 / 1,000 ambiguity is only for 3-digit groups; reject 1.234.567 style too.
    return bool(re.fullmatch(r"\d{1,3}\.\d{3}", value.strip()))


def normalize_value(raw: str, claim_text: str = "") -> tuple[str, bool]:
    """Return (normalized, ambiguous). Ambiguous must go to review."""
    text = " ".join(raw.strip().split())
    lower = text.lower()

    if not text:
        return "", True
    if _date_only(text):
        return text, True
    if _ambiguous_thousands(text):
        return text, True

    date_value = _parse_date(text)
    if date_value is not None and (("T" in text) or ("+" in text) or text.endswith("Z")):
        return date_value.astimezone(UTC).isoformat(), False

    license_match = re.fullmatch(
        r"(apache(?:[ -]?2(?:\.0)?)?|mit|agpl(?:[ -]?3(?:\.0)?)?"
        r"|gpl(?:[ -]?3(?:\.0)?)?|bsd(?:[ -]?3(?:[ -]clause)?)?)",
        lower,
    )
    if license_match:
        token = license_match.group(1).replace(" ", "-").replace("_", "-")
        if token.startswith("apache"):
            return "lic:apache-2.0", False
        if token.startswith("agpl"):
            return "lic:agpl-3.0", False
        if token.startswith("gpl"):
            return "lic:gpl-3.0", False
        if token.startswith("bsd"):
            return "lic:bsd-3-clause", False
        return f"lic:{token}", False

    version_match = re.fullmatch(r"v?(\d+(?:\.\d+){1,3}(?:[-+][A-Za-z0-9.]+)?)", text)
    if version_match and (
        "版本" in claim_text or "version" in claim_text.lower() or text.count(".") >= 2
    ):
        return f"ver:{version_match.group(1).lower()}", False

    amount_match = re.fullmatch(
        r"([$€£¥])?\s?(\d[\d,]*(?:\.\d+)?)\s*(credits?|usd|eur|cny|%)?",
        lower,
    )
    if amount_match:
        currency, number, unit = amount_match.groups()
        normalized_number = number.replace(",", "")
        if (
            currency in {"$", "€", "£", "¥"}
            or unit in {"usd", "eur", "cny"}
            or any(symbol in claim_text for symbol in ("$", "€", "£", "¥"))
        ):
            if "credit" in claim_text.lower() and unit is None:
                return f"amount:{normalized_number}", True
            return f"amount:{normalized_number}", False
        if unit == "credits" or unit == "%":
            return f"num:{normalized_number}", False
        return f"num:{normalized_number}", False

    if re.fullmatch(r"\d{1,3}(?:,\d{3})+", text):
        return f"num:{text.replace(',', '')}", False

    return text.lower(), False


def evaluate_gate(
    *,
    anchor_value: str,
    anchor_published_at: str | None,
    observations: list[GateObservation],
    claim_text: str = "",
) -> GateResult:
    usable = [item for item in observations if item.reachable and item.value.strip()]
    if not usable:
        return GateResult(GateDecision.REJECT, "no usable observations", 0.0)

    old_norm, old_ambiguous = normalize_value(anchor_value, claim_text)
    if old_ambiguous:
        return GateResult(GateDecision.REVIEW, "anchor value normalization ambiguous", 0.4)

    normalized: list[tuple[GateObservation, str, bool]] = []
    for observation in usable:
        value, ambiguous = normalize_value(observation.value, claim_text)
        normalized.append((observation, value, ambiguous))

    if all(value == old_norm and not ambiguous for _, value, ambiguous in normalized):
        return GateResult(
            GateDecision.NO_CHANGE,
            "normalized value equals current anchor",
            0.9,
            normalized_old=old_norm,
            normalized_new=old_norm,
            observations=usable,
        )

    if any(ambiguous for _, _, ambiguous in normalized):
        return GateResult(
            GateDecision.REVIEW,
            "observation value normalization ambiguous",
            0.4,
            normalized_old=old_norm,
            observations=usable,
        )

    anchor_time = _parse_date(anchor_published_at)
    newer = [
        (observation, value)
        for observation, value, _ in normalized
        if anchor_time is None
        or (
            observation.published_at
            and (_parse_date(observation.published_at) or anchor_time) >= anchor_time
        )
    ]
    if not newer:
        return GateResult(
            GateDecision.REJECT,
            "observations are older than anchor",
            0.2,
            normalized_old=old_norm,
            observations=usable,
        )

    authoritative = [
        (observation, value)
        for observation, value in newer
        if observation.source_tier <= 2
    ]
    if not authoritative:
        return GateResult(
            GateDecision.REJECT,
            "no authoritative (T1/T2) observation",
            0.2,
            normalized_old=old_norm,
            observations=usable,
        )

    values = {value for _, value in authoritative}
    if len(values) > 1:
        return GateResult(
            GateDecision.REVIEW,
            "authoritative observations conflict",
            0.5,
            normalized_old=old_norm,
            observations=usable,
        )

    new_norm = values.pop()
    groups = {observation.independent_group for observation, _ in authoritative}
    authority = max(
        TIER_WEIGHTS.get(observation.source_tier, 0.25)
        for observation, _ in authoritative
    )
    confidence = round(0.6 * authority + 0.4 * min(1.0, len(groups) / 2), 3)
    if len(groups) >= 2:
        return GateResult(
            GateDecision.AUTO_UPDATE,
            "two independent authoritative groups agree",
            confidence,
            normalized_old=old_norm,
            normalized_new=new_norm,
            candidate_value=new_norm,
            observations=usable,
        )
    return GateResult(
        GateDecision.REVIEW,
        "only one authoritative independent group",
        confidence,
        normalized_old=old_norm,
        normalized_new=new_norm,
        observations=usable,
    )


def evaluate_label_case(case: dict[str, Any]) -> GateResult:
    anchor = case.get("anchor", {})
    observations = [
        GateObservation(
            url=str(item.get("url", "")),
            source_tier=int(item.get("source_tier", 4)),
            independent_group=str(item.get("independent_group", "")),
            value=str(item.get("value", "")),
            published_at=item.get("published_at"),
            content_hash=str(item.get("content_hash", "")),
            reachable=bool(item.get("reachable", True)),
        )
        for item in case.get("observations", [])
    ]
    return evaluate_gate(
        anchor_value=str(anchor.get("value", "")),
        anchor_published_at=anchor.get("published_at"),
        observations=observations,
        claim_text=str(case.get("claim_text", "")),
    )



