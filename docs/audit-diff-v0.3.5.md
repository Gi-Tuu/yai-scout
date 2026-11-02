# Diff Audit — GPT review vs current `v0.3.5`

> Baseline: current working tree after `v0.3.5` (HEAD `5ef542a` + pending fixes).  
> The GPT prompt was written against `72e7e02` / `v0.3.0`; several findings were already fixed before this audit, and **one critical regression was found again** (app did not actually use Bifrost config).

## Summary

| GPT item | Status before this audit | Action |
|---|---|---|
| P0-1 Bifrost wiring | **Confirmed broken**: app built `LLMClient` from `openai_*`, healthz reported Bifrost from config only | **Fixed** |
| P0-2 currency/units | **Confirmed broken**: `$1000` and `€1000` both `amount:1000`; credits/percent collapsed | **Fixed** |
| P0-3 independence / write safety | **Partial**: PSL bug `.co.uk` → `co.uk`; approve could target a superseded anchor | **Fixed for known aliases + transactions; residual unknown publishers** |
| P0-4 revalidation wiring | **Confirmed broken**: admin API called `revalidate_due()` without `discovery`/`auto_update` | **Fixed** |
| P1-1 research limits | Confirmed not fixed | **Fixed (rate/daily/active cap/budget reservation/timeout); XFF trust noted** |
| P1-2 ownership isolation | Confirmed not fixed | **Fixed via session owner + admin bypass; anchor writes admin-only** |
| P1-3 live fetch hardening | Mostly fixed in v0.3.5 (stream cap, `trust_env=False`) | **Adversarial tests added; timeout enforced in code** |
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

## P0-3 — independence / write safety (fixed for known publishers)

Fixed:

- registrable domain handles common multi-label public suffixes (`.co.uk`, `.com.au`, etc.) and IPs;
- GitHub org aliases are mapped to publisher domains for known orgs (`tavily-ai → tavily.com`, `deepseek-ai → deepseek.com`, `maximhq → getbifrost.ai`, `anthropic-ai → anthropic.com`, `openai → openai.com`); unknown GitHub orgs use `github:<org>`;
- primary observation and discovery share `independent_group_from_url()`;
- approving a candidate for a non-active (superseded/rolled-back) anchor returns 409;
- `Store.apply_candidate_transaction()` claims the candidate, inserts the replacement anchor, supersedes the old anchor and updates the candidate in one SQLite transaction;
- concurrent approval test has a single winner.

Residual:

- unknown cross-domain publishers (e.g. PyPI vs an unknown GitHub org) still cannot be proven independent; Gate may need a future `publisher_confidence`/review rule;
- SQLite transaction protects one process; multi-process deployments need the same DB-level transaction (SQLite WAL) or a shared store.

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

- **P1-1** `/api/research` now uses a dedicated `research` bucket (`DAILY_RESEARCH_LIMIT`), active-task cap (`MAX_ACTIVE_RESEARCH_TASKS`), wall-clock timeout, and conservative per-query credit reservation. `RESEARCH_ENABLED=false` disables it. X-Forwarded-For still trusted for per-IP limits; the global per-minute/daily caps cap spoofing damage.
- **P1-2** session cookie (`scout_sid`) + `owner_id` now scopes research tasks and freshness reports: lists filter to the current session, detail/export/cancel/events return 404 for other sessions, and `ADMIN_TOKEN` bypasses. Legacy rows (`owner_id=""`) remain public demo data. Anchor creation is admin-only by default (`PUBLIC_ANCHOR_WRITES=false`) and still rate-limited. Residual: this is a browser-session capability, not full user authentication; clearing cookies loses access.
- **P1-3** live fetch is HTTPS-only, exact-allowlisted, pinned-IP with Host/SNI, no redirects, stream-capped, no proxy env, and now has an explicit `asyncio.wait_for` timeout. Tests cover private/mixed DNS, single resolution, pinned Host/SNI, redirect refusal, non-text content-type, timeout, and 500KB cap.
- **P1-4** holdout key is public; 60/60 is rule-following, not independent ground truth. Need a private set + second labeler.
- **P2** schema version/migration runner, module-boundary CI, CodeQL/Gitleaks/Dependabot are not done.

## Verification (this change set)

```text
ruff  : pass
mypy  : pass (49 files)
pytest: 162 passed
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
