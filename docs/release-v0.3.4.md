# YAI Scout v0.3.4 — bounded discovery cache + anchor host policy

Follow-up to audit findings B6/B8.

## Fixed

- **B6**: `CachedDiscovery` now uses an LRU-bounded cache (`ANCHOR_DISCOVERY_CACHE_ENTRIES`, default 256); healthz exposes `cache_size`.
- **B8**: optional `ANCHOR_CREATE_ALLOWLIST` host policy; URLs with embedded credentials are rejected.

## Verification

```text
ruff  : pass
mypy  : pass
pytest: 144 passed
```

B4 (sync SQLite in async handlers) remains deferred for the single-worker demo; B9/B10 are product/scope items.
