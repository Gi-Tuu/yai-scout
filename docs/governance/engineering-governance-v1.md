# YAI Scout — Engineering Governance v1.0

> Status: **adopted in branch `governance/engineering-v1` (not merged)**. 2026-11-01.
> Scope: `src/yai_scout/`, `benchmarks/`, `tests/`, `docs/`, `.github/workflows/`, deployment files.
> This document describes what the code **actually does**, not aspirations. Items marked `P1` are not implemented.

## 0. Why this exists

YAI Scout ships two independently testable entry points on one shared core. Without explicit contracts,
the benchmark can silently change with detector rules, hidden data can leak through public APIs,
and a "reproducible" run can become unreproducible after a config or weight change. Governance is
the set of enforced rules that makes experiment results auditable and product boundaries real.

## 1. Ten engineering principles

1. **Evidence over assumptions.** Claims about behavior require a test, a hash, or a recorded run.
2. **Contracts before implementations.** Public JSON, adapter protocol, dataset schema and manifest
   are versioned before internals change.
3. **Reproducibility by design.** Every run records the complete configuration that affects results.
4. **Immutable results.** Completed runs are append-only; revisions create new records with
   `supersedes`.
5. **Explicit dependencies.** Allowed dependency directions are listed; undeclared or cyclic imports
   are defects.
6. **Backward compatibility.** Existing APIs, SQLite rows and historical reports keep working or
   have a documented migration.
7. **Fail safely.** Missing evidence yields `INSUFFICIENT`, not a guessed verdict; failed adapters
   yield structured errors, not silent defaults.
8. **Security by default.** No secrets in manifests, logs, repos or prompt payloads. Hidden/private
   evaluation data is never served by public APIs.
9. **Test before promotion.** Lint + types + tests + Docker build pass before a change is proposed.
10. **Independent product governance.** Benchmark and Freshness can be
    deployed and evaluated independently; shared code lives in explicitly named modules.

## 2. A. Architecture governance

### 2.1 Layers and responsibilities

| Layer | Modules | Owns | Must not own |
|---|---|---|---|
| API | `api/app.py`, `web/static/*` | HTTP routing, validation, serialization, page serving, mode guards | scoring formulas, freshness decision logic, SQL |
| Application / orchestration | `pipeline/*`, `benchmark/runner.py`, `detector/service.py` | Use-case sequencing, concurrency, budgets, run lifecycle | vendor HTTP details, DOM parsing |
| Domain | `domain/models.py` | Pydantic models, invariants, status/version enums | I/O, SQL, HTTP, filesystem |
| Infrastructure | `store.py`, `retrieval/*`, `sources/*`, `llm.py`, `kernel/yai_adapter.py` | SQLite, Tavily, snapshots, model API, YAI integration | product ranking/scoring policy |
| Shared evaluation | `benchmark/scoring.py`, `benchmark/manifest.py`, `detector/freshness.py`, `detector/compare.py` | deterministic metrics, manifests, scoring rules | request handling |

### 2.2 Allowed dependency directions

```text
api            → application, domain, infrastructure, evaluation
application    → domain, infrastructure, evaluation
evaluation     → domain, infrastructure (read-only)
infrastructure → domain
domain         → (pydantic only)
```

Forbidden (checked by review until P1 automation exists):

- `domain` → any other `yai_scout` module; `domain` → sqlite/httpx.
- `detector/*` → `benchmark/*`.
- `benchmark/*` → `detector/*` except the explicit evaluation service interface
  (`detector.service.StaleAnswerDetector`, `detector.versions`). Current dependency is intentional
  and one-way.
- Product pages importing another product's internal page modules.

### 2.3 Product boundaries

- **Benchmark** owns: dataset, adapter registry/protocol, runner, leaderboard/Pareto,
  manifest, run immutability. Entry points: `/benchmark`, `/api/benchmark/*`.
- **Freshness** owns: claim extraction, temporal classification, verification, scoring,
  reports, inspector, compare. Entry points: `/freshness`, `/api/detector`, `/freshness/*`.
- Shared core: `domain`, `store`, `retrieval/tavily`, `sources`, `llm`, `detector.service` used by
  Benchmark only as an evaluator.
- Single-container mode guard (`SCOUT_MODE`) hides the other product's routes; it is a deployment
  boundary, not a security boundary.

### 2.4 YAI Agent Core adapter boundary

- YAI Agent Core is pinned as `yai-agent-core==0.25.0` (MIT). YAI Scout does **not** modify it.
- All YAI-specific calls live in `src/yai_scout/kernel/yai_adapter.py`; no other module imports
  `yai_core` directly. `tests/test_kernel.py` guards the adapter.
- YAI is optional at runtime: the freshness and benchmark paths work with rule-based fallbacks.

### 2.5 Known architecture debt (not fixed in this round)

- API handlers still contain some orchestration (report export, compare call); no separate
  application-service layer for Freshness.
- `benchmark/runner.py` knows detector/service details; acceptable one-way dependency, but a narrow
  `Evaluator` protocol would be cleaner (P1).
- No automated import-direction check in CI yet (P1).

## 3. B. Change governance

### 3.1 ADR mechanism

Every change that affects contracts, data meaning, scoring, or deployment requires an ADR in
`docs/adr/` using `docs/adr/TEMPLATE.md`. ADR fields are mandatory:

Context · Problem · Considered Options · Decision · Consequences · Migration Plan ·
Rollback Plan · Verification.

ADR status values: `proposed` → `accepted` → `superseded` (never deleted).

### 3.2 Change rules

- Branch + review; no direct push to `main`, no merge/release without owner approval.
- One concern per commit; tests in the same commit as the code they protect.
- Version bumps when semantics change:
  - dataset: `version` + `dataset_hash`;
  - freshness rules: `POLICY_VERSION` / `WEIGHTS_VERSION` in `detector/versions.py`;
  - scoring: `EVALUATOR_VERSION` in `benchmark/manifest.py`;
  - adapter protocol: `scout-adapter/x.y`.
- A change that alters scoring weights or ranking requires a new weights/evaluator version and a
  baseline comparison in the ADR.
- Secrets never enter commits, manifests, logs or screenshots.

## 4. C. Data governance

### 4.1 Datasets

- Public dataset: `benchmarks/tasks.json`, version string + `dataset_hash` computed over the
  selected task models (canonical JSON).
- `BenchmarkTask.hidden` is **not** a security boundary. The three existing hidden tasks were
  committed to public Git history and are marked `compromised: true`. Do not describe them as
  secret.
- Private evaluation data must live outside this repository (or in a git-ignored directory) and is
  loaded only through `load_private_dataset(path)`; public APIs never expose it.

### 4.2 Gold standard and scoring

- `gold_values` / `gold_sources` are part of the public dataset; changes change `dataset_hash` and
  must be recorded in an ADR/CHANGELOG.
- `evidence_metrics.stable_fact_integrity` counts only claims with
  `temporal_sensitivity == STABLE`, joined by `claim_id`; it returns `null` when no stable claim is
  evaluable.

### 4.3 Snapshots and provenance

- Snapshots store URL, origin, content hash, publication/fetch timestamps and text path.
- Origins: `wayback`, `manual`, `official_history`, `live`. Only dated snapshots participate in
  replay; undated snapshots are excluded.
- Historical web snapshots require a real archive or a manually saved page; fabricated history is
  prohibited.
- Snapshot bundle `benchmarks/snapshots.json` is seeded at startup for stateless deployments.

### 4.4 Historical results

- `bench_session` rows are append-only after completion; config hash cannot be rewritten;
  revisions create a new session with `supersedes`.
- `bench_result` rows are insert-only.
- Detector reports are stored as JSON; legacy reports missing version fields load as
  `policy_version=unknown`, `weights_version=unknown` and are never rewritten on read.

### 4.5 Backup / restore (P1)

No automated backup exists. Until P1: copy `data/scout.sqlite3` while the service is stopped, or use
`sqlite3 .backup`. Exported snapshot JSON (`scripts/export_snapshots.py`) is the portable evidence
copy.

## 5. D. Experiment lifecycle

```text
create → running → done/failed → export → reproduce → (revise → new run with supersedes)
```

- **Create**: `BenchmarkRunner.start()` builds an `ExperimentManifest`, computes `config_hash`,
  writes the session and manifest before any task runs.
- **Run**: each `TaskResult` carries metrics, cost, tokens and error; detector failures are isolated.
- **Finish**: `result_hash` is computed from the stored results and written once; status flips to
  `done`/`failed`; further mutation is rejected.
- **Export/reproduce**: the manifest contains dataset version/hash, selected task IDs, agent
  manifests, model and protocol versions, tool/retrieval/budget/timeout config, evaluator/policy/
  weights/prompt versions, code commit, lock hash and snapshot IDs. `code_commit` and lock hash make
  the software state auditable.
- **Revision**: a new session must reference the old one via `supersedes`; old results stay intact.
- **Verification**: `GET /benchmark/runs/{id}/verify` recomputes `result_hash` and reports a match.

Limits: `result_hash` covers answer text, citations, metrics and scores, **not** the full detector
evidence graph. Full evidence-level replay is P1.

## 6. E. Quality governance

### 6.1 Test levels (current)

| Level | Examples | Status |
|---|---|---|
| Unit | scoring, freshness decision table, temporal classifier, manifest hashing | present |
| Contract | adapter protocol validation, HTTP/Python/CLI adapters | present |
| API | TestClient endpoints, mode guard, hidden isolation | present |
| Persistence | SQLite roundtrip, legacy schema migration, immutability | present |
| Replay | snapshot search, as-of filtering, GitHub-history replay | present |
| Regression | benchmark runner, freshness service, dual-mode startup | present |
| Concurrency | runner concurrency; no stress tests | partial |
| Cross-product | separate entry points and mode guard | present |
| Docker | image build in CI | present |

### 6.2 CI gates

Required for any proposed change:

```bash
uv run ruff check src tests scripts examples
uv run mypy
uv run pytest -q
docker build -t yai-scout:governance .
```

CI matrix: Python 3.11 and 3.12 (test job), Docker build job. A change is not "done" if any gate is
skipped or a test is weakened.

### 6.3 Release requirements

- Changelog entry + version bump.
- All gates green.
- No known P0 governance defect open.
- Deployment smoke (`scripts/smoke_online.py`) when the public demo is updated.

## 7. Enforcement map

| Principle | Mechanism today | Automation gap |
|---|---|---|
| Evidence over assumptions | tests + hashes | review only |
| Contracts first | protocol validators, schema models | no schema version table |
| Reproducibility | manifest + config_hash + lock hash | full package freeze missing |
| Immutable results | DB guards + result_hash | no DB triggers |
| Explicit dependencies | review | no import-linter |
| Backward compatibility | legacy parsing tests | no formal API versioning |
| Fail safely | INSUFFICIENT, structured errors | no chaos tests |
| Security by default | redaction + no secrets in repo | no secret scanning in CI |
| Test before promotion | CI gates | branch protection depends on owner |
| Independent products | `SCOUT_MODE`, separate deps | shared DB file by default |

## 8. Revision history

- v1.0 (2026-11-01): initial adoption, accompanies ADR-0003 and P0 hardening.
