# Local Staging Load Test

This is a local, isolated staging run for HTTP P95/P99 data. It is **not** a
production capacity test.

## Components

```text
scripts/staging_server.py   # separate DB + packaged snapshots + Fake Tavily
load/k6-fixed-cases.js      # 30s mixed scenario, 6 VUs
Docker grafana/k6           # load generator
```

The staging server does not call real Tavily or LLM.

## Run

Start staging server:

```powershell
.\.venv\Scripts\python.exe scripts\staging_server.py
```

In another shell:

```powershell
docker run --rm `
  --add-host=host.docker.internal:host-gateway `
  -v "${PWD}\load:/scripts" `
  -e BASE_URL=http://host.docker.internal:8020 `
  grafana/k6 run /scripts/k6-fixed-cases.js
```

The staging DB defaults to:

```text
data/staging/staging.sqlite3
```

Set `STAGING_DB`, `STAGING_PORT`, or `STAGING_RESET=0` to override.

## Scenario

```text
replay 2026-10-28 -> fresh
replay 2026-11-01 -> stale
live stable Python 3.12 -> fresh  (Fake Tavily)
/api/healthz
```

Duration: 30 seconds, 6 total VUs.

## Local result

```text
http_reqs        = 2055
RPS              = 67.99
http_req_failed  = 0.00%
p50              = 14.77 ms
p95              = 45.24 ms
p99              = 430.61 ms
checks           = 3980/3980 passed
thresholds       = passed
```

The p99 includes occasional slow first-request/warmup behavior and SQLite writes
for detector reports. It is not a production SLA.

## Scope

- one process, one SQLite database, one local Docker k6 generator;
- no real retrieval, no LLM, no external network;
- no benchmark-run fan-out;
- no sustained soak, DB contention, or multi-instance testing.

For production capacity, use a separate staging service, independent DB, real
observability, and a longer/soak load plan.
