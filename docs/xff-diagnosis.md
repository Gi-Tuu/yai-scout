# XFF / Proxy Header Diagnosis

Temporary admin-only diagnostic for verifying how the deployment proxy populates
client-address headers.

## Enable

Set:

```text
XFF_DEBUG_TOKEN=<temporary random token>
```

The endpoint is disabled (404) when the variable is empty.

## Call

```bash
curl -H "X-XFF-Debug: $XFF_DEBUG_TOKEN" \
  -H "X-Forwarded-For: 198.51.100.10, 203.0.113.20" \
  https://<host>/admin/debug/request
```

Response includes:

```text
client_host
resolved_client_key
x_forwarded_for
x_forwarded_for_chain
forwarded
x_real_ip
cf_connecting_ip
true_client_ip
x_forwarded_proto
```

Use TEST-NET addresses (`198.51.100.0/24`, `203.0.113.0/24`) only.

## Interpret

```text
observed = spoof value only          -> proxy passes client header through
observed = spoof, real egress        -> proxy appends; last hop is real
observed = real egress only          -> proxy overwrites
observed = real egress, spoof        -> proxy prepends; last-hop logic is wrong
```

Compare with the real egress address from `https://api.ipify.org`.

## Disable

Remove or empty `XFF_DEBUG_TOKEN` and redeploy/restart. The route then returns 404.

The endpoint is read-only and includes no authentication secrets in its response.


## Observed on Render (2026-11-04)

The live deployment is behind Cloudflare + Render. A request without a client
XFF produced a chain shaped like:

```text
<client-egress>, <cloudflare-edge>, <internal-render-address>
```

Cloudflare also supplied:

```text
cf-connecting-ip: <client-egress>
true-client-ip:   <client-egress>
```

Consequences:

- `X-Forwarded-For` is appended, but its **last hop is an internal Render
  address**, not the client;
- naively taking the last XFF hop collapses all clients into one rate-limit
  bucket;
- `CF-Connecting-IP` / `True-Client-IP` are the correct client identity on this
  deployment.

`UsageLimiter.client_key` now prefers those headers, then falls back to the last
XFF hop for environments without Cloudflare. Client-supplied `CF-Connecting-IP`
and `True-Client-IP` were rejected/overwritten at the edge in this deployment.

The diagnostic endpoint was enabled only for this one-off check and then
disabled by clearing `XFF_DEBUG_TOKEN`.


## Deployment contract

Supported public deployment:

```text
client -> Cloudflare -> Render -> app
```

Requirements:

- `CF-Connecting-IP` or `True-Client-IP` must be present and authoritative;
- `X-Forwarded-For` may end in an internal Render address and must not be used
  as the sole client identity;
- custom domains must remain behind Cloudflare.

If the app is deployed without Cloudflare, do not keep the public rate-limit
assumption silently: either put a trusted reverse proxy in front and supply a
known client-IP header, or change `UsageLimiter.client_key` for that topology.
The last-hop XFF fallback is only for simple direct/proxy deployments where the
last hop is actually the client.
