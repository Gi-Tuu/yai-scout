# Open Tasks

> Snapshot: 2026-11-04 · release `v0.4.1` · 316 tests · Python 3.12 local verification

## DONE

| Task | Evidence |
|---|---|
| Typed claim identity (v1/v2) | `claim_keys.py`, `claim_classification.py`, `Anchor.claim_type`, migration 8 |
| Claim identity dual-read | `detector/service.py`; tests `test_claim_identity_integration.py` |
| Drift diff v2 grouping | `detector/compare.py`; list grouping prevents duplicate-key loss; `test_compare_identity.py` |
| Full-page provenance | `sources/page.py` merge preserves Tavily publication metadata; `test_evidence_provenance.py` |
| Full-page security boundary | allowlist, pinned IP, Host/SNI, size/time caps; code default off, public deployment opt-in |
| Snapshot search pagination | `list_snapshots_page`, `list_snapshots_for_url_page` |
| WAL-safe FK migrator | `scripts/migrate_fk.py` uses SQLite backup API |
| FK enforcement | fresh `SCHEMA` FKs; `PRAGMA foreign_keys=ON` after migrations |
| Benchmark run auth | `BENCHMARK_RUN_REQUIRES_ADMIN` default true |
| Revalidation async I/O | `detector/revalidate.py` uses `asyncio.to_thread` |
| Coverage gate | `fail_under = 80`; current documented coverage above threshold |
| Public benchmark cost guard | public synthetic runs force `detect_freshness=false`; no Tavily/LLM fan-out |
| Benchmark reliability | repeated runs, deterministic failure injection, step/tool traces, std/success/fault stats |
| Benchmark dataset | 40 tasks (37 public + 3 compromised) across four freshness categories |
| Full-page production rollout | public deployment enabled with explicit allowlist; live `fetched_page` evidence verified |
| Live benchmark verification | `freshness-bench/0.3.0`; 37 public tasks exposed, full public run completed 37/37 |
| Freshness verdict evaluation | 50 fixed claim/evidence cases (standard/adversarial/ambiguous); precision/recall/confusion |
| Private verdict labeling bridge | accuracy-gate private cases → unlabeled verdict worksheet → local labels → evaluator |
| Holdout v2 worksheet | 60 unlabeled cases from separate accuracy-gate worksheet; human status labels only |
| Holdout v3 worksheet | 60 balanced unlabeled cases (15 fresh/stale/conflicted/insufficient), 60 unique claims, not derived from the public compromised key |
| Retention observability | startup result exposed; failures logged and reported as generic `retention_failed` |
| Rate-limit bucket sweep | stale per-client buckets removed after 60s |
| Browser CI | pinned Playwright 1.64.1 admin rollback/approve smoke job |
| Automatic benchmark retention | opt-in `BENCHMARK_RETENTION_DAYS`, startup prune, default off |
| Benchmark retention | migration 9 unique cell index; explicit prune CLI with dry-run and pre-delete JSON audit |
| Benchmark failure aggregation | gather waits for siblings and reports all cell failures before failing the session |

## IN PROGRESS

| Task | Notes |
|---|---|
| Migration 8 validation in more real databases | local DB reports schema versions 1–8 and 0 consistency issues; add fixture coverage as databases appear |

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
