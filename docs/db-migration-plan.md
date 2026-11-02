# SQLite FK / JSON Migration Design

> Status: **proposal only** — do not run before the hackathon submission.
> Current live DB is ephemeral; a full table rebuild is a post-submission activity.

## 1. Why this needs a rebuild

SQLite cannot add a `FOREIGN KEY` with `ALTER TABLE`:

- `ALTER TABLE ... ADD COLUMN` works;
- adding FK/UNIQUE/CHECK constraints requires **rebuilding the table**;
- `PRAGMA foreign_keys` is disabled by default per connection.

Current schema duplicates `payload_json` with indexed columns:

| Table | Columns | Payload | Risk |
|---|---|---|---|
| `anchor` | id, claim_key, url, status | `Anchor` | drift; no FK |
| `anchor_candidate` | anchor_id, status | `AnchorCandidate` | drift; orphan |
| `anchor_observation` | anchor_id, status | `AnchorObservation` | orphan |
| `anchor_audit` | anchor_id | dict | audit must survive deletes |
| `detector_report` | id, owner_id, answer, as_of | `DetectorReport` | drift |
| `bench_session` | id, owner_id, status | `BenchSession` | drift (found) |
| `bench_result` | session_id | `TaskResult` | orphan |
| `source`/`plan`/`run_event`/`cost_ledger` | task_id | mixed | orphan |

`scripts/db_consistency.py` already detects drift/orphans without changing
anything. It found the benchmark `config_json` stale-status bug.

## 2. Policy: hybrid schema, not full normalization

Keep `payload_json` for rich nested objects. Columns are not a second source of
truth; they exist for:

- ownership (`owner_id`);
- filtering (`status`, `claim_key`);
- ordering (`created_at`);
- join keys (`task_id`, `session_id`, `anchor_id`);
- integrity (`FOREIGN KEY`, `UNIQUE`).

Rules:

1. Columns listed above are **mirrors** and must be updated in the same
   transaction as the payload.
2. `consistency_report()` remains part of CI/DBA checks.
3. Do not split nested JSON into dozens of tables in this migration.

## 3. Target constraints

```sql
PRAGMA foreign_keys = ON;

-- research
research_task(id PK, owner_id, status, created_at, ...)
source(id PK, task_id REFERENCES research_task(id) ON DELETE CASCADE, ...)
plan(task_id PK REFERENCES research_task(id) ON DELETE CASCADE, ...)
run_event(seq PK, task_id REFERENCES research_task(id) ON DELETE CASCADE, ...)
cost_ledger(id PK, task_id REFERENCES research_task(id) ON DELETE CASCADE, ...)

-- benchmark
bench_session(id PK, owner_id, status, ...)
bench_result(id PK, session_id REFERENCES bench_session(id) ON DELETE CASCADE, ...)

-- anchors
anchor(id PK, claim_key, url, status, ...)
anchor_candidate(id PK, anchor_id REFERENCES anchor(id) ON DELETE RESTRICT, ...)
anchor_observation(id PK, anchor_id REFERENCES anchor(id) ON DELETE RESTRICT, ...)
anchor_audit(id PK, anchor_id, ...)  -- no FK: audit survives anchor deletion
snapshot(id PK, ...)                 -- no parent relationship
detector_report(id PK, owner_id, ...) -- no FK
```

Decisions:

- `anchor_audit` intentionally has no FK; audit must outlive entities.
- candidate/observation use `RESTRICT`; anchors are superseded, not deleted.
- `snapshot` stays independent (URL is not a foreign key).
- `detector_report` has no parent; owner is a session capability token.
- `ON DELETE CASCADE` for task children; no current delete API, but safe.
- Add indexes: `owner_id`, `status`, `created_at`, join columns.

## 4. Migration procedure (post-submission)

### 4.1 Preflight

```powershell
python scripts/db_admin.py check --db data/scout.sqlite3
python scripts/db_admin.py backup --db data/scout.sqlite3 --out backups/pre-fk.sqlite3
python scripts/db_consistency.py --db data/scout.sqlite3
```

Abort if integrity fails or consistency issues are non-empty.

### 4.2 Transaction shape

DDL is transactional in SQLite, but `PRAGMA foreign_keys` cannot be changed
inside a transaction:

```sql
PRAGMA foreign_keys = OFF;
BEGIN IMMEDIATE;

-- 1. create *_new tables with FKs and CHECKs
-- 2. INSERT INTO *_new SELECT ... FROM old
-- 3. validate row counts and checksums
-- 4. DROP old; ALTER *_new RENAME TO old
-- 5. recreate indexes

PRAGMA foreign_key_check;
COMMIT;
PRAGMA foreign_keys = ON;
```

Rebuild order (parents first):

1. `research_task`
2. `plan`, `source`, `run_event`, `cost_ledger`
3. `bench_session`, `bench_result`
4. `anchor`, `anchor_candidate`, `anchor_observation`
5. `detector_report` (owner/status mirror only)

`anchor_audit` and `snapshot` are left in place (no FK needed).

### 4.3 Data checks

Before dropping old tables:

- row count equality per table;
- `PRAGMA foreign_key_check` on the new tables;
- `Store.consistency_report()` on the rebuilt DB;
- sample report/candidate JSON round-trip;
- run the full test suite against a copy.

### 4.4 Failure / rollback

- Any mismatch: `ROLLBACK`, keep old DB, restore from backup if needed.
- Do not “fix” orphans silently; either:
  - quarantine orphans into `*_orphan` tables, or
  - abort and inspect.
- Keep the pre-migration backup until the next deploy is verified.

## 5. Code changes required

- A `schema_version = 7` migration runner method, not ad-hoc SQL in `Store.__init__`.
- Turn on `PRAGMA foreign_keys=ON` after migration, before normal use.
- Update all insert/update paths to write mirrored columns.
- Keep `consistency_report()` and add it to a DBA/CI step.
- Add fixtures:
  - old schema;
  - one orphan row per relationship;
  - migration idempotency;
  - FK enforcement (`IntegrityError` on bad child);
  - rollback on validation failure.

## 6. Explicit non-goals

- No full normalization of `DetectorReport`/`Claim`/`EvidenceRef`.
- No PostgreSQL migration.
- No background live migration while traffic is served.
- No migration before the hackathon submission.

## 7. Recommended timing

| Phase | When |
|---|---|
| Design + dry-run on copy | after submission |
| Migration 7 + backup/restore drill | before any production data matters |
| Enable FK enforcement | after full test suite and consistency report pass |
| Remove legacy JSON mirrors | much later, only if needed |
