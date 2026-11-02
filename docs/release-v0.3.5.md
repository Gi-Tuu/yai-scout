# YAI Scout v0.3.5 — offload read-only SQLite calls

Minimal safe follow-up to B4.

## Changed

- Read-only anchor/admin/healthz/compare store calls run through `asyncio.to_thread`, so a slow anchor read no longer blocks `/api/healthz` or other requests.
- Writes remain synchronous inside their existing transactions/locks; no data-layer rewrite.
- Added a concurrency smoke test: a 300ms slow anchor read does not delay healthz beyond 200ms.

## Verification

```text
ruff  : pass
mypy  : pass
pytest: 145 passed
```

No product-scope change: one primary submission (Tavily 05), Tavily + Bifrost, `AUTO_UPDATE=false`.
