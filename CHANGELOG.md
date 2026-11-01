# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Pre-1.0 versions are hackathon previews; APIs may change.

## [Unreleased]

### Added

- Public demo deployment: <https://yai-scout.onrender.com> (Render free tier, `SCOUT_MODE=all`); online smoke checks pass for health, all pages and dataset, plus live freshness and benchmark runs.
- `scripts/smoke_online.py` for post-deploy verification.
- Snapshot bundle `benchmarks/snapshots.json` (32 real GitHub-release snapshots, 117 KB) exported via `scripts/export_snapshots.py` and seeded at startup, so stateless containers can run real replay; verified in a fresh container (`snapshots=32`, STALE 24 → FRESH 88).

### Planned

- 60 human-scored claims for freshness calibration (current: 20 rule-labelled).
- Real web-archive snapshots (Wayback or manual HTML) for pricing/leaderboard facts.
- More agent adapters (framework wrappers) and larger benchmark dataset.
- Final submission package: two project READMEs, slides, demo video.

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

[Unreleased]: https://github.com/Gi-Tuu/yai-scout/compare/v0.1.0-hackathon...HEAD
[0.1.0-hackathon]: https://github.com/Gi-Tuu/yai-scout/releases/tag/v0.1.0-hackathon
