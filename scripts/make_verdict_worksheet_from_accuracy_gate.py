#!/usr/bin/env python
"""Build a Freshness verdict labeling worksheet from the accuracy-gate private cases.

The source worksheet contains cases and observations but no expected decisions.
This script constructs fixed evidence for human Freshness status labels. The
relation shown is derived mechanically from value equality, not from a model.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from yai_scout.claim_classification import resolve_claim_type

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "benchmarks" / "accuracy_gate" / "private_worksheet.json"
DEFAULT_OUTPUT = ROOT / "benchmarks" / "freshness_verdicts_private.json"


def _norm(value: object) -> str:
    return " ".join(str(value or "").lower().split())


def _relation(anchor_value: str, observation_value: str) -> str:
    if not anchor_value or not observation_value:
        return "mentions"
    return "supports" if _norm(anchor_value) == _norm(observation_value) else "contradicts"


def build(source: Path = DEFAULT_SOURCE) -> dict:
    payload = json.loads(source.read_text(encoding="utf-8"))
    cases = []
    for item in payload.get("cases", []):
        claim_text = str(item.get("claim_text") or "").strip()
        if not claim_text:
            continue
        anchor = item.get("anchor") or {}
        anchor_value = str(anchor.get("value") or "")
        evidence = []
        for obs in item.get("observations") or []:
            evidence.append({
                "url": str(obs.get("url") or ""),
                "title": str(obs.get("url") or ""),
                "tier": int(obs.get("source_tier") or 3),
                "relation": _relation(anchor_value, str(obs.get("value") or "")),
                "published_at": obs.get("published_at"),
                "snippet": str(obs.get("value") or ""),
            })
        claim_type = resolve_claim_type(claim_text)
        cases.append({
            "id": str(item.get("worksheet_id") or f"PV-{len(cases) + 1:03d}"),
            "claim": {
                "text": claim_text,
                "type": claim_type.value,
                "temporal_sensitivity": str(item.get("temporal_sensitivity") or "sensitive"),
                "target_time": "2026-11-01",
            },
            "evidence": evidence,
            "case_type": "accuracy-gate-private",
            "tags": ["accuracy-gate", "human-labeling"],
            "notes": (
                "Relation is derived from anchor/observation value equality; "
                "label the claim status independently."
            ),
        })
    return {
        "version": "freshness-verdicts-private/1.0",
        "as_of": "2026-11-01",
        "source": str(source.relative_to(ROOT)) if source.is_relative_to(ROOT) else str(source),
        "description": (
            "Unlabeled claim-level Freshness worksheet derived from accuracy-gate "
            "private cases. No expected statuses."
        ),
        "cases": cases,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=str(DEFAULT_SOURCE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--version", default="freshness-verdicts-private/1.0")
    parser.add_argument(
        "--description",
        default=(
            "Unlabeled claim-level Freshness worksheet derived from accuracy-gate "
            "private cases. No expected statuses."
        ),
    )
    args = parser.parse_args(argv)
    data = build(Path(args.source))
    data["version"] = args.version
    data["description"] = args.description
    Path(args.output).write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"cases={len(data['cases'])} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
