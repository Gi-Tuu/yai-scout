# Submission Checklist — Tavily Track, Problem 05 (Tavily-01)

> Primary problem statement: **05 / Stale-answer detector [Proposed]**  
> One team, one submission. Deadline: **15 Nov 2026, 23:59 IST**.

## 1. Requirement → evidence

| Official requirement | Where it is met |
|---|---|
| Accept an LLM-generated answer | `/freshness` UI + `POST /freshness/verify` |
| Identify factual, time-sensitive claims | claim extraction + temporal sensitivity classes (`stable/slow/sensitive/volatile`) |
| Use live research to re-check claims | Tavily Search/Extract; **Tavily role documented** |
| Freshness/confidence per claim with source links | per-claim status + score breakdown + evidence links |
| Show supported / changed / cannot verify | `FRESH` / `STALE` / `CONFLICTED` / `INSUFFICIENT` / `UNKNOWN` + rationale + suggestion |
| Meaningful Bifrost use | all model requests go through Bifrost when `BIFROST_BASE_URL` is set; provider routing/logs/budget; see [bifrost-integration](bifrost-integration.md) |
| Working project/demo | Render link + `/label` + fixed demo script |
| Repository, setup, architecture | `README.md`, `docs/`, Docker/uv setup |
| Explanation of AI use | README “AI usage” + deterministic-code boundary |
| Test/measurement evidence | 223 tests; fixed replay cases; 60 rule-labeled claims + Gate eval; benchmark appendix |
| Safety/authorization | read-only web research; no pentest/security claims |

## 2. Both technologies — proof to show

1. `curl /api/healthz` → `"llm": {"gateway":"bifrost"}` when Bifrost is configured.
2. Bifrost request log for `/v1/chat/completions`.
3. Same `/freshness/verify` response showing Tavily evidence.
4. Architecture diagram: Tavily = research; Bifrost = model gateway; deterministic code = decisions.

## 3. Deliverables

- [ ] 3-minute demo video: stale answer → claims → Tavily evidence → correction; show Bifrost log.
- [ ] Public repo (README, setup, architecture, both integrations).
- [ ] Working demo link (note Render cold start).\n- [x] Editable deck: `deliverables/YAI_Scout_Submission.pptx` (`scripts/build_submission_deck.py`).
- [ ] Problem statement selected + requirement mapping (this file).
- [ ] Measurements: replay FRESH/STALE, benchmark appendix, accuracy caveat.
- [ ] `AUTO_UPDATE=false` and no overclaiming.

## 4. Known gaps / wording

- Do **not** claim Bifrost Track Problem 02.
- Do **not** claim independent human ground truth: labeler 001 matched the hidden key; call it “rule-consistent labeling”.
- Public Render demo uses direct model fallback unless a public Bifrost deployment is added; video/local demo shows Bifrost.
- Benchmark is supporting evaluation evidence, not the primary submission.


