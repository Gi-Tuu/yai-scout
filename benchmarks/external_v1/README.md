# External V1 Dev Set

Track A, official PyPI release timestamps.

```text
dev.jsonl      56 cases, 28 fresh / 28 stale
snapshots/     frozen release-history text
results/       dev baseline predictions and scores
manifest.json  counts + data/snapshot hashes
```

Build:

```powershell
.\.venv\Scripts\python.exe scripts\build_external_set.py --pairs 8
```

This is a **dev** set, not the sealed test set. Test labels require two
independent annotators; see `docs/external-benchmark.md`.

No author project is included. Each snapshot is the source of truth used by
all baselines.

The dev run includes a negative result: `yais_full` does not meet the
pre-registered +0.10 advantage over `llm_only`; see
`docs/external-benchmark-results.md`.
