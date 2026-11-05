# External V2 — L1 Mechanical Holdout

This directory is deliberately **not** an independent external test.

```text
status          = L1_mechanical_holdout
labels          = mechanical PyPI timestamps
independent     = false
labelers        = 0
kappa           = null
```

Data is reused from `benchmarks/external_v1`:

```text
test.jsonl          182 public claim + evidence rows (no gold)
mechanical_holdout/  git-ignored mechanical labels
results/            test_summary + ablation_summary + mixed_summary
mixed.jsonl         9-case cross-source mechanical smoke
```

The v2 protocol is frozen for the primary comparison:

```text
primary baseline = citation_only
thresholds       = macro-F1 +0.10, STALE recall +0.10,
                   paired bootstrap lower > 0,
                   false-fresh <= 0.10, stable false-stale <= 0.05
```

`llm_only` remains a secondary/exploratory control.  
L2 is blocked on two independent annotators and kappa >= 0.7; no L2 result is
claimed here.

## Label files

L2 labelers should use:

```text
labels/labeler_a.jsonl  {"id": "...", "status": "fresh|stale|conflicted|insufficient|unknown"}
labels/labeler_b.jsonl
labels/adjudicated.jsonl
```

Validate with:

```powershell
.\.venv\Scripts\python.exe scripts\check_external_labels.py `
  --a labels\labeler_a.jsonl `
  --b labels\labeler_b.jsonl `
  --adjudicated labels\adjudicated.jsonl
```

Do not fill these with mechanical labels.
