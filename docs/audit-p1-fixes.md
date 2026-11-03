# P1 Audit Fixes — 2026-11-02

Follow-up to the deep review. Scope: confirmed P1 issues only.

## P1-1 Upstream malformed payload no longer becomes HTTP 500

- `TavilyClient.search` converts malformed JSON into `TavilyError`.
- `ClaimVerifier.verify` treats any search-time exception as `INSUFFICIENT`.
- `StaleAnswerDetector` isolates each claim and each suggestion call.

Tests:

- `tests/test_robustness.py::test_tavily_malformed_json_becomes_tavily_error`
- `tests/test_robustness.py::test_one_claim_failure_becomes_insufficient_not_500`

## P1-2 URL sanitization and security headers

- All external evidence/source links use a `safeUrl()` helper that only allows
  `http:` / `https:`.
- Titles and domains are HTML-escaped before `innerHTML`.
- Added `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, and a
  restrictive CSP for the web UI.

Tests:

- `tests/test_api.py` header assertions.

## P1-3 Ownership filtering moved into SQL

- `detector_report` now has `owner_id` + index (migration 3).
- `research_task.owner_id` gets an owner/created index.
- `list_detector_reports` and `list_tasks` accept `owner_id` and filter before
  `LIMIT`, so another session's rows cannot crowd out yours.
- Legacy rows with `owner_id=""` remain public demo data.
- Migration 3 is idempotent and safe on existing `detector_report` tables.

Tests:

- `tests/test_ownership.py::test_owner_reports_are_not_crowded_out_by_other_sessions`
- `tests/test_schema_migrations.py` version list `[1, 2, 3]`

## P1-4 Unreachable anchors are not marked as checked

- `revalidate_anchor` updates `last_checked_at` only for `verified` / `changed`.
- An `unreachable` result remains due and is retried, instead of being suppressed
  by the sensitivity TTL.

Tests:

- `tests/test_revalidate.py::test_unreachable_anchor_is_not_marked_freshly_checked`

## P2 follow-up fixes

- Invalid `updated_at` now falls back to `published_at` (freshness.py).
- `anchor.status` is a SQL column with a status/created index (migration 4);
  active filtering happens before `LIMIT`.
- Snapshots are queried by URL (`list_snapshots_for_url`) so replay does not
  depend on the latest 1000 global rows.
- Startup reconciles `pending`/`running` research tasks and `running`
  benchmark sessions as failed after a process restart.
- Core API paths (detector, research, report reads/writes, anchor reads/writes)
  now offload SQLite calls with `asyncio.to_thread`.
- CI now runs `pytest-cov`; baseline is **86%** line coverage.
- `claim_key` collision tests document the known period/quarter merge; the
  key is kept unchanged for backward compatibility with existing anchors.
- Benchmark sessions now carry `owner_id` (migration 5); run/session/verify/
  leaderboard endpoints are session-scoped, with admin bypass.

## JSON/column consistency

- `Store.consistency_report()` checks anchor/candidate/report/benchmark
  payload-vs-column drift and orphan rows.
- `scripts/db_consistency.py --db ...` exits non-zero on issues.
- Bench lifecycle updates now keep `config_json` in sync; migration 6
  backfills legacy sessions.
- Snapshot search paginates instead of silently stopping at 500 rows.
- Coverage has a CI threshold (`fail_under = 80`; current 86%).

## Verification

```text
pytest      : 223 passed
ruff        : pass
mypy        : pass (50 files)
architecture: ok
Docker      : built
```

## Still open (P2)

- no FK constraints / duplicated JSON columns;
- Page, benchmark, research, freshness and admin routes are now in separate
  modules (`api/pages.py`, `api/benchmark_routes.py`, `api/research_routes.py`,
  `api/freshness_routes.py`, `api/admin_routes.py`); `api/app.py` is wiring/health.
  The revalidation pipeline still uses sync SQLite internally.
- `claim_key` numeric normalization can merge distinct facts;
- no line-coverage tool installed;
- benchmark endpoints are session-scoped but still have no separate api-key auth.
