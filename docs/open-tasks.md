# Open Tasks

> Snapshot: 2026-11-03 · release `v0.3.6` · 262 tests · Python 3.12 local verification

## DONE

| Task | Evidence |
|---|---|
| Typed claim identity (v1/v2) | `claim_keys.py`, `claim_classification.py`, `Anchor.claim_type`, migration 8 |
| Claim identity dual-read | `detector/service.py`; tests `test_claim_identity_integration.py` |
| Drift diff v2 grouping | `detector/compare.py`; list grouping prevents duplicate-key loss; `test_compare_identity.py` |
| Full-page provenance | `sources/page.py` merge preserves Tavily publication metadata; `test_evidence_provenance.py` |
| Full-page security boundary | allowlist, pinned IP, Host/SNI, size/time caps; default off |
| Snapshot search pagination | `list_snapshots_page`, `list_snapshots_for_url_page` |
| WAL-safe FK migrator | `scripts/migrate_fk.py` uses SQLite backup API |
| FK enforcement | fresh `SCHEMA` FKs; `PRAGMA foreign_keys=ON` after migrations |
| Benchmark run auth | `BENCHMARK_RUN_REQUIRES_ADMIN` default true |
| Revalidation async I/O | `detector/revalidate.py` uses `asyncio.to_thread` |
| Coverage gate | `fail_under = 80`; current documented coverage above threshold |

## IN PROGRESS

| Task | Notes |
|---|---|
| Migration 8 validation in more real databases | local DB reports schema versions 1–8 and 0 consistency issues; add fixture coverage as databases appear |
| CI dual-Python verification | CI remains the authority for 3.11 + 3.12; local runtime is 3.12 |

## BLOCKED

| Task | Blocker |
|---|---|
| Independent human accuracy metrics | no valid independent labels; do not treat rule-following labels as ground truth |
| Durable production SQLite | current deployment filesystem is ephemeral; needs persistent storage before a real migration switch |

## DEFERRED

| Task | Reason |
|---|---|
| Full async SQLite layer | write contention is not currently the bottleneck; large refactor |
| PostgreSQL migration | no operational requirement yet; changes storage architecture |
| FK/JSON full normalization | hybrid payload + indexed columns is intentional; high-risk rewrite |
| Public Bifrost deployment | optional; local gateway path is verified |
| Full-page fetch rollout | default off; needs an explicit allowlist and cost review |
| Benchmark expansion | current 24-task suite is evaluation tooling, not a leaderboard |

## Evidence commands

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check src tests scripts examples
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe scripts\check_imports.py
.\.venv\Scripts\python.exe scripts\db_consistency.py --db data\scout.sqlite3
```

## Out of scope

- Automatic overwrite of the original answer (`AUTO_UPDATE` stays off).
- Claiming independent human ground truth.
- Treating the benchmark as a universal accuracy leaderboard.
- Expanding scrape permissions or disabling SSRF/size protections.
