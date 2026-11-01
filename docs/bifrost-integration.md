# Bifrost Integration

> Role in the submission: **all model requests can be routed through Bifrost's OpenAI-compatible gateway** — claim extraction, relation assessment, and correction rewriting. Tavily remains the live web-research layer.

## 1. Why Bifrost

The Tavily challenge implementation note asks for:

> Use Tavily for fresh web research and **Bifrost for the model requests** that extract, assess, or rewrite claims.

So the integration is not a logo on a slide: when `BIFROST_BASE_URL` is set, every `LLMClient` request goes to Bifrost, which owns:

- provider routing / failover;
- request logs;
- budget and operational policy;
- a single OpenAI-compatible endpoint for the app.

If Bifrost is not configured, the app falls back to the direct OpenAI-compatible endpoint. The live public demo uses the fallback; the local/video demo uses Bifrost and shows its logs.

## 2. Start Bifrost locally

```powershell
# Docker (recommended for demo)
docker run --rm -p 8080:8080 -v "${PWD}\data\bifrost:/app/data" maximhq/bifrost

# or npx
npx -y @maximhq/bifrost
```

Then open <http://localhost:8080> and add an OpenAI-compatible provider (for example DeepSeek / Suanli) plus the model you want to use.

References: [Bifrost GitHub](https://github.com/maximhq/bifrost) · [Bifrost setup docs](https://docs.getbifrost.ai/quickstart/gateway/setting-up)

## 3. Configure Scout

```text
BIFROST_BASE_URL=http://127.0.0.1:8080/v1
BIFROST_API_KEY=<key if Bifrost auth is enabled>
BIFROST_MODEL=<provider>/<model>
```

`BIFROST_API_KEY` may be empty for a local gateway without auth; the client treats a configured Bifrost base URL as available and sends a bearer header only when a key is set.

## 4. Verify the integration

```powershell
curl http://127.0.0.1:8010/api/healthz
# "llm": {"available": true, "gateway": "bifrost", "model": "..."}

# trigger one audit; then check Bifrost logs
curl -s http://127.0.0.1:8010/freshness/verify \
  -H 'Content-Type: application/json' \
  -d '{"answer":"Tavily 免费计划每月提供 500 credits。","as_of":"2026-11-01"}'
```

Evidence to capture for the submission:

1. `healthz` showing `"gateway":"bifrost"`;
2. Bifrost request log for `/v1/chat/completions`;
3. the same `/freshness/verify` report.

## 5. What is routed

| Call | Routed through Bifrost when configured |
|---|---|
| Claim extraction | ✅ |
| Relation / contradiction assessment | ✅ |
| Correction suggestion | ✅ |
| Answer synthesis | ✅ |
| Tavily search | ❌ (Tavily is the research layer) |
| Deterministic scoring / status decision | ❌ (code, not model) |

## 6. Live demo limitation

Render cannot reach `127.0.0.1:8080`. For the live public demo, either:

- deploy Bifrost as a separate Render/Docker service with a public URL, or
- use the direct fallback and show Bifrost in the local/video demo.

Do not claim the public link is running through Bifrost unless `healthz` says `"gateway":"bifrost"`.
