# Benchmark Result Retention and Uniqueness

## Unique cell constraint

Migration 9 now guarantees one benchmark result per:

```text
(session_id, task_id, agent_id)
```

Before creating the unique index, the migration keeps the smallest row id for
each cell and deletes any legacy duplicates.

Existing deployments are migrated on `Store` startup. The migration is
idempotent and records version 9 in `schema_version`.

## TTL pruning

Terminal benchmark sessions can be removed with:

```bash
python scripts/prune_benchmarks.py --days 30 --dry-run
python scripts/prune_benchmarks.py --days 30
python scripts/prune_benchmarks.py --db data/scout.sqlite3 --days 30 --json
```

Rules:

- only `done` / `failed` sessions;
- `finished_at` (fallback `created_at`) older than cutoff;
- `bench_result` rows are removed by FK cascade;
- `running` sessions are never touched;
- `--dry-run` only reports counts.

The command is explicit; the app does not automatically delete benchmark
history on startup.

## Notes

- The unique index prevents future duplicate rows; migration 9 cleans existing
  duplicates.
- A benchmark session with the same task/agent but a different run is a
  different session and remains valid.
- Pruning is irreversible. Run `--dry-run` first for production-like databases.
