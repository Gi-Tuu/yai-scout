# YAI Scout v0.3.0

**Single primary submission: Tavily Track — Problem 05 (Stale-answer detector).**
Both required technologies are now wired: **Tavily** for live research, **Bifrost by Maxim AI** as the model gateway. The benchmark stays as supporting evaluation evidence, not a second submission.

## Highlights

- **One submission narrative**: README, track docs, and submission checklist align on Tavily 05.
- **Bifrost integration is real**: `BIFROST_BASE_URL` routes every model request through Bifrost's OpenAI-compatible API; `/api/healthz` reports `gateway`.
- **Local proof**: a real `/freshness/verify` call produced `STALE` while Bifrost logged `POST /v1/chat/completions 200`.
- **Fixed no-auth gateways**: no empty `Authorization` header; local Bifrost works without a key.
- **Evidence continues to ship**: 32 real snapshots, as-of replay (2026-10-28 FRESH → 2026-11-01 STALE), 136 tests, CI matrix.
- **Editable submission deck**: `deliverables/YAI_Scout_Submission.pptx`.

## Verify

```powershell
# Local Bifrost
docker run -d --name yai-bifrost -p 8080:8080 -v "${PWD}\data\bifrost:/app/data" maximhq/bifrost
# configure provider, then:
$env:BIFROST_BASE_URL="http://127.0.0.1:8080/v1"
$env:BIFROST_MODEL="<provider>/<model>"
uv run uvicorn yai_scout.api.app:app --port 8012
python scripts/verify_bifrost.py --url http://127.0.0.1:8012
```

Expected: `gateway=bifrost`, Bifrost log `POST /v1/chat/completions`, freshness `stale`.

## Honest boundaries

- The public Render demo uses **direct** model fallback unless a public Bifrost deployment is configured; do not claim the live link is Bifrost-routed.
- Human labels: labeler 001 matched the hidden key 60/60, so they are **rule-following**, not independent ground truth. `AUTO_UPDATE` remains **off**.
- Benchmark is a 24-task demo benchmark, not an academic leaderboard.
- Replay covers GitHub Release-style facts; no fake historical evidence.

## Links

- Repo: <https://github.com/Gi-Tuu/yai-scout>
- Demo: <https://yai-scout.onrender.com/freshness>
- Bifrost integration: `docs/bifrost-integration.md`
- Bifrost verification: `docs/bifrost-verification.md`
- Submission checklist: `docs/submission.md`
