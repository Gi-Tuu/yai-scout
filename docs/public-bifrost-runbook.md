# Public Bifrost Runbook

> Status: **not executed yet**. Plan is "C now → B after video/PPT freeze → shut down after competition".
> Current public Scout stays on direct fallback until this runbook is completed and verified.

## 0. Non-negotiable rules

- Never commit provider keys, virtual keys, `BIFROST_SETUP_TOKEN`, or Render API keys.
- Never expose an unauthenticated `/v1/chat/completions`.
- Protect the dashboard before setting the public URL anywhere.
- Keep Scout's direct fallback intact; Bifrost must be optional.
- Do not claim `gateway=bifrost` until `/api/healthz` proves it.
- Shut down the Bifrost service and revoke its keys after the competition.

## 1. Prerequisites

- Bifrost image pinned to a version/digest, not `latest`.
- Render service plan that supports a persistent disk mounted at `/app/data`.
- A provider key dedicated to this demo if possible.
- A budget cap and a virtual key for Scout only.
- Render dashboard/API access (never paste the API key into a file).
- Local proof already captured (video) as fallback evidence.

## 2. Deploy Bifrost as a separate service

### 2.1 Render Dashboard (preferred; schema-safe)

1. New → Web Service → Deploy an existing image.
2. Image: `maximhq/bifrost:<PINNED_VERSION>`.
3. Region: same as Scout (`oregon`) to reduce latency.
4. Port: `8080`; health check path: `/health`.
5. Add persistent disk:
   - mount path: `/app/data`
   - size: smallest that fits `config.db` + `logs.db`.
6. Environment variables:

```text
APP_HOST=0.0.0.0
APP_PORT=8080
BIFROST_SETUP_TOKEN=<random 32-byte hex>
OPENAI_API_KEY=<provider key>
LOG_STYLE=json
```

Do **not** put `OPENAI_API_KEY` in the repo, logs, video, or screenshots.

7. Deploy and wait for `/health`:

```bash
curl -fsS https://<bifrost-host>/health
# {"status":"ok", ...}
```

### 2.2 Render API (only if the schema is confirmed)

Use the Render API with a service payload matching the current API version. Do not
guess fields in production; verify against the Render API schema first. The
Dashboard path above is safer for a one-off service.

## 3. First-run security setup

1. Open `https://<bifrost-host>/`.
2. Create the first admin account using `BIFROST_SETUP_TOKEN`.
3. Immediately enable **Password protect the dashboard**.
4. Configure one provider only:
   - provider: `openai` (OpenAI-compatible)
   - base URL: `https://api.suanli.cn`
   - key reference: `env.OPENAI_API_KEY`
   - models: the Scout model only
5. Create a **virtual key** for Scout:
   - budget: daily and monthly caps
   - rate limit: low
   - permissions: chat/completions only
6. Disable unused providers and unused models.
7. Do not leave the setup token in any public place after the admin exists.

## 4. Wire Scout to Bifrost

Set these on the **Scout** Render service; keep `OPENAI_*` as fallback:

```text
BIFROST_BASE_URL=https://<bifrost-host>/v1
BIFROST_API_KEY=<virtual key>
BIFROST_MODEL=openai/deepseek/deepseek-v4.1-flash-1017
```

Redeploy Scout. Verify:

```bash
curl -fsS https://yai-scout.onrender.com/api/healthz
# "llm": {"available": true, "gateway": "bifrost", ...}
```

If `gateway` is still `direct`, stop and inspect:

- `BIFROST_BASE_URL` missing/wrong;
- `BIFROST_MODEL` not in Bifrost's model list;
- Scout service not redeployed;
- Bifrost cold-starting.

## 5. Verify a real request

Use an environment variable, never a literal key in shell history you will share:

```bash
export BIFROST_KEY='<virtual key>'
curl -sS -o /tmp/bifrost_resp.json -w '%{http_code}\n' \
  -X POST https://<bifrost-host>/v1/chat/completions \
  -H "Authorization: Bearer $BIFROST_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"model":"openai/deepseek/deepseek-v4.1-flash-1017","messages":[{"role":"user","content":"reply with ok"}]}'
```

Expected: `200`, JSON with a choice; Bifrost logs show the request.

Then trigger one Scout audit:

```bash
curl -sS https://yai-scout.onrender.com/freshness/verify \
  -H 'Content-Type: application/json' \
  -d '{"answer":"Tavily 免费计划每月提供 500 credits。","as_of":"2026-11-01"}'
```

Confirm:

- response has claim verdicts;
- Bifrost logs show `/v1/chat/completions`;
- Scout `/api/healthz` still says `gateway=bifrost`.

## 6. Fallback test (must pass)

1. Temporarily unset `BIFROST_BASE_URL` on Scout.
2. Redeploy Scout.
3. Confirm `/api/healthz` says `gateway=direct`.
4. Run one audit; confirm it still works.
5. Restore Bifrost env and redeploy.

If fallback fails, roll back to direct and do not submit the Bifrost claim.

## 7. Evidence to capture

- `/health` response;
- Bifrost dashboard provider/virtual-key screenshot (no keys visible);
- `POST /v1/chat/completions` 200;
- Bifrost request log entry;
- Scout `/api/healthz` `gateway=bifrost`;
- one `/freshness/verify` report;
- fallback `gateway=direct` proof.

## 8. Rollback

Immediate rollback is always:

1. Remove `BIFROST_BASE_URL` from Scout (or set it empty).
2. Redeploy Scout.
3. Verify `gateway=direct`.
4. Leave Bifrost idle; do not delete evidence until verification is complete.

## 9. Shutdown after competition

1. Delete the Render Bifrost service.
2. Delete its persistent disk.
3. Revoke the Scout virtual key.
4. Revoke/rotate the provider key if it was dedicated.
5. Remove `BIFROST_*` env vars from Scout.
6. Redeploy Scout; verify `gateway=direct`.
7. Keep screenshots/log excerpts for verification; do not keep secrets.
8. Update `docs/bifrost-integration.md` wording to "local demo / archived".

## 10. Go/No-Go

Proceed with B only if:

- [ ] video/PPT are already frozen;
- [ ] provider key and budget are explicitly approved;
- [ ] persistent disk/plan is available;
- [ ] dashboard protection and virtual key are configured;
- [ ] fallback test passes;
- [ ] there is enough time to roll back before submitting.

Otherwise stay on C (direct fallback + local Bifrost video).
