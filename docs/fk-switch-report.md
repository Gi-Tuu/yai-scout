# FK Migration Switch Report — 2026-11-03

## 1. Migrated copy

```text
source : data/scout.sqlite3
target : backups/fk-copy.sqlite3
before : 13 tables, 0 orphans, 0 duplicate bench results
after  : row counts unchanged
FK     : anchor_candidate -> anchor present
checks : foreign_key_check=ok, integrity_check=ok
```

The app was started against the copy on port 8013:

- `/api/healthz` = ok, 32 snapshots
- `/freshness`, `/label?worksheet=private`, `/benchmark` = 200
- replay `0.24.0 @ 2026-10-28` = FRESH / 88
- report / receipt / export = 200 with the session cookie
- FK enforcement: orphan `anchor_candidate` insert blocked

## 2. Local switch (completed)

- pre-switch backup:
  `backups/pre-fk-local-20261103-105532.sqlite3`
- stopped local server
- replaced `data/scout.sqlite3` with the migrated copy
- removed `-wal` / `-shm`
- `db_admin check` = ok
- `db_consistency` = 0 issues
- `anchor_candidate` FK present
- restarted Scout on port 8014:
  - health ok
  - replay report FRESH / 88
  - report / receipt / export 200
- stopped server

Rollback for the local DB:

```powershell
Copy-Item backups/pre-fk-local-20261103-105532.sqlite3 data/scout.sqlite3 -Force
```

## 3. Production switch (NOT completed)

Render service:

```text
plan   = free
disk   = none
data   = ephemeral container filesystem
```

`GET /disks?serviceId=...` returns nothing, and `serviceDetails` has no disk.
That means:

- the current live DB is recreated on deploy/restart;
- uploading/replacing a migrated DB is not durable;
- a production FK switch would be lost on the next restart.

Therefore production was **not** switched. Doing so would only create a
misleading one-off DB.

## 4. What is needed for a real production switch

1. Add a Render persistent disk or move to Postgres.
2. Point `DB_PATH` at the durable location.
3. Run `scripts/migrate_fk.py` against that DB copy.
4. Enable maintenance mode / stop writers.
5. Swap the DB atomically, run `foreign_key_check` + consistency.
6. Deploy and verify health/replay, then remove maintenance mode.
7. Keep the pre-switch backup.

## 5. Current code state

- `PRAGMA foreign_keys=ON` is set by `Store`.
- Existing old-schema DBs have no FK constraints, so the pragma is a no-op there.
- Migrated DBs now enforce FKs.
- Tests: 227 passed; ruff/mypy/architecture pass.

## 6. Honest limitation

Local switch and validation are real. Production switch is blocked by
infrastructure, not by code. Do not claim production FK enforcement.
