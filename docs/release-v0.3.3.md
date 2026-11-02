# YAI Scout v0.3.3 — candidate dedupe + rollback audit

Follow-up to the audit findings B5/B7.

## Fixed

- **B5**: repeated admin candidate creation for the same anchor/value/decision returns the existing pending/rejected candidate instead of inserting a duplicate.
- **B7**: rollback marks applied candidates as `rolled_back`, writes an `anchor_audit` event, and exposes `GET /admin/anchors/audit` plus an Audit table in `/admin`.

## Verification

```text
ruff  : pass
mypy  : pass
pytest: 142 passed
```

No product-scope change: one primary submission (Tavily 05), Tavily + Bifrost, `AUTO_UPDATE=false`.
