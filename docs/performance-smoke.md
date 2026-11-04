# Performance Smoke

`scripts/perf_smoke.py` measures the deterministic freshness scorer, not the
full HTTP/Tavily path.

```powershell
.\.venv\Scripts\python.exe scripts\perf_smoke.py --iterations 200
```

Example local result:

```text
cases=50 iterations=200 samples=10000
p50_ms=0.0174 p95_ms=0.0358 p99_ms=0.0676
mean_ms=0.0206 max_ms=1.1651
```

Scope:

- pure `score_claim()` on the 50 fixed verdict cases;
- no network, no LLM, no SQLite;
- local microbenchmark, not a long-run load test.

A real P95/P99 load test still needs a running API, concurrent clients, DB
writes and external retrieval; that is not claimed here.
