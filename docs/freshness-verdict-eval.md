# Freshness Verdict Evaluation

A claim-level evaluation of the deterministic Freshness scorer.

This is intentionally separate from the answer-accuracy benchmark:

```text
answer benchmark  = "did the agent answer the question correctly?"
verdict evaluation = "did the freshness scorer classify the claim correctly?"
```

The evaluation uses fixed evidence and explicit gold statuses. It does **not**
call Tavily or an LLM, so it is reproducible and has no API cost.

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
dataset = freshness-verdicts/1.0
cases   = 14
accuracy = 100.00% (14/14)
abstention_rate = 35.71%
```

The 100% is expected: the fixtures were designed against the documented
decision table, so this is a regression/conformance suite, not evidence of
independent generalization. A wrong label is caught by
`tests/test_verdict_eval.py::test_evaluator_detects_a_wrong_label`.

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
