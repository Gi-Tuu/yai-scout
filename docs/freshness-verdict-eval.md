# Freshness Verdict Evaluation

A claim-level evaluation of the deterministic Freshness scorer.

This is intentionally separate from the answer-accuracy benchmark:

```text
answer benchmark  = "did the agent answer the question correctly?"
verdict evaluation = "did the freshness scorer classify the claim correctly?"
```

The evaluation uses fixed evidence and explicit gold statuses. It does **not**
call Tavily or an LLM, so it is reproducible and has no API cost.

The suite has 50 cases: standard, adversarial and ambiguous. The private
labeling bridge derives an unlabeled 30-case worksheet from the accuracy-gate
private cases; human labels are evaluated with the same metrics.

## Dataset

`benchmarks/freshness_verdicts.json` is a conformance suite, not an independent
human benchmark. Cases cover:

- fresh official support;
- stale official contradiction;
- conflicted authoritative sources;
- no evidence;
- low-authority single support;
- stable facts with old support;
- missing publication date;
- expired support;
- stable support outside the recency window;
- version claims;
- future contradiction exclusion;
- mentions-only evidence;
- authority contradiction plus low-authority support.

Statuses:

```text
fresh / stale / conflicted / insufficient / unknown
```

## Run

```bash
python scripts/eval_freshness_verdicts.py
```

Machine-readable:

```bash
python scripts/eval_freshness_verdicts.py --json
```

Threshold gate:

```bash
python scripts/eval_freshness_verdicts.py --min-accuracy 0.8
```

## Current result

```text
dataset = freshness-verdicts/1.1
cases   = 50
accuracy = 100.00% (50/50)
abstention_rate = 26.00%
scored_cases = 39
mean_score = 71.7
```

The 100% is expected: the fixtures were designed against the documented
decision table, so this is a regression/conformance suite, not evidence of
independent generalization. A wrong label is caught by
`tests/test_verdict_eval.py::test_evaluator_detects_a_wrong_label`.

Standard/adversarial/ambiguous breakdown is reported by `case_type`.

## Metrics

- accuracy: exact status match;
- per-status precision / recall / F1;
- confusion matrix;
- abstention rate: predicted `insufficient` or `unknown`;
- scored cases and mean score.

## Limitations

- No independent human labels.
- Fixed evidence does not exercise Tavily retrieval errors or page fetching.
- The suite is small; extend it before making statistical claims.
- It evaluates the scorer, not the answer generator.


## Private labeling bridge

The accuracy-gate private worksheet contains cases and observations but no
expected decisions. Convert it to an unlabeled verdict worksheet:

```bash
python scripts/make_verdict_worksheet_from_accuracy_gate.py
```

This writes:

```text
benchmarks/freshness_verdicts_private.json
```

30 cases, no `expected_status`. The relation shown for each evidence item is
derived mechanically from anchor/observation value equality; the human label is
the claim-level Freshness status.

Annotate at:

```text
/label/verdict
/label/verdict?worksheet=holdout
```

`holdout` uses the separate 60-case v2 worksheet. The source 60-case accuracy
set is publicly documented as compromised, so use it for contamination and
labeling workflow checks, not as evidence of independent generalization.

Labels stay in the browser and export as:

```json
{"version":"freshness-verdict-labels/1.0",
 "labeler":"...",
 "labels":{"PV-001":"fresh","PV-002":"stale"}}
```

Evaluate exported labels:

```bash
python scripts/eval_freshness_verdicts.py \
  --worksheet benchmarks/freshness_verdicts_private.json \
  --labels freshness-verdict-labels.json
```

Labels are intentionally not committed. The worksheet contains case data only;
it is not a gold set.
