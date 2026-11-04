# Benchmark Session State

`bench_session` has one canonical lifecycle source: the database columns.

```text
status
finished_at
error
result_hash
supersedes
```

`config_json` stores configuration only:

```text
id, owner_id, agent_ids, task_ids, dataset_version, config_hash, created_at
```

`manifest_json` stores the experiment manifest configuration only. Lifecycle
fields (`status`, `finished_at`, `result_hash`) are not persisted there.

On read, `Store.get_bench_session()` composes the public `BenchSession` from:

```text
config_json + manifest_json + lifecycle columns
```

Migration 10:

- strips lifecycle fields from legacy `config_json` and `manifest_json`;
- backfills `manifest_json` from a nested `config_json.manifest` when needed.

All lifecycle updates (`update_bench_session`, `mark_interrupted_work`) write the
columns, not the JSON blobs. `consistency_report()` flags any lifecycle fields
that reappear in JSON.
