# Database operations

SQLite is the single runtime store. The app applies `schema_version` migrations
on startup; backups/restores are **offline scripts** and never run from the API.

## Check

```powershell
python scripts/db_admin.py check --db data/scout.sqlite3
# integrity=ok
```

## Backup

```powershell
python scripts/db_admin.py backup `
  --db data/scout.sqlite3 `
  --out backups/scout-2026-11-02.sqlite3
# backup=... sha256=... integrity=ok
```

## Restore

Restore refuses to overwrite an existing DB unless explicitly forced:

```powershell
python scripts/db_admin.py check --db backups/scout-2026-11-02.sqlite3
python scripts/db_admin.py restore `
  --backup backups/scout-2026-11-02.sqlite3 `
  --db data/scout-restored.sqlite3
```

To replace the live DB, stop the app first and use `--force` only after a
verified backup exists.

## Consistency check

```powershell
python scripts/db_consistency.py --db data/scout.sqlite3
# {"issues": [], "count": 0}
```

Checks JSON payload vs duplicated columns and orphan rows; read-only.

See [db-migration-plan.md](db-migration-plan.md) for the FK/JSON rebuild design.

## Migrations

- `schema_version` records applied versions;
- migrations are sequential and idempotent;
- old databases are upgraded in place, existing rows are not deleted;
- `tests/test_schema_migrations.py` covers old-DB upgrade.

## Not done

- scheduled off-host backup (Render disk/object storage);
- automated restore drill in CI;
- point-in-time recovery (SQLite does not provide it).

## Snapshot fetch safety

Offline snapshot capture validates http(s), rejects private/loopback targets,
limits redirects, caps bodies at 500KB, and accepts only text content types.
