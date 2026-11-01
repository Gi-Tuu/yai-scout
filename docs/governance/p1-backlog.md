# P1 Governance Backlog

> Design and task list only; none of these are implemented unless explicitly marked.
> Priority: P1-now (before final submission) / P1-later (post-hackathon).

## Architecture

| ID | Task | Priority | Depends on | Acceptance | Phase |
|---|---|---|---|---|---|
| A1 | Module dependency graph + `import-linter` contract in CI | P1-now | none | CI fails on forbidden imports; graph committed under `docs/governance/` | next |
| A2 | Extract Freshness application service from API handlers | P1-later | A1 | API handlers < 20 lines; tests unchanged | post-event |
| A3 | `Evaluator` protocol for benchmark freshness evaluation | P1-later | A1 | Runner depends on protocol, not concrete detector | post-event |
| A4 | Product boundary tests (freshness mode cannot call benchmark routes and vice versa) | P1-now | none | dedicated tests for both modes | next |
| A5 | Scout Core public interface (`__all__` + docs) | P1-later | A1 | stable import surface documented | post-event |

## Database

| ID | Task | Priority | Depends on | Acceptance | Phase |
|---|---|---|---|---|---|
| D1 | Schema version table + sequential migration runner | P1-now | none | old DB upgrades idempotently; CI tests v0→vN | next |
| D2 | Backup/restore command and documented RPO/RTO | P1-now | D1 | `scripts/backup_db.py` + restore test | next |
| D3 | Integrity checks (`PRAGMA integrity_check`, FK/orphan checks) | P1-later | D1 | CI job on a seeded DB | post-event |
| D4 | DB triggers preventing updates to completed sessions/results | P1-later | D1 | direct SQL update rejected | post-event |

## CI/CD and supply chain

| ID | Task | Priority | Depends on | Acceptance | Phase |
|---|---|---|---|---|---|
| C1 | Pin GitHub Actions by commit SHA | P1-now | none | no floating tags in workflows | next |
| C2 | CodeQL / Semgrep | P1-now | none | weekly scan + PR gate | next |
| C3 | Dependabot for pip + GitHub Actions | P1-now | none | PRs generated, CI enforced | next |
| C4 | Gitleaks secret scan | P1-now | none | CI fails on secret-like patterns | next |
| C5 | Container scan (Trivy) + SBOM (Syft) | P1-later | Docker job | artifacts stored per release | post-event |
| C6 | Release gate workflow (tag → tests → changelog → assets) | P1-later | C1/C5 | one-click release with checks | post-event |

## Runtime safety

| ID | Task | Priority | Depends on | Acceptance | Phase |
|---|---|---|---|---|---|
| R1 | API rate limit + per-IP budget | P1-now | none | public demo cannot exhaust credits; 429 tested | next |
| R2 | Request concurrency/timeout limits at API edge | P1-now | R1 | slow requests bounded; smoke test | next |
| R3 | Cost guard for public demo (daily credit cap, alert) | P1-now | R1 | cap enforced; healthz exposes usage | next |
| R4 | Error-log redaction (keys, prompts, PII) | P1-now | none | tests on log formatter | next |
| R5 | External service degradation matrix (Tavily/LLM) | P1-later | R1 | documented fallbacks + tests | post-event |

## Evaluation quality

| ID | Task | Priority | Depends on | Acceptance | Phase |
|---|---|---|---|---|---|
| E1 | 60 human-scored freshness claims | P1-now | none | MAE ≤10, agreement reported; dataset versioned | next |
| E2 | Golden dataset for hidden/private eval (outside public repo) | P1-now | P0-2 | private loader only; no leakage in CI logs | next |
| E3 | Precision / Recall / F1 for conflict detection | P1-later | E1/E2 | metrics on labelled set | post-event |
| E4 | Retrieval recall + source relevance eval | P1-later | E2 | recall@k and relevance judged on sample | post-event |
| E5 | Reproducibility test: rerun same manifest → same result_hash | **done** | P0-1/P0-6 | `test_same_manifest_and_results_are_reproducible` | v0.2.1 |
| E6 | Full evidence-graph hash (beyond TaskResult summary) | P1-later | E5 | evidence included in result hash with version | post-event |

## Suggested sequencing

1. **Now**: A4, C1–C4, R1–R3, E1, E2, E5 (submission safety and reproducibility).
2. **After event**: A2/A3/A5, D2–D4, C5/C6, R5, E3/E4/E6.

