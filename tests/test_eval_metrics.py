from __future__ import annotations

import json
from pathlib import Path

from scripts.eval_accuracy_gate import evaluate_independent


def test_evaluator_uses_human_labels_not_key(tmp_path: Path, capsys):
    labels = tmp_path / "labels.json"
    key = tmp_path / "key.json"
    labels.write_text(
        json.dumps({"labeler": "test", "labels": {"BL-001": "review"}}),
        encoding="utf-8",
    )
    key.write_text(
        json.dumps(
            {
                "BL-001": {
                    "source_id": "AG-05",
                    "expected_decision": "reject",
                }
            }
        ),
        encoding="utf-8",
    )
    result = evaluate_independent(labels, key)
    output = capsys.readouterr().out
    assert result == 1
    assert "agreement=0.000" in output
    assert "confusion (human,gate)" in output
