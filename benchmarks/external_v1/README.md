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

This is a **dev** set, not an independent test set. Test labels require two
independent annotators; see `docs/external-benchmark.md`.

No author project is included. Each snapshot is the source of truth used by
all baselines.

The dev run meets the pre-registered primary comparison vs `citation_only`.
It does not show a +0.10 advantage over the secondary `llm_only` control.
Dev-only; not independent test evidence.
