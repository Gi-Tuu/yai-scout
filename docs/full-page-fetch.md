# Full-page Fetch MVP

Disabled by default.

```text
FULL_PAGE_FETCH_ENABLED=false
FULL_PAGE_ALLOWLIST=docs.tavily.com,api-docs.deepseek.com
```

When enabled:

- only exact allowlisted hosts are fetched;
- reuses the hardened anchor fetch (HTTPS, pinned IP, Host/SNI, no redirects,
  500KB cap, timeout, `trust_env=False`);
- fetched evidence is marked `FETCHED_PAGE`;
- fetch failure falls back to the original search snippet.

It is intentionally opt-in: fetching every search result would add cost,
latency, and SSRF surface.

## Allowlist configuration

- values are bare hostnames, comma separated;
- case-insensitive, whitespace trimmed;
- exact host match only (no wildcards);
- empty allowlist keeps the feature off;
- `Settings.full_page_hosts()` is the single parser.

Config tests: `tests/test_full_page_config.py`.

## Time provenance

Full-page merge preserves the original Tavily `published_date` and
`published_date_source`; the fetch timestamp is stored only in `retrieved_at`.
If neither source nor page provides a publication date, it stays unknown.
