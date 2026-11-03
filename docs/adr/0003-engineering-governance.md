# ADR-0003 — Engineering Governance v1.0 and P0 Hardening

- Status: accepted (branch `governance/engineering-v1`, not merged)
- Date: 2026-11-01
- Owners: YAI Scout maintainers

## Context

YAI Scout contains two independently testable entry points (Benchmark / Freshness) sharing one evidence
core. A read-only audit before this ADR found reproducibility, isolation and version-consistency
defects:

- Benchmark `config_hash` covered only agent IDs, task IDs, dataset version and target times.
- Runs had no result hash, no manifest, no revision link, and completed sessions could be updated.
- Hidden tasks were committed to public Git history and `include_hidden=true` bypassed API
  filtering; the runner accepted hidden task IDs without a private context.
- `stable_fact_integrity` counted all FRESH/STALE/CONFLICTED verdicts, not only STABLE claims.
- `DetectorReport` defaulted to `weights_version="rubric-v1"` while the detector executed
  `rubric-v2-calibrated`.
- `requires-python = ">=3.11"` disagreed with CI/Docker/Ruff (3.12) and one PEP 695 generic made
  the code fail to import on 3.11.

## Problem

Without enforced contracts, experiment results cannot be reproduced or trusted, hidden evaluation
data cannot be protected, and product boundaries can erode. Documentation alone does not prevent
regressions.

## Considered options

1. **Do nothing** — unacceptable: results remain non-reproducible and hidden data is already
   compromised.
2. **Documentation-only governance** — cheap, but no enforcement; defects recur.
3. **Full architectural rewrite** — high risk, violates the "no large rewrite" constraint.
4. **Incremental governance + targeted P0 controls (chosen)** — versioned docs, ADR process, and
   small, testable changes to manifest, isolation, scoring, versions, Python support and run
   immutability.

## Decision

Adopt Engineering Governance v1.0 and implement P0 controls:

- **P0-1**: `ExperimentManifest` with canonical JSON hashing, secret redaction (sha256
  fingerprints), dataset/agent/model/tool/budget/timeout/evaluator/policy/weights/code/lock/
  snapshot fields; stored at run creation; `result_hash` computed at completion.
- **P0-2**: public loaders/API return only non-hidden tasks; `include_hidden` removed; runner
  rejects hidden IDs unless an explicit private `allow_hidden=True` context is used; existing
  hidden tasks marked `compromised`; private datasets live outside the public repo.
- **P0-3**: `stable_fact_integrity` filtered by `TemporalSensitivity.STABLE` and joined by
  `claim_id`; `null` when no stable claim is evaluable.
- **P0-4**: single version source `detector/versions.py`; `DetectorReport` defaults to `unknown`
  for historical rows; new reports always record executed versions.
- **P0-5**: support Python 3.11 and 3.12; remove the single PEP 695 generic; set Ruff/Mypy to 3.11;
  CI matrix 3.11/3.12; Docker stays 3.12.
- **P0-6**: append-only lifecycle after completion, `result_hash` stored once, config hash
  immutable, `supersedes` for revisions, legacy SQLite migration (add columns only),
  `/benchmark/runs/{id}/verify` recomputation.

## Consequences

Positive:

- A run can be audited from manifest + hashes; config changes are visible.
- Public APIs cannot read or execute hidden tasks; compromise is documented honestly.
- Metrics match their definitions; version drift becomes a test failure.
- Python support is truthful and tested on both versions.
- Historical data remains readable; no destructive migration.

Negative / trade-offs:

- API response changes: `include_hidden` query parameter removed (security fix); clients must use
  the public dataset.
- Older reports and sessions show `unknown`/no manifest rather than fabricated values.
- Manifest `code_commit` falls back to `unknown` in environments without Git metadata; the public
  demo (Render) does not inject a commit, so the build marker may be `dev`/`unknown` until CI sets
  `GIT_COMMIT`.
- `result_hash` does not include the full evidence graph; a future evaluator version will extend it.
- Hidden replacement questions are **not** added in this round (private data must not enter the
  public repo).

## Migration plan

1. No destructive migration: `bench_session` gains `manifest_json`, `result_hash`, `supersedes`
   via `ALTER TABLE` only when missing (`Store._ensure_bench_columns`).
2. Old rows parse with defaults (`manifest=None`, `result_hash=None`); old detector reports keep
   stored versions, missing fields load as `unknown`.
3. New runs use the new manifest; no backfill of historical runs (would fabricate evidence).
4. API clients that sent `include_hidden=true` now receive the public dataset only; this is
   intentional and documented.

## Rollback plan

- Revert this branch's commits; schema columns are additive and harmless to the old code.
- Existing rows written with `manifest_json`/`result_hash` remain readable by old code because it
  selects only `config_json`/`status`/`finished_at`/`error`.
- If the Python 3.11 support causes issues, revert the PEP 695 rewrite and set
  `requires-python >=3.12` in a follow-up ADR; do not leave a false claim.
- No data deletion is part of this change.

## Verification

```bash
uv run ruff check src tests scripts examples
uv run mypy
uv run pytest -q            # 3.11 and 3.12 venvs
docker build -t yai-scout:governance .
```

Specific tests: `tests/test_governance.py` (manifest determinism/sensitivity/redaction, hidden
isolation, stable integrity, version consistency, legacy migration, immutability, private execution,
supersedes), `tests/test_benchmark.py` (runner manifest/result hash).

Manual API smoke: `GET /api/benchmark/tasks` contains no hidden IDs;
`POST /api/benchmark/run` with a hidden ID returns 400;
`GET /benchmark/runs/{id}/verify` matches after a run.
