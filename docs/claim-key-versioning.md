# Claim Key Versioning Design

> Status: **typed v2 identity, migration 8, backfill and dual-read are implemented.**
> `claim_type` is persisted in the payload; v1 remains the legacy fallback.

## 1. Problem

`claim_key()` currently removes every number:

```python
NUMBER_RE.sub("#", text.lower())
```

That intentionally matches the same fact when its value changes:

```text
Tavily 免费 500 credits
Tavily 免费 1,000 credits
→ tavily 免费 # credits
```

But it also merges distinct facts:

```text
第1季度营收 500
第2季度营收 600
→ 第#季度营收 #
```

```text
2026 年截止
2027 年截止
→ # 年截止
```

Changing v1 in place would break every historical `Anchor.claim_key`.
Therefore v2 must be **additive**.

## 2. Goals / non-goals

Goals:

- stop merging different periods/quarters/dates;
- keep matching the same fact when only its **value** changes;
- make the key version explicit;
- preserve v1 data and API compatibility;
- allow a gradual rollout.

Non-goals:

- entity resolution / NER;
- cross-language semantic matching;
- rewriting existing anchors in one shot;
- changing the Accuracy Gate decision logic.

## 3. v2 key policy

v2 protects **identity qualifiers** and normalizes only **value tokens**.

### Preserved (not normalized)

- ISO date: `2026-11-01`
- Chinese date: `2026 年 11 月 1 日`, `2026 年`
- Quarter: `Q1`..`Q4`, `第1季度`, `一季度`
- Month/day: `11 月`, `11-01`
- Currency/unit/period: `USD`, `EUR`, `credits`, `/month`, `/year`
- Version tokens: **only when `claim.type == VERSION`** (see below)

### Normalized

- amounts: `500`, `1,000`, `$500`, `30%`
- counts: users/downloads/registrations
- ports: `8080` (port changes are value changes)
- version tokens for non-VERSION claims

### Type-specific rules

| Claim type | Version token | Date/quarter | Amount |
|---|---|---|---|
| `DATE` | n/a | preserved | normalized |
| `VERSION` | normalized (`#`) | preserved | normalized |
| `PRICING` | normalized | preserved | normalized |
| `STATISTIC` | normalized | preserved | normalized |
| `LAW` / `LEADERSHIP` | preserved | preserved | normalized |
| `OTHER` | preserved | preserved | normalized |

Rationale:

- `DATE` / periods are identity: Q1 revenue ≠ Q2 revenue;
- `VERSION` claims are usually “current version” → version is the value, so
  normalize it, while preserving the rest;
- amounts are values everywhere.

### Examples

```text
第1季度营收 500       → 第1季度营收 #
第2季度营收 600       → 第2季度营收 #      (different)
2026 年截止           → 2026 年截止
2027 年截止           → 2027 年截止        (different)
Tavily 500 credits    → tavily # credits
Tavily 1000 credits   → tavily # credits   (same)
当前版本 0.24.0       → 当前版本 #
当前版本 0.25.0       → 当前版本 #          (same family)
```

## 4. API and storage

### Functions

```python
CLAIM_KEY_VERSION = 2

def claim_key_v1(text: str) -> str: ...          # current implementation
def claim_key_v2(text: str, claim_type: ClaimType | str) -> str: ...
def claim_keys(text: str, claim_type: ClaimType | str) -> tuple[str, str]:
    return claim_key_v1(text), claim_key_v2(text, claim_type)
```

Keep `claim_key()` as an alias for v1 until dual-read is removed.

### Model

```python
class Anchor(BaseModel):
    claim_key: str                 # v1, historical
    claim_key_v2: str = ""         # v2, new
    claim_key_version: int = 1     # 1 or 2
```

### Database (migrations 7-8)

```sql
ALTER TABLE anchor ADD COLUMN claim_key_v2 TEXT NOT NULL DEFAULT '';
ALTER TABLE anchor ADD COLUMN claim_key_version INTEGER NOT NULL DEFAULT 1;
CREATE INDEX idx_anchor_claim_v2 ON anchor(claim_key_v2);
-- migration 8: classify claim_text, persist claim_type in payload, recompute v2
```

Backfill:

- use `resolve_claim_type()` from `claim_classification.py`;
- if `claim_text` is present, persist `claim_type`, compute v2, and set version 2;
- if `claim_text` is empty, leave the legacy record untouched.

No destructive rewrite; v1 stays.

## 5. Lookup semantics

### New anchors

Write all three fields:

```text
claim_key      = v1
claim_key_v2   = v2
claim_key_version = 2
```

### Detector matching

1. Try exact v2 match.
2. If no v2 match, fall back to v1 **only for anchors with
   `claim_key_version = 1`**.
3. Never mix v1 matches with v2 matches in one candidate set.
4. Deduplicate by anchor id; prefer v2.

This avoids an old v1 collision silently overriding a new v2 identity.

### Compare / drift

- New reports use v2 for claim pairing.
- If a legacy report has no stored v2, compute v2 from `claim.text` at read
  time.
- Keep v1 as a fallback for reports that only have opaque claim keys.

## 6. Rollout plan

### Phase 1 — shadow

- Add v2 functions and tests.
- Compute both keys for every new anchor/report.
- Do not use v2 for matching yet.
- Log/compare collision counts.

### Phase 2 — dual read

- Detector prefers v2, falls back to v1 legacy.
- New anchors write v2.
- Compare uses v2.
- Feature flag: `CLAIM_KEY_MODE=v2-shadow|v2|v1`.

### Phase 3 — backfill

- Migration 7 adds columns/index.
- Backfill anchors with `claim_text`.
- Run consistency report.

### Phase 4 — v1 retirement

Only after:

- all active anchors have v2 or are confirmed legacy-only;
- no lookups hit the v1 fallback for a full reporting period;
- tests and production metrics agree.

## 7. Tests required

Property/fuzz tests are implemented in `tests/test_claim_key_properties.py`
(deterministic random corpus; no Hypothesis dependency).

- v2 keeps same fact with changed amount;
- v2 separates Q1/Q2;
- v2 separates 2026/2027;
- v2 normalizes version when `ClaimType.VERSION`;
- v2 preserves date/quarter;
- v1 remains byte-identical for historical keys;
- detector prefers v2 and falls back only to v1 legacy;
- mixed v1/v2 anchors do not duplicate candidates;
- compare pairs on v2, legacy reports still work;
- migration backfill idempotent.

## 8. Risks

| Risk | Mitigation |
|---|---|
| New keys split an old anchor from a value update | New anchors write both; v1 fallback for legacy only |
| Mixed v1/v2 candidates duplicate | dedupe by anchor id; prefer v2 |
| Backfill wrong due missing `claim_text` | leave version 1; do not guess |
| Claim type misclassification changes key | type-specific tests; shadow mode |
| API clients pass old keys | keep v1 alias and query param |

## 9. Recommendation

Implement v2 in this order:

1. pure functions + tests (no runtime switch);
2. shadow write;
3. dual-read behind flag;
4. migration 7 + backfill;
5. switch and remove v1 fallback later.

Do not change the live key without a migration and dual-read rollout.
