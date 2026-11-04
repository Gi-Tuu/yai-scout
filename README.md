# YAI Scout

**Evidence-first stale-answer detector.** Audit an existing LLM answer claim by claim, verify it against current sources, and show what is still true, what changed, and what cannot be verified.

[![CI](https://github.com/Gi-Tuu/yai-scout/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Gi-Tuu/yai-scout/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/Gi-Tuu/yai-scout?include_prereleases&label=release)](https://github.com/Gi-Tuu/yai-scout/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)

**Live demo:** <https://yai-scout.onrender.com/freshness>  
Free tier sleeps after ~15 min idle; first request can take 30–90s. 32 real GitHub-release snapshots ship in the image, so replay works without setup.

---

## The problem

LLM answers often look cited but cite **old pages**. Grounding and citation checks answer "is this supported by evidence", not "is the evidence still current, and what is the value today".

YAI Scout is a **post-hoc audit layer**:

```text
answer → claims → temporal sensitivity → current-source research
       → FRESH / STALE / CONFLICTED / INSUFFICIENT / UNKNOWN per claim
       → current value + correction + evidence links
```

## What is different

1. **Post-hoc**: audit answers from any model; no need to rebuild the RAG or agent.
2. **Support ≠ freshness**: evidence can fully support a claim that is already outdated.
3. **Current value + correction**, not just a red/green status.
4. **As-of replay**: the same answer is fresh at 2026-10-28 and stale at 2026-11-01 using real GitHub release history.
5. **Evidence governance**: anchors, multi-source candidates, an accuracy gate, approve/reject and rollback — automated updates stay auditable instead of overwriting silently.

## Technology roles

| Component | Role | Where |
|---|---|---|
| **Tavily** | live research: current sources, source content, recency and tier signals | `retrieval/tavily.py`, detector verification |
| **Controlled page fetch** | optional, allowlisted HTTPS fetch of a result page; default off | `sources/page.py`, `sources/anchor.py` |
| **Bifrost** | OpenAI-compatible model gateway: claim extraction, relation assessment, correction rewrite; provider routing and logs | `llm.py`, `docs/bifrost-integration.md` |
| Deterministic code | status decisions, budgets, evidence storage, scoring, audit | `detector/`, `store.py` |

Bifrost is an optional gateway. When `BIFROST_BASE_URL` is set, model requests go through Bifrost. Without it, the app uses a direct OpenAI-compatible endpoint. The public demo uses the direct fallback; local verification and the Bifrost verification docs show the gateway path.

## Quick start

```bash
uv sync --extra dev
cp .env.example .env
# fill TAVILY_API_KEY
# optional Bifrost gateway:
#   scripts/start_bifrost.ps1   # or: docker run -p 8080:8080 maximhq/bifrost
# fill BIFROST_BASE_URL / BIFROST_MODEL
uv run uvicorn yai_scout.api.app:app --port 8010
```

| URL | Purpose |
|---|---|
| `/freshness` | paste an LLM answer → claim-level freshness report |
| `/inspector` | claims → sources → timestamps → score breakdown |
| `/compare` | temporal drift between two reports (real replay) |
| `/benchmark` | evaluation: 40 tasks, multiple agents, Pareto |
| `/label` | blind accuracy labeling |
| `/admin` | token-gated candidates / approve / reject / rollback |

## Fixed replay demo

```powershell
# deterministic offline replay from cached real API responses
.\.venv\Scripts\python.exe scripts\demo_fixed_cases.py

# live check
.\.venv\Scripts\python.exe scripts\demo_fixed_cases.py --check `
  --url https://yai-scout.onrender.com
```

Fixed cases:

```text
Python 3.12 (2023)        FRESH   stable fact, old source is fine
YAI 0.24.0 @ 2026-10-28   FRESH   correct at the time
YAI 0.24.0 @ 2026-11-01   STALE   citation ≠ freshness
YAI 0.25.0 @ 2026-11-01   FRESH   current value
```

## Architecture

```mermaid
flowchart LR
  U[User / API] --> F[Claim extraction]
  F -->|LLM via Bifrost or direct| B[Model provider]
  F --> T[Tavily live research]
  T --> E[Evidence + source tiers]
  E --> V[Deterministic verification<br/>relation / recency / authority / coverage]
  V --> R[Freshness report + correction]
  R --> A[Anchor / candidate / audit]
  A --> UI[Inspector / compare / admin]
```

## Current capabilities

| Capability | Status |
|---|---|
| Claim extraction | LLM via Bifrost/direct or rule fallback; quote-substring validated |
| Live verification | Tavily search; supports / contradicts / mentions relation |
| Freshness model | temporal sensitivity classes, versioned policy and weights, explainable breakdown |
| Evidence provenance | published / updated / retrieved times kept distinct; full-page fetch preserves search metadata |
| Claim identity | typed v1/v2 keys with additive migration and dual-read fallback |
| Bifrost integration | configurable OpenAI-compatible gateway; `healthz` reports the active gateway |
| Temporal replay | GitHub release snapshots: 2026-10-28 FRESH vs 2026-11-01 STALE |
| Evidence governance | anchors, multi-source candidates, accuracy gate, approve/reject/rollback |
| Benchmark | 40 tasks, HTTP/Python/CLI adapters, repeated runs, failure injection, step/tool traces, Pareto, manifest + `result_hash` |
| Verdict evaluation | claim-level Freshness status suite; no Tavily/LLM; precision/recall/confusion |
| Quality gates | 274 tests on Python 3.11/3.12, ruff, mypy strict, CI + Docker |

## Honest limits

- Human labels are **rule-following**, not an independent ground truth; `AUTO_UPDATE` stays **off**.
- Web-archive history is unavailable in the current environment; replay uses GitHub release history and is labelled `simulated` when no snapshot exists. Historical evidence is never fabricated.
- The benchmark is a small evaluation suite, not an academic leaderboard.
- Bifrost is verified locally; the public demo uses the direct fallback unless a public Bifrost deployment is configured.
- LLM/Tavily keys are not in this repo; keyless and rule-based fallbacks exist.

## Documentation

- [Bifrost integration](docs/bifrost-integration.md) · [Bifrost verification](docs/bifrost-verification.md)
- [Benchmark reliability](docs/benchmark-reliability.md) · [Freshness verdict evaluation](docs/freshness-verdict-eval.md)
- [Claim key versioning](docs/claim-key-versioning.md)
- [Full-page fetch](docs/full-page-fetch.md)
- [Freshness scoring](docs/spec-freshness-scoring.md) · [Temporal replay](docs/spec-temporal-replay.md)
- [Anchor retrieval](docs/spec-anchor-retrieval.md) · [Accuracy gate](docs/spec-accuracy-gate.md) · [Accuracy eval](docs/accuracy-eval.md)
- [Database operations](docs/db-operations.md) · [Migration plan](docs/db-migration-plan.md)
- [Deployment](docs/deploy-free.md)
- [Governance](docs/governance/engineering-governance-v1.md) · [ADR-0003](docs/adr/0003-engineering-governance.md)
- [Engineering audit](docs/audit-2026-11-02.md) · [Changelog](CHANGELOG.md)

## License

MIT — see [LICENSE](LICENSE) and [NOTICE](NOTICE) for reused components (YAI Agent Core v0.25.0, MIT).
