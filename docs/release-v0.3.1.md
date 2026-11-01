# YAI Scout v0.3.1 — audit fixes

Patch release after a full engineering audit. No product-scope change: still **one primary submission, Tavily Track Problem 05**, with Tavily + Bifrost.

## Fixed

- **Anchor evidence misattribution**: unreachable anchors no longer shift `anchor_id` / `content_changed` onto another anchor.
- **Revalidation candidates**: gate `reject` candidates are stored as `rejected`, not `pending`; same pending/rejected candidate is deduped.
- **Temporal sensitivity** from `POST /freshness/anchors` is now persisted (TTL works).
- **TTL loop**: `Anchor.last_checked_at` stops every anchor from staying permanently due.
- **Independent grouping**: primary + discovery observations use registrable-domain grouping; same publisher cannot count twice.
- **Atomic anchor replacement**: new Anchor + old superseded in one transaction.
- **Anchor creation rate limit**: `DAILY_ANCHOR_LIMIT` (default 30).
- **Live fetch**: `trust_env=False`, so proxy env vars cannot bypass pinned-IP SSRF protection.
- **API consistency**: approve/auto-apply share the candidate service.
- **Indexes**: observation/candidate indexes added.

## Verification

```text
ruff  : pass
mypy  : pass
pytest: 140 passed
gate  : 60/60 rule-consistent labels
```

Full report: `docs/audit-2026-11-02.md`.

## Known limits

- `AUTO_UPDATE` remains **false**.
- Public Render demo still uses direct model fallback unless a public Bifrost deployment is configured.
- Human labels remain rule-following, not independent ground truth.
- Benchmark is supporting evidence, not the primary challenge.
