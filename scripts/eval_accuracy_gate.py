"""Evaluate accuracy-gate rules.

Default: rule-labeled 60-case set.
Independent labeling:
    python scripts/eval_accuracy_gate.py \
        --labels accuracy_labels_<name>.json \
        --key benchmarks/accuracy_gate/holdout_key.json
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from yai_scout.detector.accuracy_gate import evaluate_label_case

ROOT = Path(__file__).resolve().parents[1]
LABELS = ROOT / "benchmarks" / "accuracy_gate" / "labeled_cases.json"
KEY = ROOT / "benchmarks" / "accuracy_gate" / "holdout_key.json"


def evaluate_default() -> int:
    payload = json.loads(LABELS.read_text(encoding="utf-8"))
    total = correct = 0
    predicted = Counter()
    expected = Counter()
    auto_pred = auto_correct = 0
    misses = []
    for case in payload["cases"]:
        total += 1
        result = evaluate_label_case(case)
        want = case["expected"]["decision"]
        expected[want] += 1
        predicted[result.decision.value] += 1
        if result.decision.value == want:
            correct += 1
        else:
            misses.append((case["id"], want, result.decision.value, result.reason))
        if result.decision.value == "auto_update":
            auto_pred += 1
            if want == "auto_update":
                auto_correct += 1
    print(f"gate=accuracy-gate-v0 cases={total} agreement={correct / total:.3f}")
    print(f"predicted={dict(predicted)}")
    print(f"expected={dict(expected)}")
    print(f"auto_update_precision={auto_correct / auto_pred if auto_pred else 1.0:.3f}")
    for miss in misses:
        print("MISS", miss)
    return 0 if correct / total >= 0.85 else 1


def evaluate_independent(labels_path: Path, key_path: Path) -> int:
    labels_payload = json.loads(labels_path.read_text(encoding="utf-8"))
    labels = labels_payload.get("labels", {})
    key = json.loads(key_path.read_text(encoding="utf-8"))
    cases = {
        case["id"]: case
        for case in json.loads(LABELS.read_text(encoding="utf-8"))["cases"]
    }

    total = correct = 0
    gate_auto = auto_correct = false_update = 0
    human_auto = review_coverage = 0
    confusion: Counter[tuple[str, str]] = Counter()
    for worksheet_id, meta in key.items():
        human = labels.get(worksheet_id)
        if human is None:
            continue
        source_id = meta["source_id"]
        case = cases[source_id]
        prediction = evaluate_label_case(case).decision.value
        expected_human = meta["expected_decision"]
        total += 1
        correct += int(prediction == expected_human)
        confusion[(expected_human, prediction)] += 1
        if prediction == "auto_update":
            gate_auto += 1
            if expected_human == "auto_update":
                auto_correct += 1
            else:
                false_update += 1
        if expected_human == "auto_update":
            human_auto += 1
            if prediction == "review":
                review_coverage += 1

    if total == 0:
        print("no overlapping labels")
        return 2
    agreement = correct / total
    precision = auto_correct / gate_auto if gate_auto else 1.0
    fals = false_update / gate_auto if gate_auto else 0.0
    coverage = review_coverage / human_auto if human_auto else 0.0
    print(f"independent_labeler={labels_payload.get('labeler', 'unknown')}")
    print(f"cases={total} agreement={agreement:.3f}")
    print(f"gate_auto={gate_auto} auto_precision={precision:.3f} false_update_rate={fals:.3f}")
    print(f"review_coverage={coverage:.3f} ({review_coverage}/{human_auto})")
    print("confusion (human,gate):", dict(confusion))
    identical = all(
        labels.get(wid) == meta["expected_decision"] for wid, meta in key.items()
    )
    if identical:
        print(
            "WARNING: labels are identical to the hidden key. This may mean the "
            "annotator followed the same rule sheet or saw the key; do not treat "
            "it as independent validation."
        )
    return 0 if agreement >= 0.85 and fals <= 0.05 else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels", default=None)
    parser.add_argument("--key", default=str(KEY))
    args = parser.parse_args()
    if args.labels:
        return evaluate_independent(Path(args.labels), Path(args.key))
    return evaluate_default()


if __name__ == "__main__":
    raise SystemExit(main())

