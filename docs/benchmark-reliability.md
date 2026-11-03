# Benchmark Reliability

The benchmark runner supports repeatable reliability experiments in addition to
single-run leaderboards.

## Request

```json
{
  "agent_ids": ["mock_good"],
  "task_ids": ["b_tavily_free_credits"],
  "repeats": 3,
  "failure_injection": {
    "enabled": true,
    "rate": 0.2,
    "modes": ["error", "empty"]
  }
}
```

`repeats` is 1–5. Each task × agent cell is executed `repeats` times and stored
as one aggregated result.

## Aggregated result fields

| Field | Meaning |
|---|---|
| `repeats` | number of samples in the cell |
| `score_std` | population standard deviation of sample scores |
| `success_rate` | fraction of samples with a non-empty answer and no error |
| `faults` | injected fault modes observed in the cell |
| `trace` | bounded step/tool trace for the cell |
| `error` | `null` when all samples succeeded; otherwise failure summary |

Leaderboard adds:

```text
samples / avg_score_std / success_rate / fault_count
```

## Failure injection

The runner can inject:

- `error`: synthetic adapter error;
- `timeout`: synthetic timeout error;
- `empty`: empty answer without an error.

Selection is deterministic per `task + agent + repeat + injection config`, so
separate sessions with the same configuration reproduce the same fault pattern.
This tests the runner's failure handling and statistics; it is **not** a
measurement of a real agent's failure rate.

## Traces

Runner-level steps:

```text
run.started
fault.injected
adapter.completed
adapter.trace
freshness.completed
score.completed
```

Built-in adapters add `tool.web_search` / `llm.call` events where applicable.
External `scout-adapter/1.0` agents can return their own `trace` entries.

Traces are capped at 100 entries per cell to bound SQLite payload size.

## Public demo

Public benchmark runs are limited to synthetic agents (`mock_good`,
`mock_stale`) by default. Real retrieval/LLM agents require the admin token.
This keeps the public demo useful without exposing Tavily/LLM cost.

## Limits

- This is a deterministic fault-injection layer, not production chaos
  engineering.
- The 24-task dataset is demo scale.
- Injected failures are marked in results and must not be presented as real
  agent reliability.
