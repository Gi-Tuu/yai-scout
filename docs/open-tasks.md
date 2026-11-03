# Open Tasks — YAI Scout

> Snapshot: 2026-11-02 · release `v0.3.6` · 204 tests · live build `ef45a66dbcb4`
> Primary submission: **Tavily Track, Problem 05 (Stale-answer detector)**
> Deadline: **2026-11-15 23:59 IST** (Beijing 2026-11-16 02:29)

## P0 — submission blockers

| # | Task | Owner | Due | Done when |
|---|---|---|---|---|
| 1 | **3-minute demo video** | you (record), Lead (script) | 11/10 | shows fixed-case FRESH→STALE, live Tavily, local `gateway=bifrost` + Bifrost `POST /v1/chat/completions`, repo/architecture |
| 2 | **Final PPT** (`deliverables/YAI_Scout_Submission.pptx`) | you/Lead | 11/11 | matches shipped `0.3.6`; no overclaim |
| 3 | **Submission copy / 200-word description** | Lead/you | 11/12 | maps official requirements to evidence (`docs/submission.md`) |
| 4 | **Submission form** | you | 11/14 | one primary challenge, repo/demo/video URLs, both-tech explanation |
| 5 | **Final submit** | you | **11/15 23:59 IST** | confirmation captured |
| 6 | Final repo/page check | you | before submit | README, demo, `/label`, `/admin` 404 without token, healthz version |

## P1 — quality / evidence

| # | Task | Status | Notes |
|---|---|---|---|
| 7 | Independent human metrics + adjudication | **blocked / on hold** | tooling exists; public key compromised; 336 public-set agreement 0.267; private `jin` failed quality (12 impossible `no_change`); other 1/30. Do not claim independent accuracy. |
| 8 | Full-page fetch for authoritative snippets | **frozen** | needs SSRF-safe fetch, allowlist, budget, size/time limits; not worth before deadline. Current evidence honestly marked `search_snippet`. |
| 9 | Public Bifrost deployment | optional | extra service; local/video proof is enough; public Render stays direct fallback. |
| 10 | Refresh fixed demo cache | as needed | `benchmarks/demo/responses.json` recorded 2026-11-01; re-record only if demo facts change. |
| 11 | B4 residual: async SQLite writes | deferred | reads use `asyncio.to_thread`; writes synchronous. |
| 12 | Join Discord / monitor updates / Tavily credits | ongoing | announcements, form changes, credits status. |

## P2 — optional, only after P0

| # | Task | Notes |
|---|---|---|
| 13 | Benchmark failure injection / repeated runs / step traces | only if benchmark becomes primary; it is **not** Bifrost-02 |
| 14 | Full async DB layer | large refactor; not before deadline |
| 15 | More adversarial accuracy cases | only meaningful with independent labels |
| 16 | Post-submission cleanup / blog | not required |
| 17 | Claim-key v2 design | `docs/claim-key-versioning.md`; additive v2 key, dual-read/backfill, no live change yet. |
| 18 | FK/JSON migration design | docs/db-migration-plan.md; post-submission table rebuild, no runtime change yet. |
| 18 | Scholarly/citation record status (future work) | only for explicit cited papers/DOIs: retraction, correction, version/edition via Crossref/OpenAlex/PubMed/Retraction Watch. Keep Tavily as the claim-evidence layer; surface it only as an evidence-status sub-check, **not** a standalone citation product or second submission. |

## Recently completed (do not re-open)

- P0-1 temporal eligibility: old/future/unknown contradictions fixed.
- P0-2 LLM aggregate assessment separated from `evidence[0]`.
- P0-3 latest vs historical version relation.
- P0-4 gate time guard: missing/invalid/future time → REVIEW.
- Coverage / abstention fields.
- Publication-date coverage / missing-date confidence.
- Versioned Evidence Receipt endpoint.
- Drift diff: content hash / kind / date changes.
- Evaluator bug fixed (Gate vs human label).
- 204 tests; CI/CodeQL green; deployed `0.3.6` build `ef45a66dbcb4`.

## Explicitly out of scope

- Re-submitting the benchmark as a second project.
- Claiming public Render is Bifrost-routed.
- Claiming independent human ground truth.
- Enabling `AUTO_UPDATE`.
- Recruiting more labelers before freeze; labels are not a submission blocker.

## Recommended order

1. Video
2. PPT + submission copy
3. Repo/page check
4. Form + submit
5. Optional P2 only after confirmation
