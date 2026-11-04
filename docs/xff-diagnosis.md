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
