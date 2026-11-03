# Bifrost integration — local verification record

> Date: 2026-11-02 · Local only · No paid Bifrost plan used.

## Setup actually run

```powershell
docker run -d --name yai-bifrost -p 8080:8080 `
  -v "${PWD}\data\bifrost:/app/data" `
  -e OPENAI_API_KEY=<existing model key> maximhq/bifrost
```

`data/bifrost/config.json` configures an OpenAI-compatible provider pointing at the existing model endpoint; the key is referenced as `env.OPENAI_API_KEY`, never written to the repo.

Scout was started with:

```text
BIFROST_BASE_URL=http://127.0.0.1:8080/v1
BIFROST_MODEL=openai/deepseek/deepseek-v4.1-flash-1017
```

## Evidence

1. `GET /api/healthz`:
   ```json
   {"llm":{"available":true,"gateway":"bifrost","model":"openai/deepseek/deepseek-v4.1-flash-1017"}}
   ```
2. Bifrost `/v1/models` returns the configured model catalog.
3. A real `/freshness/verify` call produced `STALE` and Bifrost logged:
   ```text
   POST /v1/chat/completions 200
   user_agent=python-httpx/0.28.1
   ```
4. `scripts/verify_bifrost.py` reproduces the check locally.

## What to record for verification

- `healthz` showing `"gateway":"bifrost"`;
- Bifrost dashboard / logs showing `POST /v1/chat/completions`;
- the same freshness report.

## Boundary

The public Render demo has no public Bifrost deployment, so its `healthz` says `"gateway":"direct"`. Do **not** claim the live link is Bifrost-routed. The local/video demo is the Bifrost proof.
