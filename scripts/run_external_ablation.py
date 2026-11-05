"""Deterministic ablations on the frozen external evidence package."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from run_external_eval import _claim, _evidence, _latest_value, _rows

from yai_scout.detector.freshness import as_of_datetime, score_claim
from yai_scout.domain.models import EvidenceRef

VARIANTS = (
    "full",
    "full_minus_authority_gate",
    "full_minus_temporal_window",
    "full_minus_relation_rules",
    "full_minus_anchors",
    "full_minus_llm_relation",
)


def predict(row: dict, variant: str, root: Path | None = None) -> dict:
    claim = _claim(row)
    evidence: list[EvidenceRef] = _evidence(
        row, claim, root or Path("benchmarks/external_v1")
    )
    applicable = True
    if variant == "full_minus_relation_rules":
        evidence = [item.model_copy(update={"relation": "mentions"}) for item in evidence]
    elif variant == "full_minus_temporal_window":
        claim = claim.model_copy(update={"validity_window_days": 10**9})
    elif variant == "full_minus_authority_gate":
        evidence = [item.model_copy(update={"tier": 3}) for item in evidence]
    elif variant in {"full_minus_anchors", "full_minus_llm_relation"}:
        # Controlled external evidence does not use anchors or LLM relation.
        applicable = False
    verdict = score_claim(
        claim,
        evidence,
        as_of=as_of_datetime(row["as_of"]),
        allow_future=False,
    )
    return {
        "id": row["id"],
        "expected": row.get("gold_status"),
        "source_family": row.get("source_family", ""),
        "claim_type": row.get("claim_type", ""),
        "current_value": _latest_value(row, root or Path("benchmarks/external_v1")),
        "gold_current_value": row.get("gold_current_value"),
        "predicted": verdict.status.value,
        "score": verdict.score,
        "applicable": applicable,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True)
    parser.add_argument("--labels", default="")
    parser.add_argument("--variant", required=True, choices=VARIANTS)
    parser.add_argument("--out", default="")
    args = parser.parse_args(argv)
    rows = _rows(Path(args.data), Path(args.labels) if args.labels else None)
    data_root = Path(args.data).parent
    predictions = [predict(row, args.variant, data_root) for row in rows]
    payload = {
        "method": args.variant,
        "split": Path(args.data).stem,
        "cases": len(predictions),
        "predictions": predictions,
        "applicable": any(item["applicable"] for item in predictions),
    }
    if args.out:
        Path(args.out).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
