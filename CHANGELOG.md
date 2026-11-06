# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Pre-1.0 versions are previews; APIs may change.

## [Unreleased]

### Planned

- 60 human-scored claims for freshness calibration (current: 20 rule-labelled).
- Real web-archive snapshots (Wayback or manual HTML) for pricing/leaderboard facts.
- API rate limiting and cost protection for the public demo (P1 R1/R3).
- More agent adapters (framework wrappers) and larger benchmark dataset.
- Independent accuracy calibration and a stable label-adjudication workflow.

## [0.7.15] - 2026-11-06

### Fixed

- Unmeasured freshness no longer receives full credit in benchmark scoring.
- Numeric benchmark matching now respects currency/credit/period units.
- Repeated benchmark runs retain per-sample score/latency/cost/error and average
  valid samples rather than selecting the highest-scoring sample.
- `pypi.org` is classified as an authoritative package-index source (T2), so
  official PyPI snapshots can support FRESH/STALE replay verdicts.
- Added regression tests for scoring, repeat aggregation and PyPI tiering.

## [0.7.14] - 2026-11-05

### Fixed

- Only GitHub release pages are grouped by owner/repo. Issues, discussions and
  README pages are URL-keyed, so a same-repo issue cannot replace a release-page
  contradiction.

## [0.7.13] - 2026-11-05

### Fixed

- Version evidence now groups GitHub release URLs by owner/repo rather than by
  host; different repositories on github.com are not merged.
- Same-timestamp support/contradict evidence is retained together, making
  CONFLICTED independent of input order.
- Non-GitHub version evidence uses the full URL as a conservative source key.

## [0.7.12] - 2026-11-05

### Fixed

- Live requests without `as_of` freeze the actual UTC request timestamp instead
  of using a date that includes future same-day evidence.
- Replay search and anchor retrieval use the same end-of-day UTC semantics for
  date-only `as_of` as scoring.
- Version evidence selects the newest release per source; cross-source
  authoritative support/contradiction is retained and can yield CONFLICTED.

## [0.7.11] - 2026-11-05

### Fixed

- Date-only `as_of` now means end-of-day UTC, so same-day evidence is no longer
  excluded as future.
- Replay snapshot eligibility now respects origin: official history/Wayback use
  publication time; live/manual captures require fetched/updated time no later
  than the target.
- Low-authority version mentions no longer displace older authoritative
  supports/contradictions.
- Search failure preserves successfully fetched anchor evidence.
- External benchmark mixed count documentation is 9 cases.

## [0.7.10] - 2026-11-05

### Fixed

- External benchmark snapshot paths are normalized to POSIX separators in
  committed JSONL and builders. This fixes Linux CI/fresh-checkout ablation runs
  that previously treated Windows backslashes as literal filename characters.

## [0.7.9] - 2026-11-05

### Fixed

- Committed external-v2 mixed snapshot files (previously ignored by the global
  `snapshots/` rule), so CI and fresh checkouts can run mixed ablations.

## [0.7.8] - 2026-11-05

### Fixed

- Ablation harness derives its evidence root from the data file, so it works on
  external-v2 mixed data.
- Mixed builder now writes `mixed_manifest.json` and no longer emits hardcoded
  stable-page publication dates.
- Public benchmark agents response hides the configured HTTP adapter endpoint;
  admin still sees it.
- SSE response releases its stream slot via background task; limiter release is
  idempotent.
- Benchmark detector concurrency gate is shared across sessions on the same
  event loop.

## [0.7.7] - 2026-11-05

### External benchmark

- Added an 11-case cross-source mechanical smoke set: PyPI/GitHub conflict,
  no-evidence insufficient, semantic unknown and official stable controls.
- Added mixed manifest/summary and builder.
- Documents the smoke as a gap detector, not L2/L3 evidence.

## [0.7.6] - 2026-11-05

### External benchmark

- Added deterministic ablation harness and ablation summary.
- Added McNemar exact test to paired comparison.
- Added per-status, per-source-family and per-claim-type scoring.
- Added a labeler packet generator with no gold labels.
- Added L1 test/ablation tests. All results remain mechanical holdout, not
  independent test evidence.

## [0.7.5] - 2026-11-05

### External benchmark

- Added `external-v2` protocol and L1 mechanical-holdout tooling.
- Renamed the old sealed directory to `mechanical_holdout` and stopped calling
  it a blind/independent test.
- Added `check_external_labels.py` for independent labeler A/B validation and
  kappa.
- Added L1 test-summary with paired primary comparison.
- No independent L2 labels or kappa are claimed.

## [0.7.4] - 2026-11-05

### Fixed

- Benchmark runs now enforce a detector concurrency budget independent of the
  adapter semaphore.
- Snapshot text paths are stored relative to the DB directory when possible and
  resolved on replay/search, so moving the data directory keeps replay working.
- LLM relation, claim extraction and benchmark RAG prompts mark source text as
  untrusted data and explicitly instruct the model not to follow instructions
  inside it.

## [0.7.3] - 2026-11-05

### Fixed

- Public benchmark task API no longer exposes gold values, expected claims or
  reference evidence.
- Unknown benchmark agent IDs are rejected instead of silently dropped.
- Candidate approval returns 409 when another request already decided it.
- Legacy ownerless rows are admin-only; session lists no longer leak them.
- SSE streams are capped per task and globally.
- Importing `api.app` no longer creates the default app/database.
- `Database.write()` rolls back on exceptions.
- Proxy headers are ignored unless `TRUST_PROXY_HEADERS` is enabled.
- Debug endpoint redacts authorization/cookie headers.

### External benchmark

- Added `protocol.json` with `citation_only` as the frozen primary baseline.
- Added paired bootstrap delta comparison (`compare_external_eval.py`).
- Corrected docs so `llm_only` is secondary/exploratory.
- Test candidate remains mechanical, sealed and not independent.

## [0.7.2] - 2026-11-05

### Added

- 182-case mechanically-labelled external test candidate (`test.jsonl`) with
  git-ignored sealed labels and recorded hashes.
- `compute_agreement.py` for Cohen's kappa and a synthetic test. Real kappa
  still requires two independent annotators.
- Blind/labelled loading support in the external runner.

## [0.7.1] - 2026-11-05

### Added

- `llm_only` and `retrieval_only` external baselines.
- Current-value accuracy on STALE rows.
- Dev result: full system does not meet the pre-registered +0.10 advantage over
  LLM-only; recorded as a negative result.

## [0.7.0] - 2026-11-05

### Added

- External Track A dev set from official PyPI release timestamps
  (`benchmarks/external_v1`, 56 cases, frozen snapshots).
- `build_external_set.py`, `run_external_eval.py` and
  `score_external_eval.py` with always-fresh, recency-only, citation-only and
  full-system baselines.
- Pre-registration and dev-results docs. No sealed external test labels yet.

## [0.6.1] - 2026-11-04

### Tests

- Added an AST boundary test ensuring `detector/relation` does not import
  `verify`, `store` or `api`.

## [0.6.0] - 2026-11-04

### Changed

- Split `verify.py` into orchestration (`verify.py`, `verify_steps.py`) and pure
  relation modules (`relation/`), plus `query.py`, `evidence.py` and
  `llm_relation.py`.
- `_relation`, `_to_evidence`, `_llm_relation` and `build_query` remain
  compatible proxies.
- Added direct relation classifier tests.

## [0.5.2] - 2026-11-04

### Changed

- Schema initialization uses `Database.ddl()`; migrations run in one
  `Database.atomic()` scope.
- Pre-v10 backup uses a separate source connection, so it captures committed
  pre-migration state without committing the migration transaction.

## [0.5.1] - 2026-11-04

### Changed

- Storage repositories now use `Database.read()` / `write()` / `atomic()`
  contexts for SQL access instead of duplicating lock/commit handling.
- Transactional methods remain explicit atomic scopes.

## [0.5.0] - 2026-11-04

### Changed

- Split the 1865-line `store.py` into a `Store` facade plus `storage/`
  repositories, migrations, schema, row mappers, consistency and maintenance.
  Public `Store` method signatures and storage semantics are unchanged.
- Added a dependency boundary for `storage`: it may depend on `domain` and
  storage internals only.

### Tests

- Added an AST boundary test preventing `storage` from importing `store` or
  upper layers.
- Full suite remains green.

## [0.4.5] - 2026-11-04

### Added

- Local staging load harness: `scripts/staging_server.py` uses a separate DB,
  packaged snapshots and deterministic Fake Tavily.
- k6 scenario `load/k6-fixed-cases.js` and `docs/staging-load-test.md` record
  local HTTP p50/p95/p99, error rate and RPS.
- Calibration sorting regression test.

## [0.4.4] - 2026-11-04

### Fixed

- `scripts/eval_freshness.py --calibrate` now sorts weight candidates by
  accuracy and MAE without comparing dictionaries.

### Added

- `scripts/perf_smoke.py` and `docs/performance-smoke.md` for deterministic
  scorer P50/P95/P99 measurements. This is a local microbenchmark, not a
  long-run HTTP/DB load test.

## [0.4.3] - 2026-11-04

### Fixed

- Stable historical release claims (for example `Python 3.12 于 2023 年发布`)
  are supported by version/date tables and are no longer contradicted by
  `latest` markers.
- Fixed demo cache is re-recorded; offline fixed-case tests cover replay and the
  stable live path without network calls.
- Freshness evaluation documentation now reports the measured 19/20 and MAE
  11.25, including the L16 decision-table explanation.
- Architecture documentation marks the monorepo split as planned; current code
  lives in `src/yai_scout`.
- README now has a concrete feedback/issues entry point.

## [0.4.2] - 2026-11-04

### Fixed

- Consistency checks handle non-object JSON payloads without crashing.
- Benchmark status has database-level insert/update triggers rejecting values
  outside `running`, `done`, `failed`.
- Pre-v10 migration backups are timestamped per attempt instead of reusing a
  stale fixed filename.

## [0.4.1] - 2026-11-04

### Fixed

- Corrupt `bench_session.config_json` / `manifest_json` now fails closed instead
  of returning a synthetic empty session.
- Consistency checks validate manifest schema and report invalid JSON/schema.
- Migration 10 creates a `.pre-v10.bak` SQLite backup before rewriting session
  JSON.
- Generic version claims without project identity no longer borrow another
  project's release as a contradiction.

## [0.4.0] - 2026-11-04

### Changed

- Benchmark session lifecycle has a single source of truth: database columns.
  `config_json` is configuration-only; `manifest_json` is manifest-only; status,
  timestamps, error and result hash are composed from columns on read.
- Migration 10 normalizes legacy session JSON and backfills nested manifests.

### Added

- Consistency reporting rejects lifecycle fields embedded in config/manifest JSON.
- Regression tests for create/update/interrupt and legacy migration.

## [0.3.7] - 2026-11-04

### Fixed

- Release-version relation now requires project identity overlap, preventing
  another project's release URL from producing a false STALE verdict.
- Benchmark prune audits are retained for a bounded number of days
  (`--audit-keep-days`, default 30).

## [0.3.6] - 2026-11-04

### Fixed (deep audit)

- Replay: newer explicit release URL now contradicts a "current version" claim;
  version comparison is numeric, not lexical.
- Citation-only URL sentences no longer become standalone claims.
- Benchmark sibling failures are aggregated before terminal state; prune writes
  a pre-delete JSON audit and aborts deletion if the audit cannot be written.
- Client IP uses Cloudflare authoritative headers with documented deployment
  boundaries.
- Added balanced 60-case unlabeled holdout v3 and version consistency checks.

- P1-1: malformed upstream payload -> INSUFFICIENT, not 500; per-claim isolation.
- P1-2: URL scheme sanitization + CSP/security headers.
- P1-3: detector_report owner column/index and SQL owner filtering.
- P1-4: unreachable anchors are not marked as freshly checked.
- P2: invalid updated_at fallback; anchor status SQL filter/migration 4;
  URL-scoped snapshot replay; restart reconciliation for running work;
  core API SQLite calls offloaded with asyncio.to_thread;
  pytest-cov added; claim_key collision behavior documented in tests;
  benchmark sessions are owner-scoped (migration 5); admin candidate and
  benchmark read paths offloaded to worker threads; page/benchmark/research/
  freshness/admin routes moved to separate modules; JSON/column consistency
  checker + migration 6; snapshot search pagination; 80% coverage threshold;
  revalidation store I/O offloaded to worker threads; per-URL snapshot replay paginates;
  offline FK migration copy tool and validation; benchmark run admin gate;
  snapshot fetch SSRF/size hardening; FK constraints in fresh schema;
  typed claim identity with migration 8 and dual-read recall; full-page fetch
  provenance merge; WAL-safe migration copy and pinned snapshot fetch; claim
  identity/provenance integration tests; benchmark repeated runs, deterministic
  failure injection, step/tool traces, stability statistics, and public
  synthetic benchmark runs; dataset expanded from 24 to 40 tasks; public
  synthetic runs no longer fan out into detector/Tavily calls.

### Fixed

- P0-1: temporal eligibility (future/expired/unknown contradictions no longer become current STALE).
- P0-2: LLM aggregate assessment no longer overwrites evidence[0].
- P0-3: historical versions no longer support current-version claims.
- P0-4: gate requires known, non-future observation times; unknown time -> REVIEW.

### Added

- Coverage/abstention fields and versioned evidence receipt endpoint.
- Publication-date coverage / missing-date confidence.
- Drift diff: same-URL content hash, evidence kind and date changes.

### Added

- Private label quality checker (`scripts/check_label_quality.py`) and plain-language `/label` instructions; first private label batch reviewed and rejected as incomplete/inconsistent (`docs/eval-private-2026-11-02.md`).

### Fixed

- **P0-1**: app now uses the effective Bifrost/direct `llm_connection()`; healthz reports the actual client gateway/model; manifest records effective gateway/model + redacted fingerprint.
- **P0-2**: currency/unit/period-aware value normalization (`$` vs `€`, credits vs money, `/month` vs `/year`).
- **P0-4**: admin revalidation passes discovery + auto-update flag; API integration test.
- **P0-3**: public-suffix grouping, known GitHub publisher aliases, active-anchor guard, and transactional single-winner candidate approval.
- **P1-1**: research bucket/daily cap/active-task cap, wall-clock timeout, conservative credit reservation, `RESEARCH_ENABLED` switch.
- **P1-2**: session-scoped research/report ownership with admin bypass; public anchor writes require admin by default.
- **P1-3**: explicit live-fetch timeout and adversarial SSRF/DNS/redirect/content-type/size tests.
- **P1-4 tooling**: private 30-case worksheet (no answers in repo), `/label?worksheet=private`, worksheet evaluator, adjudication script; human labels pending.
- **P2 partial**: schema_version migrations, architecture import CI, pinned actions, Dependabot, CodeQL, offline backup/restore/integrity scripts.
- Fixed independent-label evaluator to compare human labels, not key; labeler 336 report in `docs/eval-336.md`.
- P0 freshness: old/undated authoritative support no longer FRESH; numeric relation checks versions, currencies, credits and periods; year regex/future-year classification fixed.
- P0 as_of/timestamp: live uses current date, replay requires explicit as_of, invalid as_of rejected, query year dynamic; published_at and retrieved_at separated for live/replay evidence.

## [0.3.5] - 2026-11-02

### Changed

- Offloaded read-only anchor/admin/healthz/compare SQLite calls via `asyncio.to_thread`; writes stay sync (minimal B4 mitigation).
- Concurrency smoke test for slow reads vs healthz.

## [0.3.4] - 2026-11-02

### Fixed

- `CachedDiscovery` LRU cache bound (`ANCHOR_DISCOVERY_CACHE_ENTRIES`, default 256); healthz reports `cache_size` (B6).
- Optional `ANCHOR_CREATE_ALLOWLIST`; anchor URLs with credentials rejected (B8).

## [0.3.3] - 2026-11-02

### Fixed

- Admin candidate creation dedupes `pending/rejected` candidates for the same anchor/normalized value/decision (B5).
- Rollback marks applied candidates `rolled_back`, writes `anchor_audit`, and exposes `GET /admin/anchors/audit` + `/admin` Audit table (B7).

## [0.3.2] - 2026-11-02

### Fixed

- Typed `CandidateEvidence` model for `AnchorCandidate.evidence` (B1).
- `AnchorCandidate.gate_decision` is now a Literal (B2).
- Live anchor fetch streams through `aiter_bytes`, caps at `LIVE_MAX_BYTES`, and closes the response (B3).

## [0.3.1] - 2026-11-02

### Fixed

- **Anchor evidence mapping**: unreachable first anchor no longer shifts `anchor_id`/`content_changed` onto a later anchor (verify.py explicit pairs).
- **Revalidation candidates**: gate `reject` results are saved as `rejected`, not `pending`; duplicate pending/rejected candidates are deduped.
- **Temporal sensitivity**: `POST /freshness/anchors` now persists `temporal_sensitivity`.
- **TTL loop**: added `Anchor.last_checked_at`; revalidation no longer keeps every anchor permanently due.
- **Independence**: primary and discovery observations share registrable-domain grouping; same publisher cannot masquerade as two sources.
- **Atomic replacement**: new anchor + supersede old in one transaction, avoiding two active anchors on crash.
- **Rate limit**: public anchor creation now uses the `anchor` bucket (`DAILY_ANCHOR_LIMIT`, default 30).
- **Live fetch**: `trust_env=False` prevents proxy env vars from bypassing pinned-IP SSRF protection.
- **API consistency**: candidate approve/auto-apply use the shared service; no divergent selection rules.
- **Indexes**: anchor observation/candidate indexes added after table creation.

### Docs

- `docs/audit-2026-11-02.md`: findings, fixes, open risks, data-model assessment.

## [0.3.0] - 2026-11-02

### Changed

- Positioned around one product: a freshness audit layer. The benchmark is supporting evaluation evidence.
- README documents the product model and the roles of Tavily, Bifrost, and the deterministic engine.

### Added

- **Bifrost AI Gateway integration**: `BIFROST_BASE_URL` / `BIFROST_API_KEY` / `BIFROST_MODEL`; all LLM requests route through Bifrost when configured; healthz reports `gateway`.
- Local Bifrost verification: real `/freshness/verify` routed through Bifrost, `POST /v1/chat/completions` 200, documented in `docs/bifrost-verification.md`; `scripts/verify_bifrost.py`.

### Fixed

- No-auth local Bifrost failed with `Illegal header value b''`; `Authorization` is now omitted when no key is set.

## [0.2.1-preview] - 2026-11-01

### Added

- Accuracy gate design (`docs/spec-accuracy-gate.md`), labeling protocol (`docs/accuracy-labeling-protocol.md`), and 30 labeled gate cases (`benchmarks/accuracy_gate/labeled_cases.json`, synthetic source metadata) covering auto_update/review/reject/no_change.
- Deterministic accuracy gate evaluator (`accuracy_gate.py`) + `scripts/eval_accuracy_gate.py`; v0 reports 30/30 agreement on rule-consistent labels (overfit caveat documented).
- Accuracy labels expanded to 60; gate agreement 1.000 on rule-consistent labels (independent human labels still pending).
- First human labeling result (labeler 001) and caveat: 60/60 matches hidden key, so it is rule-following not independent ground truth (`docs/accuracy-eval.md`).
- Blind labeling kit: 60-case worksheet, hidden key, `/label` UI, and `eval_accuracy_gate.py --labels` for independent human labels/false-update rate.
- Typed value-hint templates (price/credits, version, license, port, date, numeric) with ambiguity rejection.
- Cached/budgeted Tavily discovery (`ANCHOR_DISCOVERY_TTL_SECONDS`, `ANCHOR_DISCOVERY_DAILY_BUDGET`); healthz exposes usage.
- Multi-source discovery for changed anchors: revalidation now enriches observations via Tavily (2–3 sources) before gate evaluation.
- Rollback API + `/admin` UI: token-gated anchor/candidate tables, approve/reject and rollback.
- Real revalidation → candidate pipeline: changed anchor observations create candidates; single-source goes to review, auto-update flag remains off.
- Candidate persistence + admin API: create candidate from observations, list, approve/reject; auto-update feature flag (`ACCURACY_AUTO_UPDATE`, default off); supersedes/rollback-friendly anchor writes.

### Added (anchor)

- Anchor MVP: `Anchor` model + SQLite store, `POST/GET /freshness/anchors`, replay-only anchor evidence injected by claim key, and `anchor_id/anchor_status` on verdicts (scoring unchanged).
- Anchor hardening: content hash diff (`changed`), deterministic multi-anchor ordering, read-time TTL (`needs_revalidation`), and optional allowlisted live fetch (`ANCHOR_LIVE_FETCH`, default off; HTTPS-only, no redirects, public-IP checks, size/time limits).
- Anchor revalidation CLI + token-protected admin endpoint (external cron; observations only, never auto-overwrite).
- DNS rebinding mitigation: resolve once, connect to pinned public IP, preserve Host/SNI; conflict UI shows anchor evidence side-by-side without auto-resolution.
- Anchor-first retrieval design (`docs/spec-anchor-retrieval.md`) and a citation-vs-freshness demo case (`docs/demo-case-citation-vs-freshness.md`).
- `scripts/demo_citation_not_freshness.py` and `scripts/freshness_ci.py` (Freshness CI gate with configurable fail-on statuses).
- Tests for Freshness CI status filtering.

### Fixed

- Version claims now compare only the newest release timestamp, so two releases published the same day no longer produce a false CONFLICTED.

### Added (previous)

- Reproducibility regression test: same manifest + deterministic mock agents produce the same `config_hash` and `result_hash` in CI.
- Public-demo cost guard: global + per-IP per-minute limits and daily caps for detector/benchmark endpoints, with `429`/`Retry-After` and usage in `/api/healthz` (configurable; in-memory, resets on restart).

### Fixed

- Per-minute cap is enforced globally as well as per client, so rotating `X-Forwarded-For` cannot bypass it.

## [0.2.0-preview] - 2026-11-01

Engineering governance adoption and P0 hardening. No change to freshness scoring rules or
benchmark ranking weights.

### Added

- Engineering governance v1.0 (`docs/governance/engineering-governance-v1.md`), ADR-0003,
  P1 backlog and a read-only audit report.
- Experiment Manifest for benchmark runs: dataset/task hashes, agent manifests,
  model/protocol/tool/budget/timeout config, evaluator/policy/weights/prompt versions,
  code commit, dependency-lock hash, snapshot IDs, `config_hash` and `result_hash`.
- `GET /benchmark/runs/{id}/verify` to recompute and compare the stored result hash.
- `supersedes` revision link for benchmark sessions.
- Governance tests: manifest determinism/sensitivity/redaction, hidden isolation, stable metric,
  version consistency, legacy migration, immutability, private execution, revisions.
- Public demo deployment <https://yai-scout.onrender.com> with bundled snapshot replay and
  `scripts/smoke_online.py` (these landed after v0.1.0 and are included here).

### Changed

- Hidden tasks are marked `compromised` (they were committed to public history); public loaders/API
  no longer expose them and the insecure `include_hidden` parameter is removed.
- Freshness policy/weights versions now come from a single source (`detector/versions.py`);
  reports missing versions load as `unknown` instead of being silently assigned the current version.
- Python support is now truthful for 3.11 and 3.12 (PEP 695 generic removed, Ruff/Mypy target 3.11,
  CI matrix with both versions).
- Benchmark sessions are append-only after completion; config hash cannot be rewritten.
- Dataset version bumped to `freshness-bench/0.2.1` for compromised metadata; hidden task content
  is unchanged.

### Fixed

- `stable_fact_integrity` now counts only genuinely STABLE claims, joined by claim ID; returns
  `null` when no stable claim is evaluable.
- Benchmark manifests redact secrets with sha256 fingerprints (changes remain hash-sensitive,
  plaintext never stored).

### Security

- Hidden dataset isolation is enforced in both loader and runner; no public endpoint can execute
  hidden tasks.
- Credential fingerprints are recorded instead of keys; no secrets in manifests.

### Verification

- 93 tests on Python 3.11 and 3.12; ruff and mypy strict clean; Docker image builds.
- Real replay example unchanged: YAI `0.25.0` — STALE (24) at as_of 2026-10-28, FRESH (88) at
  as_of 2026-11-01.
- Render deploy `2e6ad02` served `snapshots=32` with build marker; latest release commit deployed
  after this changelog entry.

## [0.1.0-preview] - 2026-11-01

Initial preview: a benchmark and a freshness-audit detector sharing one evidence core.

### Added

- **Freshness pipeline**
  - LLM claim extraction (JSON mode) with exact-substring validation against the answer, plus rule-based fallback.
  - Temporal sensitivity classification: stable / slow / sensitive / volatile, with per-class validity windows and reasons.
  - Tavily live verification with supports / contradicts / mentions relations, authority tiers and timestamps.
  - Decision-table statuses `FRESH / STALE / CONFLICTED / INSUFFICIENT / UNKNOWN`, nullable score, confidence and score breakdown.
  - LLM relation review for law / leadership / date claims; correction suggestions for stale or insufficient claims.
- **Benchmark**
  - `scout-adapter/1.0` HTTP protocol (`GET /manifest`, `POST /run`) with request/response validation.
  - Python in-process and CLI subprocess adapters next to HTTP; reference agents (LLM RAG, retrieval baseline, synthetic).
  - 24-task dataset: 21 public + 3 hidden, across stable / time-sensitive / changed / conflicting categories.
  - Multi-dimensional leaderboard (accuracy, freshness, stale rate, evidence quality, claim coverage, cost, latency, tokens in/out).
  - Non-dominated Pareto frontier and reproducible `config_hash` per run.
- **Evidence & temporal tooling**
  - Evidence Inspector pages: claim → sources → timestamps → relation → score breakdown → suggestion.
  - Temporal drift comparison (`/compare`) with changed / new / removed / stable claims.
  - Snapshot store and capture scripts: Wayback probe, manual HTML import, GitHub Releases official history.
  - Replay mode (`mode=replay`) using only snapshots dated at or before the target time.
- **Deployment & quality**
  - Two-container deployment (`benchmark` / `freshness`) with `SCOUT_MODE` isolation; Dockerfile and compose verified.
  - GitHub Actions CI: ruff + mypy (strict) + pytest + Docker build.
  - MIT license, NOTICE with reused-component attribution (YAI Agent Core v0.25.0).
  - Project README, charters and technical specs.

### Changed

- YAI Agent Core pin recorded as `==0.25.0` with tag commit `614f3106...` (MIT, verified byte-for-byte against the tag).
- Freshness weights calibrated from rubric-v1 to **rubric-v2** (`relation 0.6 / recency 0.1 / authority 0.3`); score MAE 13.41 → 12.06 on the 20-claim set.
- Version claims compare only the newest release (older releases are history, not contradictions).

### Fixed

- Docker image pages returned 404 because `web/` resolved inside site-packages; switched to editable install.
- Version numbers were split (`0.25.0` → `0.25` + `0.0`) causing false support/contradiction matches.
- Unrelated snapshots (other projects) leaked into replay results; added URL/keyword relevance gates and excluded undated snapshots.
- Legacy detector reports with `uncertain` / `unverifiable` statuses are mapped to `insufficient` when read.

### Security

- API keys are read from `.env` (git-ignored); no keys are committed or served. Remote `/.env` returns 404.
- Snapshot text is stored for audit only; no paywalled content or personal data.

### Verification

- 73 tests, ruff clean, mypy strict clean.
- Real replay example: YAI `0.25.0` — **STALE (24) at as_of 2026-10-28**, **FRESH (88) at as_of 2026-11-01**.
- CI run on the release commit: success (test + docker).

[Unreleased]: https://github.com/Gi-Tuu/yai-scout/compare/v0.2.0-preview...HEAD
[0.2.0-preview]: https://github.com/Gi-Tuu/yai-scout/releases/tag/v0.2.0-preview
[0.1.0-preview]: https://github.com/Gi-Tuu/yai-scout/releases/tag/v0.1.0-preview





















