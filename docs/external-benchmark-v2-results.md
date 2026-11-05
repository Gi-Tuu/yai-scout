# External Benchmark V2 — L1 Mechanical Holdout Results

**Status: L1 mechanical holdout only. Not independent external test evidence.**

Data:

```text
split       = test
cases       = 182
labels      = mechanical PyPI timestamps
independent = false
kappa       = null
```

Primary comparison is frozen in:

```text
benchmarks/external_v2/protocol.json
```

## Primary (pre-registered)

| method | macro-F1 | STALE recall | false-fresh |
|---|---:|---:|---:|
| yais_full | 1.000 | 1.000 | 0.000 |
| citation_only | 0.500 | 0.000 | 0.000 |

```text
macro-F1 delta    = +0.500
STALE recall delta= +1.000
paired CI lower   = 0.500 / 1.000
threshold_met     = true
```

This is a **mechanical holdout regression result**, not a blind external test.

## Secondary

`recency_only` and `always_fresh` were run as controls:

```text
recency_only   macro-F1 delta = +0.667
always_fresh   macro-F1 delta = +0.667
```

They are exploratory and not pre-registered +0.10 comparisons.  
`llm_only` and `retrieval_only` were not re-run for L1 to avoid extra external
cost; their dev results remain in `docs/external-benchmark-results.md`.

## What this proves

```text
On mechanical PyPI holdout data, the full deterministic scorer separates
FRESH/STALE and beats citation_only on the frozen primary metrics.
```

## What this does not prove

```text
No independent human labels
No kappa
No blind test
No external test conclusion
No generalization claim
```

L2 remains blocked on two independent annotators and kappa >= 0.7.

## Reproduce

```powershell
.\.venv\Scripts\python.exe scripts\run_external_eval.py `
  --data benchmarks\external_v1\test.jsonl `
  --labels benchmarks\external_v1\mechanical_holdout\labels_test.jsonl `
  --method yais_full `
  --out <temporary>\test_yais_full.json
.\.venv\Scripts\python.exe scripts\run_external_eval.py `
  --data benchmarks\external_v1\test.jsonl `
  --labels benchmarks\external_v1\mechanical_holdout\labels_test.jsonl `
  --method citation_only `
  --out <temporary>\test_citation_only.json
.\.venv\Scripts\python.exe scripts\compare_external_eval.py `
  --protocol benchmarks\external_v2\protocol.json `
  --results <temporary> `
  --split test `
  --status mechanical_holdout `
  --out benchmarks\external_v2\results\test_summary.json
```

`result_hash`:

```text
sha256:36f32f3f1d1e22d6d1ad2a2ddbc4299f3e85ec80e01b697e7435892688fac78b
```
