# Evidence Integrity Receipt (MVP)

Endpoint:

```text
GET /freshness/reports/{report_id}/receipt
```

Each receipt is versioned (`yai_scout.receipt.v1`) and contains:

- report id / as_of / mode;
- policy and weights versions;
- coverage and publication-date coverage;
- per-claim status, score, rationale, claim-level LLM assessment;
- evidence URL, title, domain, tier, relation, kind, fetch status, content hash,
  published_at, retrieved_at;
- limitations.

## Honest limits

- Content hashes identify the recorded evidence text, not source authenticity.
- `search_snippet` is **not** full-page verification.
- Missing publication dates are shown as unknown.
- `AUTO_UPDATE` remains disabled; a receipt is not an automatic fact update.
- No signatures, blockchain, or independent human ground truth.
