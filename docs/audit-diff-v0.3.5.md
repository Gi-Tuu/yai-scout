# Diff Audit — GPT review vs current `v0.3.5`

> Baseline: current working tree after `v0.3.5` (HEAD `5ef542a` + pending fixes).  
> The GPT prompt was written against `72e7e02` / `v0.3.0`; several findings were already fixed before this audit, and **one critical regression was found again** (app did not actually use Bifrost config).

## Summary

| GPT item | Status before this audit | Action |
|---|---|---|
| P0-1 Bifrost wiring | **Confirmed broken**: app built `LLMClient` from `openai_*`, healthz reported Bifrost from config only | **Fixed** |
| P0-2 currency/units | **Confirmed broken**: `$1000` and `€1000` both `amount:1000`; credits/percent collapsed | **Fixed** |
| P0-3 independence / write safety | **Partial**: PSL bug `.co.uk` → `co.uk`; approve could target a superseded anchor | **Partially fixed** |
| P0-4 revalidation wiring | **Confirmed broken**: admin API called `revalidate_due()` without `discovery`/`auto_update` | **Fixed** |
| P1-1 research limits | Confirmed not fixed | Deferred (P1) |
| P1-2 ownership isolation | Confirmed not fixed | Deferred (P1) |
| P1-3 live fetch hardening | Mostly fixed in v0.3.5 (stream cap, `trust_env=False`) | Tests partial |
| P1-4 evaluation independence | Confirmed not fixed | Deferred (blocked on human) |
| P2 architecture/DB/CI | Not done | Deferred |

## P0-1 — Bifrost wiring (fixed)

Before: `create_app()` used `cfg.openai_api_key/base_url/llm_model`; healthz showed `gateway=bifrost` based on config existence, not the actual client.

Now:

- `Settings.llm_connection()` is the single effective resolver: Bifrost if `BIFROST_BASE_URL` is set, direct otherwise.
- `create_app()` builds `LLMClient` from that resolver; healthz reads `llm.gateway/model` from the actual client.
- `ExperimentManifest` records `model_provider/model_name`, `tool_configuration.model_gateway`, `model_base_url`, and a redacted credential fingerprint.
- Tests:
  - app end-to-end with `httpx.MockTransport` → `/freshness/verify` hits `/v1/chat/completions` with Bifrost model;
  - manifest Bifrost vs direct produces different `config_hash`, no secret in JSON;
  - local real Bifrost: `healthz gateway=bifrost`, `POST /v1/chat/completions 200`.

Limitation: public Render still uses direct fallback because no public Bifrost is deployed.

## P0-2 — currency/units (fixed)

`normalize_value()` now preserves:

- currency: `usd/eur/gbp/cny` (`$1000` ≠ `€1000`);
- credits vs currency (`credits:1000` ≠ `usd:1000`, ambiguous → REVIEW if claim conflicts);
- percent (`pct:50`);
- periods (`credits:1000/month` ≠ `credits:1000/year`);
- semantic equivalence (`1000 USD` == `$1,000`).

60 labeled gate cases still pass 60/60; new required assertions added.

## P0-3 — independence / write safety (partial)

Fixed:

- registrable domain now handles common multi-label public suffixes (`.co.uk`, `.com.au`, etc.) and IPs;
- primary observation and discovery share `independent_group_from_url()`;
- approving a candidate for a non-active (superseded/rolled-back) anchor returns 409.

Still open:

- `github.com/<org>/...` vs the same organization's official docs cannot be proven independent from hostname alone; a publisher registry/alias map is still needed.
- Concurrent double-approval is not CAS-protected; two admin calls can race between read and write.
- Candidate status update and anchor replacement are separate transactions (anchor replacement is atomic, candidate update is not).

`ACCURACY_AUTO_UPDATE` remains **false**.

## P0-4 — revalidation API wiring (fixed)

Before: `POST /admin/anchors/revalidate` called:

```python
revalidate_due(store, fetcher=fetcher, limit=...)
```

so discovery and auto-update flag never reached the service.

Now it passes:

```python
discovery=discovery,
auto_update=cfg.accuracy_auto_update,
```

Added API → replay observation → discovery → candidate integration test; discovery failure remains best-effort.

## P1/P2 — intentionally deferred

- **P1-1** `/api/research` has no dedicated limiter/budget and can trigger Tavily research; needs an `research` bucket/budget or public demo disable.
- **P1-2** `/api/research`, `/freshness/reports`, `/freshness/anchors` lack per-user ownership; public demo exposes all reports/tasks. Needs session/owner model before multi-user use.
- **P1-3** live fetch is HTTPS-only, allowlisted, pinned-IP, no redirects, stream-capped, no proxy env; adversarial DNS/redirect tests are still thin.
- **P1-4** holdout key is public; 60/60 is rule-following, not independent ground truth. Need a private set + second labeler.
- **P2** schema version/migration runner, module-boundary CI, CodeQL/Gitleaks/Dependabot are not done.

## Verification (this change set)

```text
ruff  : pass
mypy  : pass (49 files)
pytest: 149 passed
gate  : 60/60 rule-consistent labels, auto precision 1.000
Bifrost app E2E: MockTransport + local real gateway
Docker: pending CI
```

## Numbering note

Official problem ID **05** = `Stale-answer detector`; it is the first of Tavily's two challenges, i.e. **track-local Tavily-01**. Do not write "Tavily Problem 05" without the "global 05" clarification.

## Not done / not claimed

- Public Bifrost deployment.
- Independent human ground truth.
- Research/API ownership isolation.
- Failure injection for the benchmark (not primary).
