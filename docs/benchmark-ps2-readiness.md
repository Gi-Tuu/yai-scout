# PS2 Readiness — Agent Benchmarking Platform

Problem statement: build a framework-independent platform that runs AI agents on
identical tasks and measures task success, steps, tool calls, tokens, cost and
time across repeated runs; test failing tools/models/misleading instructions;
provide a comparison interface and traces.

## Current fit

| Requirement | YAI Scout | Status |
|---|---|---|
| Framework-independent agents | HTTP, Python, CLI and mock adapters | ✅ |
| Identical tasks | shared `benchmarks/tasks.json` dataset | ✅ |
| Task success | `numeric_accuracy` + `task_success_rate` | ✅ |
| Execution steps | per-sample `steps`, aggregate `avg_steps` | ✅ |
| Tool calls | per-sample `tool_calls`, aggregate `avg_tool_calls` | ✅ |
| Token usage | `avg_tokens`, `avg_tokens_in`, `avg_tokens_out` | ✅ |
| Cost | `avg_cost_usd`, per-sample samples | ✅ |
| Completion time | `avg_latency_s` | ✅ |
| Repeated runs | `repeats`, sample list, score std, success rate | ✅ |
| Failing tools | explicit `tool_timeout` / `tool_error` fault labels; injected at answer boundary | ⚠️ partial |
| Unavailable models | explicit `model_unavailable` fault label; adapter failure path | ⚠️ partial |
| Misleading instructions | fault label exists; not yet a task-instruction scenario | ⚠️ partial |
| Comparison interface | `/benchmark` leaderboard, Pareto, per-task detail, two-agent trace compare | ✅ |
| Detailed traces | `trace` + per-repeat `samples` | ✅ |
| Persisted/manifested run | manifest, result hash, result rows | ✅ |

## What is already demo-ready

```text
/benchmark UI
repeated runs (1–5)
fault injection: error / timeout / empty
Pareto frontier
per-agent leaderboard
per-task detail
trace and per-repeat samples
```

## What is still missing for a strong PS2 submission

1. Explicit scenario labels for:
   - tool timeout
   - model unavailable
   - misleading instruction / prompt injection
2. A comparison view that puts two agents' traces side by side.
3. A general task suite beyond the current freshness/evidence-oriented dataset.
4. A clear statement that this is a **small benchmark**, not an academic
   leaderboard.

## Recommended scope for the hackathon

Do not build a new benchmark platform. Position YAI Scout's benchmark as:

```text
framework-independent agent evaluation
+ repeated-run reliability
+ failure injection
+ cost/token/latency/steps/tools
+ trace comparison
```

Add only the missing failure scenario labels and a two-agent trace comparison
view if time permits. Do not claim full PS2 coverage until misleading-instruction
and unavailable-model scenarios are explicit in the test data.
