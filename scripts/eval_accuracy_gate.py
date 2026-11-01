"""Evaluate accuracy-gate rules against benchmarks/accuracy_gate/labeled_cases.json."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from yai_scout.detector.accuracy_gate import evaluate_label_case

ROOT = Path(__file__).resolve().parents[1]
LABELS = ROOT / "benchmarks" / "accuracy_gate" / "labeled_cases.json"


def main() -> int:
    payload = json.loads(LABELS.read_text(encoding="utf-8"))
    total = 0
    correct = 0
    predicted = Counter()
    expected = Counter()
    auto_pred = 0
    auto_correct = 0
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
    agreement = correct / total if total else 0.0
    precision = auto_correct / auto_pred if auto_pred else 1.0
    print(f"gate=accuracy-gate-v0 cases={total} agreement={agreement:.3f}")
    print(f"predicted={dict(predicted)}")
    print(f"expected={dict(expected)}")
    print(f"auto_update_precision={precision:.3f} ({auto_correct}/{auto_pred})")
    for miss in misses:
        print("MISS", miss)
    return 0 if agreement >= 0.85 else 1


if __name__ == "__main__":
    raise SystemExit(main())
