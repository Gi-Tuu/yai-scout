# External Benchmark — Dev Results

**Status: dev-only, mechanical Track A labels. Not the sealed external test set.**

Data:

```text
dev cases = 56 (28 fresh, 28 stale)
source    = official PyPI release timestamps
hash      = see benchmarks/external_v1/manifest.json
```

All baselines use the same claim and the same frozen evidence snapshot.

## Results

| method | accuracy | macro-F1 | STALE recall | false-fresh | stable false-stale | abstention |
|---|---:|---:|---:|---:|---:|---:|
| always_fresh | 0.500 | 0.333 | 0.000 | 1.000 | 0.000 | 0.000 |
| recency_only | 0.500 | 0.333 | 0.000 | 1.000 | 0.000 | 0.000 |
| citation_only | 0.500 | 0.500 | 0.000 | 0.000 | 0.000 | 0.500 |
| yais_full | 1.000 | 1.000 | 1.000 | 0.000 | 0.000 | 0.000 |

## What this shows

On this controlled dev slice:

- citation-only never marks a still-supported claim stale;
- recency-only marks everything fresh because the evidence is recent;
- the full deterministic rule distinguishes FRESH from STALE;
- stable false-stale is 0 on the observed fresh cases.

## What this does not show

```text
No independent human test labels
No sealed test split
No LLM-only baseline
No retrieval-only baseline
No current-value accuracy
No general accuracy / leaderboard claim
```

The test split remains blocked on two independent annotators and kappa >= 0.7.
Do not cite this table as external test evidence.

## Reproduce

```powershell
.\.venv\Scripts\python.exe scripts\run_external_eval.py --method always_fresh `
  --out benchmarks\external_v1\results\dev_always_fresh.json
.\.venv\Scripts\python.exe scripts\score_external_eval.py `
  --input benchmarks\external_v1\results\dev_always_fresh.json
```

`result_hash` values:

```text
always_fresh  sha256:59155518ec52884967a01d8ef1aaa99d0f0498cab6f497856aa89b01f1025182
recency_only  sha256:10fb12310f4af0b42fdae9f93f27e953b36a15695fd236bf6378bdf30caa7c80
citation_only sha256:951903b3b989a2d0bfac735961b90679c15aba08533d0fdeb98a4654f370dd72
yais_full     sha256:caf02ae3d363c6abb5b57559f0f63e0eda1a6ee8148cf5ac6b68b75e45958f0b
```
