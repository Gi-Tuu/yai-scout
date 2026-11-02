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

## Verification

```text
pytest      : 208 passed
ruff        : pass
mypy        : pass (50 files)
architecture: ok
Docker      : built
```

## Still open (P2)

- status filters still happen after SQL `LIMIT` for anchors;
- snapshot replay has 1000-row caps;
- no FK constraints / duplicated JSON columns;
- monolithic API and sync SQLite calls in async handlers;
- `updated_at` invalid value does not fall back to `published_at`;
- `claim_key` numeric normalization can merge distinct facts;
- running tasks/benchmarks are not reconciled after restart;
- no line-coverage tool installed;
- benchmark endpoints have no owner/auth model (supporting only).
