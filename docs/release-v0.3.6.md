# YAI Scout v0.3.6 — diff-audit fixes

Fixes confirmed against the GPT audit, without adopting the stale parts of that prompt.

## Fixed

- **P0-1 Bifrost wiring**: app now builds `LLMClient` from `Settings.llm_connection()`; healthz reads the actual gateway/model; manifest records effective gateway/model and a redacted key fingerprint. Real local gateway + app E2E test.
- **P0-2 currency/unit normalization**: preserves USD/EUR/GBP/CNY, credits, percent and periods; `$1000` != `€1000`, `1000 credits` != `$1000`, `credits/month` != `credits/year`.
- **P0-4 revalidation API**: now passes `discovery` and `accuracy_auto_update`; API->discovery->candidate integration test added.
- **P0-3**: public-suffix grouping, known GitHub publisher aliases, active-anchor guard, and transactional single-winner candidate approval (CAS in SQLite).

## Still open

P0-3 residual unknown cross-domain publishers, P1 research budget/ownership, P1 private labels, P2 architecture/DB/CI. See `docs/audit-diff-v0.3.5.md`.

## Verification

```text
ruff  : pass
mypy  : pass (49 files)
pytest: 150 passed
gate  : 60/60
Docker: built
```

