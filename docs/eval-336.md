# Evaluation Report — labeler 336

> Date: 2026-11-02  
> Label file: `accuracy_labels_336.json` (public worksheet, `BL-001..BL-060`)  
> Key: `benchmarks/accuracy_gate/holdout_key.json` (**public/compromised**)

## 1. Critical evaluator bug found and fixed

The independent evaluator was comparing the **Gate prediction against the key**,
not against the human label:

```python
correct += int(prediction == expected_human)   # bug
```

It now uses:

```python
correct += int(prediction == human)            # fixed
```

Regression test: `tests/test_eval_metrics.py::test_evaluator_uses_human_labels_not_key`.

This means earlier “labeler 001 = 1.000” reports were wrong and must be
discarded.

## 2. Labeler 336 result (public set, compromised key)

```text
cases=60
agreement=0.267
gate_auto=18
auto_precision=0.222
false_update_rate=0.778
review_coverage=0.308 (4/13)
```

Confusion (human, gate) showed large disagreement in both directions, e.g.
human `review` vs gate `reject` (5), human `review` vs gate `auto_update` (5),
human `reject` vs gate `auto_update` (8).

## 3. Why this is not yet a Gate verdict

- The file uses **BL public IDs**, not the private `PV-*` worksheet;
- the public key is in the repository, so it is **compromised**;
- the disagreement is large enough that it may reflect a different rubric or a
  worksheet-version mismatch, not necessarily Gate error;
- one human labeler is not ground truth; adjudication is required.

Do not change Gate thresholds to fit this file.

## 4. Next steps

1. Ask labeler 336 to confirm the URL used (`/label` vs
   `/label?worksheet=private`) and whether the worksheet was refreshed.
2. Run the **private** 30-case worksheet (`PV-*`) with the same labeler; it has no
   public answer key.
3. Compare labeler 001 and 336 with `scripts/adjudicate_labels.py`; adjudicate
   disagreements.
4. Only adjudicated labels may be used as ground truth.

## 5. 001 vs 336

`adjudicate_labels.py` on the current 001 and 336 files: **47/60 disagreements**.
This is too large to treat either as final ground truth; a third adjudicator is
required.
