# YAI Scout — 3-Minute English Voiceover

**Target:** 2:55–3:05  
**Voice:** calm, confident, ~145–155 wpm  
**Deck:** `deliverables/YAI_Scout_Submission_EN.pptx` (11 slides)  
**Demo:** <https://yai-scout.onrender.com/freshness>

## Recording setup

- 1920×1080, browser zoom 110%, hide bookmarks and any API keys.
- Pre-open the freshness page and the fixed demo query before recording.
- If Render is cold, wait for health before starting; never record a loading spinner.
- Record voice separately in one continuous take; add slide transitions in post.
- Keep the runtime honest: do not say “accuracy improved”; say “staleness was detected”.
- Optional cutaway: terminal showing `healthz` → `"gateway":"bifrost"` and one Bifrost request log.

---

## [00:00–00:18] Slide 1 — Cover

**On screen:** YAI Scout cover; “Tavily Track · Problem 05”; “Integrated entry”.

> Every day, AI answers cite real pages that are already out of date.
>
> YAI Scout is an evidence-first stale-answer detector. It audits an existing answer claim by claim, and shows what is still true, what changed, and what cannot be verified.

## [00:18–00:42] Slide 2 — The problem

**On screen:** same answer, `FRESH 88` at 2026-10-28 → `STALE 30` at 2026-11-01.

> Here is the failure mode. This answer says YAI Agent Core is 0.24.0.
>
> The GitHub release page exists. The citation is real. The page really does support the claim. On October 28, that answer was fresh. Four days later, it was stale.
>
> Existing citation checks can’t see the difference. RAG freshness requires changing the pipeline. Manual review doesn’t scale.

## [00:42–01:05] Slide 3 — The product

**On screen:** Answer → Claims → Temporal → Research → Verdict → Correct; “KEY BOUNDARY”.

> YAI Scout works after the answer is written. It splits the answer into claims, classifies how quickly each claim can change, and researches current sources with Tavily.
>
> It returns a per-claim verdict: fresh, stale, conflicted, or insufficient. The output is not just a red light. It includes the current value, a correction, and links to evidence.
>
> Models extract and judge. Deterministic code owns status, budgets, and scoring.

## [01:05–01:28] Slide 4 — Architecture

**On screen:** Tavily and Bifrost entering the deterministic engine; freshness report and audit trail.

> Tavily is the research layer: live web search, source content, recency, and source-tier signals.
>
> Bifrost by Maxim AI is the model gateway: claim extraction, relation assessment, and correction rewriting, with provider routing and logs.
>
> A deterministic engine turns those signals into a reproducible report and an audit trail.

## [01:28–01:50] Slides 5–6 — How it works / differentiation

**On screen:** decision chain, then the six differentiation cards.

> Every claim has an explainable chain. We record the relation, recency, authority, and coverage behind the score.
>
> The same answer can be replayed against a fixed as-of time and fixed snapshots, so the result is reproducible.
>
> And freshness is kept separate from accuracy. The system does not silently overwrite an answer. Updates go through candidates, an accuracy gate, and an approve-or-rollback path.

## [01:50–02:20] Slide 7 — Fixed demo

**On screen:** fixed demo table; optionally the live page at `as_of = 2026-11-01`.

> Here is the fixed demo.
>
> At 2026-10-28, the 0.24.0 answer is fresh: score 88.
>
> At 2026-11-01, the same answer is stale: score 30, because the current value is 0.25.0. The fresh 0.25.0 claim scores 88.
>
> This is the exact behavior the product is built around: a real citation, a changed fact, and an explainable result. The demo can run offline from cached real API responses.

## [02:20–02:42] Slides 8–9 — Benchmark / Bifrost

**On screen:** 24-task benchmark summary; then local Bifrost verification log.

> We also keep a 24-task benchmark as evaluation evidence, not as a second submission: accuracy, freshness, evidence, cost, and latency, with manifests and result hashes.
>
> Bifrost is not a logo. In local verification, healthz reports gateway Bifrost, and the Bifrost log shows the chat-completions call.
>
> The public Render demo currently uses a direct fallback. We show Bifrost locally and do not conflate the two.

## [02:42–02:58] Slide 10 — Engineering

**On screen:** 249 tests, 86% coverage, CI green, 32 snapshots, AUTO_UPDATE=false.

> Engineering is part of the product: 249 automated tests, 86 percent coverage, CI, replay, evidence receipts, and rate and cost guards.
>
> We do not claim independent human accuracy. The public benchmark key is compromised, and automatic updates stay off.

## [02:58–03:05] Slide 11 — Try it

**On screen:** live URL and demo path.

> Try the fixed demo at yai-scout.onrender.com/freshness.
>
> Audit one answer. See whether it still holds.

---

## Delivery notes

- Pause briefly after “stale” and after the two scores; let the numbers land.
- Do not read the slide titles verbatim; the visuals are already doing that.
- On “real citation, changed fact”, gesture to the two cards, not the camera.
- If recording a live Demo, do not narrate waiting. Cut the wait in post.
- If the public demo is asleep, use the local replay and say “the same fixed replay runs locally”.
- Keep Bifrost language precise: **local/video verification**, not “public production Bifrost”.
- Do not claim the 24-task benchmark proves general accuracy.

## Word count

Spoken script: approximately 470 words → about 2:55–3:05 at a measured pace.
