# External Benchmark Pre-registration

Status: **protocol frozen for dev; test split not generated.**

This document defines the external benchmark before any test labels exist. It is
not a claim of general accuracy or an industry leaderboard.

## 1. Scope

Prove, on externally sourced facts:

- a claim can move FRESH → STALE across `as_of`;
- the full deterministic system can beat citation-only, recency-only and
  always-fresh baselines on the same evidence;
- stable facts are not marked STALE merely because the source is old;
- insufficient evidence produces abstention.

Do not claim:

- general accuracy;
- cross-domain generalization;
- that the author's own release history is external evidence.

## 2. Track A data

Source: official PyPI JSON API release timestamps.

Each case:

- claim: `<package> 当前版本是 <old version>`;
- `as_of`: before or after the next official release;
- gold:
  - `fresh` when the claimed version is the latest release at `as_of`;
  - `stale` when a newer official release exists at `as_of`;
- evidence: one frozen snapshot of the official release history, with
  `published_at`, `sha256`, `snapshot_path`;
- `gold_support` is separate from `gold_status`.

Dev set:

```text
benchmarks/external_v1/dev.jsonl
cases=56
fresh=28
stale=28
source_families=5 PyPI projects
```

No YAI Agent Core cases. No author-created snapshots.

Test set is not generated yet. When generated it must use a disjoint
`source_family` group and be sealed before labels are opened.

## 3. Baselines

Same claim and evidence package for B0–B2 and B5:

```text
B0 always_fresh
B1 recency_only      (evidence date inside 365 days)
B2 citation_only     (evidence supports claim => FRESH)
B5 yais_full         (deterministic score_claim)
```

Deferred until independent labels and model budget exist:

```text
B3 llm_only
B4 retrieval_only
```

B4 must be reported separately because its retrieval is not the same evidence
package.

## 4. Metrics

Primary:

```text
macro-F1
STALE recall
false-fresh rate
status accuracy
stable false-stale
abstention rate
current-value accuracy (test only; requires label + prediction value)
```

Secondary:

```text
per-class P/R/F1
confusion matrix
bootstrap 95% CI
per-family table
cost and latency (separate)
```

## 5. Frozen thresholds for the future test split

These thresholds are fixed now, before any test labels are produced:

```text
yais_full vs citation_only:
  STALE recall absolute improvement >= 0.10
  macro-F1 absolute improvement >= 0.10
  bootstrap 95% CI lower bound > 0
  false-fresh rate <= 0.10
  stable false-stale <= 0.05
```

If the test split does not meet these, publish a negative result. Do not change
thresholds after seeing test results.

## 6. Independent labels

Test labels require:

- two annotators who do not see system verdicts and do not implement the rules;
- codebook in this document;
- independent labeling, then adjudication;
- Cohen's kappa or Krippendorff's alpha >= 0.7;
- labels sealed and hash recorded before the blind run.

This repository currently has **dev-only** mechanical labels, not independent
human test labels.

## 7. Commands

```powershell
.\.venv\Scripts\python.exe scripts\build_external_set.py --pairs 8
.\.venv\Scripts\python.exe scripts\run_external_eval.py --method yais_full `
  --out benchmarks\external_v1\results\dev_yais_full.json
.\.venv\Scripts\python.exe scripts\score_external_eval.py `
  --input benchmarks\external_v1\results\dev_yais_full.json
```

## 8. Result integrity

- data hash: `benchmarks/external_v1/manifest.json`
- per-method raw predictions: `benchmarks/external_v1/results/`
- each score JSON contains `result_hash`
- snapshots are committed text files, so scoring is offline-reproducible.
