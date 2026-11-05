# External Benchmark V2 — L1 Mechanical Holdout

**Status: L1 only. Mechanical labels; not independent external validation.**

This document records the v2 protocol and the L1 mechanical-holdout run.

## Protocol

```text
primary baseline = citation_only
primary thresholds:
  macro-F1 delta >= +0.10
  STALE recall delta >= +0.10
  paired bootstrap 95% CI lower > 0
  false-fresh <= 0.10
  stable false-stale <= 0.05
secondary = llm_only, recency_only, retrieval_only, always_fresh
```

Protocol file:

```text
benchmarks/external_v2/protocol.json
```

## L2 requirements (not met)

```text
two independent annotators
blind to system output
kappa >= 0.7
third-party custody of labels
```

The mechanical holdout does not satisfy these. Do not describe it as a blind
test or independent validation.

## Mixed-source smoke

See `docs/external-benchmark-v2-mixed.md` for the 9-case smoke set. It is
not a 5-state target dataset and not independent evidence.

## L1 result

See:

```text
benchmarks/external_v2/results/test_summary.json
docs/external-benchmark-v2-results.md
```

The L1 run only supports a regression statement on mechanical PyPI holdout
data. It does not establish an external test conclusion.
