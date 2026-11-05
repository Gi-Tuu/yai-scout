# External V2 — Mixed-Source Mechanical Smoke

**Status: smoke only. 9 cases. Mechanical labels. Not independent test.**

This is the first cross-source smoke slice, not the 190-case L3 target.

## Composition

```text
conflicted   = 3  (PyPI vs GitHub release tags at the same as_of)
insufficient = 3  (no usable evidence)
unknown      = 3  (unverifiable semantic claims, no evidence)
```

Total:

```text
9 cases
```

## Files

```text
mixed.jsonl                 public claim/evidence, no gold
mixed_manifest.json         hashes + status counts
mechanical_holdout/         labels, git-ignored
results/mixed_summary.json  aggregate only
```

## Result

| method | accuracy | macro-F1 |
|---|---:|---:|
| citation_only | 0.333 | 0.167 |
| yais_full | 0.667 | 0.500 |

Confusion for `yais_full`:

```text
conflicted  -> conflicted    3
insufficient-> insufficient  3
unknown     -> insufficient  3
```

What the smoke shows:

- two authoritative sources with differing latest versions can produce CONFLICTED;
- no-evidence cases abstain as INSUFFICIENT;
- the current system has no UNKNOWN output, so gold UNKNOWN falls back to
  INSUFFICIENT;
- stable/fresh cases are not included in this smoke slice.

What it does **not** show:

```text
no independent labels
no kappa
no L2/L3 external validation
not enough cases for per-status claims
```

The mixed smoke is a **gap detector**, not evidence of superiority.

## Next

- curate more authoritative stable/conflict sources;
- decide whether UNKNOWN is a supported status or must map to INSUFFICIENT;
- build 30+ cases per status before making any per-status claim;
- L2 still requires two independent annotators and kappa >= 0.7.
