# Private Label Intake — 2026-11-02

## Files received

1. `accuracy_labels_private_jin.json` — 30/30 labels, labeler `jin`
2. `accuracy_labels_private_1.json` — 1/30 labels, labeler `1`

These files are kept outside the repository; they are not committed.

## Quality check

```text
labeler=jin
coverage=30/30
distribution={'no_change': 15, 'auto_update': 10, 'reject': 5}
SUSPICIOUS_NO_CHANGE=PV-001, PV-005, PV-006, PV-007, PV-009, PV-014,
  PV-016, PV-019, PV-020, PV-021, PV-022, PV-025
quality=needs_review
```

12 of the 15 `no_change` labels contradict the worksheet values (e.g. PV-001:
anchor `1000`, observations `4000`; PV-009: `AGPL-3.0` vs `Apache-2.0`).
There are **zero `review`** labels in 30 cases. This is a strong signal that the
rubric was misunderstood or the page was not read carefully.

`labeler=1` covered only 1/30 (`PV-001 = auto_update`), so it is incomplete and
cannot be used for agreement.

Gate metrics on `jin` (for reference only, **not valid ground truth**):

```text
agreement=0.433
auto_precision=0.727
false_update_rate=0.273
review_coverage=0.200
```

## Actions

- Added `scripts/check_label_quality.py` to reject incomplete/obviously
  inconsistent label files before they reach evaluation;
- Added a concise “how to decide” panel to `/label` so non-expert annotators see
  the four decisions and the rule “unsure → review”;
- Did **not** change Gate thresholds, labels, or auto-update behavior;
- Need one complete, carefully labeled private file (30/30) or a short version
  for a new annotator.

## Recommendation

- Do not use `jin` or `1` as ground truth;
- If the next annotator is also non-expert, reduce to a 10-case short worksheet;
- Run `check_label_quality.py` before `eval_accuracy_gate.py`.
