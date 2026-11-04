# External Benchmark — Dev Results

**Status: dev-only, mechanical Track A labels. Not a sealed external test.**

Data:

```text
dev cases = 56 (28 fresh, 28 stale)
source    = official PyPI release timestamps
hash      = see benchmarks/external_v1/manifest.json
```

All B0–B3 and B5 use the same claim and the same frozen evidence snapshot.
B4 retrieves independently and is reported separately.

## Results

| method | accuracy | macro-F1 | STALE recall | false-fresh | stable false-stale | abstention | current-value |
|---|---:|---:|---:|---:|---:|---:|---:|
| always_fresh | 0.500 | 0.333 | 0.000 | 1.000 | 0.000 | 0.000 | 1.000 |
| recency_only | 0.500 | 0.333 | 0.000 | 1.000 | 0.000 | 0.000 | 1.000 |
| citation_only | 0.500 | 0.500 | 0.000 | 0.000 | 0.000 | 0.500 | 1.000 |
| yais_full | 1.000 | 1.000 | 1.000 | 0.000 | 0.000 | 0.000 | 1.000 |
| llm_only | 0.982 | 0.982 | 1.000 | 0.000 | 0.036 | 0.000 | 1.000 |
| retrieval_only | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 | 0.000 |

`current-value` is measured on the 28 STALE rows.

Result hashes:

```text
always_fresh   sha256:613ceffef6f66f9ab04084606931c5d7381a2b0a85683321433dc48b18acc844
recency_only   sha256:afa8ccbfcb23683368999281f60e8c8f7a0067392ffa5de63e1abc61fb022e2d
citation_only  sha256:4169b1ca1bc372be93a169c5ce1f832a40af865ca5c1d437b134d4feb6581de7
yais_full      sha256:2b639f2ac54fa4d320f133a0ed973efe1b199be4c66c3ed447211d2cd97934bc
llm_only       sha256:0f77b072a938a5045bdeb47614fc7acedd4ea7a129ff8eb2ef8f22fa13d4178f
retrieval_only sha256:c6d45e962efdfcd7072975bf0fee6050eb554dda5e952c47a49c79ff0f30e527
```

## Primary comparison (pre-registered, dev only)

| method | macro-F1 | STALE recall | false-fresh |
|---|---:|---:|---:|
| yais_full | 1.000 | 1.000 | 0.000 |
| citation_only | 0.500 | 0.000 | 0.000 |

```text
delta macro-F1 = +0.500
delta STALE recall = +1.000
paired bootstrap CI lower bounds = 0.500 / 1.000
threshold_met = true
```

The +0.10 primary threshold is met on this dev slice.  
This is dev-only mechanical PyPI data, not independent test evidence.

## Secondary comparison (exploratory)

```text
yais_full vs llm_only
macro-F1 delta = +0.018
STALE recall delta = 0.000
```

This is not the pre-registered primary threshold and does not show a +0.10
advantage. The result is retained because it is an honest secondary control.

## What this shows

- citation-only cannot detect STALE when the cited evidence still contains the
  old value;
- recency-only treats recent evidence as fresh;
- an LLM judge is already very strong on clean, single-snapshot evidence;
- retrieval-only is not a meaningful freshness baseline in this construction
  (it abstains on all 56 cases).

## What this does not show

```text
No independent human test labels
No sealed test split
No kappa
No general accuracy / leaderboard claim
```

Test remains blocked on two independent annotators and kappa >= 0.7.

## Reproduce

```powershell
.\.venv\Scripts\python.exe scripts\run_external_eval.py --method llm_only `
  --out benchmarks\external_v1\results\dev_llm_only.json
.\.venv\Scripts\python.exe scripts\score_external_eval.py `
  --input benchmarks\external_v1\results\dev_llm_only.json
```

## Sealed mechanical test candidate

A 182-case test candidate set now exists:

`	ext
benchmarks/external_v1/test.jsonl          no gold labels
benchmarks/external_v1/sealed/labels_test.jsonl  git-ignored
`

This is **not** an independent test: labels are mechanically derived from PyPI
timestamps, and no two independent annotators have produced a kappa. It is a
holdout candidate only.

Mechanical result:

`	ext
yais_full accuracy = 1.000
test hash           = 8f11b56348699c90c3986788d77dbdfa535c998ea381b875489b3f5aed73875e
labels hash         = 0c0d827d7016b73528918c687efd0165ebf5ee4fb1635d7329f5fc2f343eeec2
`

Do not cite this as external test evidence.
\n