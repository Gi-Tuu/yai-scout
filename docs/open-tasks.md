# Open Tasks — YAI Scout

> Snapshot: 2026-11-02 · release `v0.3.5` · 145 tests · live `0.3.5`  
> Primary submission: **Tavily Track, Problem 05 (Stale-answer detector)**  
> Deadline: **2026-11-15 23:59 IST** (Beijing 2026-11-16 02:29)

## P0 — submission blockers

| # | Task | Owner | Due | Depends on | Done when |
|---|---|---|---|---|---|
| 1 | **Second independent labeler** labels 60 blind cases at `/label` | you + one person | 11/05 | human availability | exported JSON; run `eval_accuracy_gate.py --labels`; record agreement / false-update rate |
| 2 | **3-minute demo video** | you (record), Lead (script) | 11/10 | local Bifrost + fixed cases | shows `gateway=bifrost`, Bifrost `POST /v1/chat/completions`, STALE correction, repo/architecture |
| 3 | **Final PPT** (edit `deliverables/YAI_Scout_Submission.pptx`) | Lead/you | 11/11 | real Bifrost screenshot | deck matches shipped version; no overclaiming |
| 4 | **Submission form** | you | 11/14 | official form fields | one primary challenge, repo URL, demo URL, video URL, both-tech explanation |
| 5 | **Final submit** | you | **11/15 23:59 IST** | #1–#4 | confirmation captured |
| 6 | Join official Discord / monitor updates | you | ongoing | — | announcements checked; form/credits updates captured |
| 7 | Tavily credits status | you | ongoing | organizer | credits available or documented fallback |

## P1 — quality / evidence

| # | Task | Status | Notes |
|---|---|---|---|
| 8 | Independent-label metrics + adjudication | **tooling ready** (`private_worksheet.json`, `/label?worksheet=private`, `eval_accuracy_gate.py --worksheet`, `adjudicate_labels.py`); blocked on annotators | inter-annotator agreement; then recompute false-update rate |
| 9 | B4 residual: async SQLite writes | **deferred** | reads use `asyncio.to_thread`; writes remain synchronous. Only revisit if write concurrency grows |
| 10 | Public Bifrost deployment | optional | costs an extra service; local/video proof is enough for submission |
| 11 | Refresh fixed demo cache | as needed | `benchmarks/demo/responses.json` recorded 2026-11-01; re-record if facts/API change |
| 12 | Final repo/page check | pending | README links, release tag, `/label`, `/admin` 404 without token, healthz version |
| 13 | Submission copy / 200-word description | pending | map each official requirement to evidence (`docs/submission.md`) |

## P2 — optional, only if time remains

| # | Task | Notes |
|---|---|---|
| 14 | B10: benchmark failure injection / repeated runs / step traces | only if the benchmark becomes primary; currently explicitly **not** Bifrost 02 |
| 15 | Full async DB layer | large refactor; not worth before deadline |
| 16 | More adversarial accuracy cases | helps B9 but needs independent labels to be meaningful |
| 17 | Post-submission cleanup / blog | not required |

## Explicitly out of scope

- Re-submitting the benchmark as a second project: **one submission per team**.
- Claiming the public Render demo is Bifrost-routed: it is **direct fallback** unless a public Bifrost is deployed.
- Claiming independent human ground truth: labeler 001 matched the key 60/60 → rule-following only.
- Enabling `AUTO_UPDATE`: stays **false**.

## Recommended order

1. #1 second labeler (parallel, can start today)
2. #2 video (needs local Bifrost; script exists)
3. #3 PPT + #13 submission copy
4. #4 form + #5 submit
5. #8 metrics if labels arrive before freeze
