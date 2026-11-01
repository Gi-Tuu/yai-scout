# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Pre-1.0 versions are hackathon previews; APIs may change.

## [Unreleased]

### Planned

- 60 human-scored claims for freshness calibration (current: 20 rule-labelled).
- Real web-archive snapshots (Wayback or manual HTML) for pricing/leaderboard facts.
- API rate limiting and cost protection for the public demo (P1 R1/R3).
- More agent adapters (framework wrappers) and larger benchmark dataset.
- Final submission package: two project READMEs, slides, demo video.

## [0.2.1-hackathon] - 2026-11-01

### Added

- Accuracy gate design (`docs/spec-accuracy-gate.md`), labeling protocol (`docs/accuracy-labeling-protocol.md`), and 30 labeled gate cases (`benchmarks/accuracy_gate/labeled_cases.json`, synthetic source metadata) covering auto_update/review/reject/no_change.
- Deterministic accuracy gate evaluator (`accuracy_gate.py`) + `scripts/eval_accuracy_gate.py`; v0 reports 30/30 agreement on rule-consistent labels (overfit caveat documented).
- Candidate persistence + admin API: create candidate from observations, list, approve/reject; auto-update feature flag (`ACCURACY_AUTO_UPDATE`, default off); supersedes/rollback-friendly anchor writes.

### Added (anchor)

- Anchor MVP: `Anchor` model + SQLite store, `POST/GET /freshness/anchors`, replay-only anchor evidence injected by claim key, and `anchor_id/anchor_status` on verdicts (scoring unchanged).
- Anchor hardening: content hash diff (`changed`), deterministic multi-anchor ordering, read-time TTL (`needs_revalidation`), and optional allowlisted live fetch (`ANCHOR_LIVE_FETCH`, default off; HTTPS-only, no redirects, public-IP checks, size/time limits).
- Anchor revalidation CLI + token-protected admin endpoint (external cron; observations only, never auto-overwrite).
- DNS rebinding mitigation: resolve once, connect to pinned public IP, preserve Host/SNI; conflict UI shows anchor evidence side-by-side without auto-resolution.
- Positioning & competitor map (`docs/positioning.md`), anchor-first retrieval design (`docs/spec-anchor-retrieval.md`), and a citation-vs-freshness demo case (`docs/demo-case-citation-vs-freshness.md`).
- `scripts/demo_citation_not_freshness.py` and `scripts/freshness_ci.py` (Freshness CI gate with configurable fail-on statuses).
- Tests for Freshness CI status filtering.

### Fixed

- Version claims now compare only the newest release timestamp, so two releases published the same day no longer produce a false CONFLICTED.

### Added (previous)

- Reproducibility regression test: same manifest + deterministic mock agents produce the same `config_hash` and `result_hash` in CI.
- Public-demo cost guard: global + per-IP per-minute limits and daily caps for detector/benchmark endpoints, with `429`/`Retry-After` and usage in `/api/healthz` (configurable; in-memory, resets on restart).

### Fixed

- Per-minute cap is enforced globally as well as per client, so rotating `X-Forwarded-For` cannot bypass it.

## [0.2.0-hackathon] - 2026-11-01

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
- Organizer reply recorded (`research/organizer-reply-2026-11-01.md`), submission playbook with
  combined vs dual-submission options, and updated rules/plan docs.
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

## [0.1.0-hackathon] - 2026-11-01

Hackathon preview for **Geek Room Global AI Hackathon 2026**: two independent projects
(Bifrost-02 *Agent Benchmarking Platform*, Tavily-01 *Stale-answer detector*) sharing one
evidence core.

### Added

- **Freshness pipeline (Tavily-01)**
  - LLM claim extraction (JSON mode) with exact-substring validation against the answer, plus rule-based fallback.
  - Temporal sensitivity classification: stable / slow / sensitive / volatile, with per-class validity windows and reasons.
  - Tavily live verification with supports / contradicts / mentions relations, authority tiers and timestamps.
  - Decision-table statuses `FRESH / STALE / CONFLICTED / INSUFFICIENT / UNKNOWN`, nullable score, confidence and score breakdown.
  - LLM relation review for law / leadership / date claims; correction suggestions for stale or insufficient claims.
- **Benchmark (Bifrost-02)**
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
  - Judge-facing README, demo script, charters and technical specs.

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

[Unreleased]: https://github.com/Gi-Tuu/yai-scout/compare/v0.2.0-hackathon...HEAD
[0.2.0-hackathon]: https://github.com/Gi-Tuu/yai-scout/releases/tag/v0.2.0-hackathon
[0.1.0-hackathon]: https://github.com/Gi-Tuu/yai-scout/releases/tag/v0.1.0-hackathon











