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
python scripts/prune_benchmarks.py --days 30 --audit-dir data/benchmark_prune_audit
```

Rules:

- only `done` / `failed` sessions;
- `finished_at` (fallback `created_at`) older than cutoff;
- `bench_result` rows are removed by FK cascade;
- `running` sessions are never touched;
- `--dry-run` only reports counts.

## Audit before delete

Before deleting, the affected sessions and results are written to a JSON
audit file. The default location is `benchmark_prune_audit/` beside the
database; `--audit-dir` overrides it. If the audit write fails, deletion is
aborted. The returned `audit_file` is the basename of the audit file.

The CLI is explicit. A startup hook is also available but disabled by default:

```text
BENCHMARK_RETENTION_DAYS=0   # disabled
BENCHMARK_RETENTION_DAYS=30  # prune terminal sessions older than 30 days at startup
```

Startup pruning never touches `running` sessions. Its result is exposed in
`/api/healthz` under `retention`; a failure is logged server-side and reported
publicly only as `retention_failed`, without raw exception details.

The default is `0` (disabled), so enabling retention is an explicit deployment
decision. `prune_benchmarks.py` remains the safe dry-run/inspection path.

## Notes

- The unique index prevents future duplicate rows; migration 9 cleans existing
  duplicates.
- A benchmark session with the same task/agent but a different run is a
  different session and remains valid.
- Pruning is irreversible. Run `--dry-run` first for production-like databases.
