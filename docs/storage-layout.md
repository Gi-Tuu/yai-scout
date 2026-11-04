# Storage Layout

`Store` is now a facade over SQLite repositories.

```text
src/yai_scout/store.py              facade, public method signatures
src/yai_scout/storage/db.py         Database, locks, read/write/atomic, ping
src/yai_scout/storage/schema.py     SCHEMA + initialize
src/yai_scout/storage/migrations.py migrations 1–11, pre-v10 backup
src/yai_scout/storage/rows.py       row → domain model
src/yai_scout/storage/tasks.py      tasks/plans/sources/events/costs
src/yai_scout/storage/detector.py   detector reports
src/yai_scout/storage/benchmarks.py sessions/results
src/yai_scout/storage/benchmark_prune.py retention + audit files
src/yai_scout/storage/anchors.py    anchors/observations/audit/rollback
src/yai_scout/storage/anchor_candidates.py candidates/approval transaction
src/yai_scout/storage/snapshots.py  snapshots
src/yai_scout/storage/consistency.py consistency report
src/yai_scout/storage/maintenance.py interrupted-work recovery
```

Rules:

- `storage/*` may depend on `domain` and storage-internal modules only;
- `storage` must not import `api`, `benchmark`, `detector`, `pipeline`,
  `retrieval`, `sources` or `store`;
- all repositories share one `Database` connection and lock;
- public `Store` signatures are preserved;
- lifecycle/transaction semantics are unchanged.
