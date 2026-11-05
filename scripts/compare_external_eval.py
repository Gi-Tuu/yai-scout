"""Compare external-eval methods against the pre-registered protocol."""
from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path

from score_external_eval import metrics

ROOT = Path(__file__).resolve().parents[1]


def _load_results(results_dir: Path, split: str) -> dict[str, dict]:
    methods: dict[str, dict] = {}
    for path in sorted(results_dir.glob(f"{split}_*.json")):
        if path.name.endswith(".score.json") or path.name == f"{split}_summary.json":
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        methods[payload["method"]] = payload
    return methods


def _pairs(full: dict, base: dict) -> list[tuple[dict, dict]]:
    full_rows = {row["id"]: row for row in full["predictions"]}
    base_rows = {row["id"]: row for row in base["predictions"]}
    return [
        (full_rows[case_id], base_rows[case_id])
        for case_id in sorted(set(full_rows) & set(base_rows))
    ]


def _delta(full_rows: list[dict], base_rows: list[dict]) -> dict[str, float]:
    full = metrics(
        [row["expected"] for row in full_rows],
        [row["predicted"] for row in full_rows],
        full_rows,
    )
    base_metrics = metrics(
        [row["expected"] for row in base_rows],
        [row["predicted"] for row in base_rows],
        base_rows,
    )
    return {
        "macro_f1_delta": round(full["macro_f1"] - base_metrics["macro_f1"], 6),
        "stale_recall_delta": round(
            full["stale_recall"] - base_metrics["stale_recall"], 6
        ),
        "false_fresh_delta": round(
            full["false_fresh_rate"] - base_metrics["false_fresh_rate"], 6
        ),
        "full_false_fresh": full["false_fresh_rate"],
        "full_stable_false_stale": full["stable_false_stale"],
    }


def _bootstrap_delta(
    pairs: list[tuple[dict, dict]], *, rounds: int = 2000, seed: int = 7
) -> dict[str, tuple[float, float]]:
    rng = random.Random(seed)
    macro: list[float] = []
    stale: list[float] = []
    for _ in range(rounds):
        indices = [rng.randrange(len(pairs)) for _ in pairs]
        sample = [pairs[i] for i in indices]
        result = _delta([a for a, _ in sample], [b for _, b in sample])
        macro.append(result["macro_f1_delta"])
        stale.append(result["stale_recall_delta"])
    macro.sort()
    stale.sort()
    return {
        "macro_f1": (
            macro[int(0.025 * rounds)],
            macro[int(0.975 * rounds) - 1],
        ),
        "stale_recall": (
            stale[int(0.025 * rounds)],
            stale[int(0.975 * rounds) - 1],
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--results", required=True)
    parser.add_argument("--split", default="dev")
    parser.add_argument("--status", default="")
    parser.add_argument("--out", default="")
    args = parser.parse_args(argv)
    protocol_path = Path(args.protocol)
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    primary = protocol["primary"]
    results = _load_results(Path(args.results), args.split)
    full = results.get("yais_full")
    base = results.get(primary["baseline"])
    if full is None or base is None:
        raise SystemExit("missing yais_full or primary baseline results")
    pairs = _pairs(full, base)
    delta = _delta([a for a, _ in pairs], [b for _, b in pairs])
    ci = _bootstrap_delta(pairs)
    thresholds = primary["thresholds"]
    threshold_met = (
        delta["macro_f1_delta"] >= thresholds["macro_f1_delta"]
        and delta["stale_recall_delta"] >= thresholds["stale_recall_delta"]
        and ci["macro_f1"][0] > 0
        and ci["stale_recall"][0] > 0
        and delta["full_false_fresh"] <= thresholds["false_fresh_max"]
        and delta["full_stable_false_stale"] <= thresholds["stable_false_stale_max"]
    )
    secondary: dict[str, dict] = {}
    for method in protocol.get("secondary", []):
        other = results.get(method)
        if other is None:
            continue
        other_pairs = _pairs(full, other)
        other_delta = _delta(
            [a for a, _ in other_pairs], [b for _, b in other_pairs]
        )
        secondary[method] = {
            "macro_f1_delta": other_delta["macro_f1_delta"],
            "stale_recall_delta": other_delta["stale_recall_delta"],
            "note": "exploratory; not the pre-registered primary comparison",
        }
    summary = {
        "protocol_hash": "sha256:"
        + hashlib.sha256(protocol_path.read_bytes()).hexdigest(),
        "split": args.split,
        "label_status": args.status or protocol.get("test_status", {}).get(
            "label_status", "unknown"
        ),
        "independent_labels": bool(
            protocol.get("test_status", {}).get("independent_labels", False)
        ),
        "primary": {
            "baseline": primary["baseline"],
            **delta,
            "delta_ci_lower": {
                "macro_f1": round(ci["macro_f1"][0], 6),
                "stale_recall": round(ci["stale_recall"][0], 6),
            },
            "threshold_met": threshold_met,
        },
        "secondary": secondary,
    }
    canonical = json.dumps(summary, sort_keys=True, ensure_ascii=False)
    summary["result_hash"] = "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()
    text = json.dumps(summary, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
