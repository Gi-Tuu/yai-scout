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
