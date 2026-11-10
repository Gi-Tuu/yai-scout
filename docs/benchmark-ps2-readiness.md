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
| Failing tools | task-level `tool_timeout` / `tool_error` scenario; built-in adapters inject failure and external adapters receive the scenario field | ✅ demo |
| Unavailable models | task-level `model_unavailable` scenario | ✅ demo |
| Misleading instructions | task-level `misleading_instruction` + `injected_instruction`; injected into source context | ✅ demo |
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

1. A general agent task suite beyond the current freshness/evidence-oriented
   dataset.
2. A UI control to attach `tool_timeout` / `model_unavailable` /
   `misleading_instruction` to a selected task; the scenario model and adapter
   behavior exist, but the dashboard currently selects tasks only.
3. A reviewer-facing statement that this is a small benchmark, not an academic
   leaderboard.

## What is already demo-ready

```text
/benchmark UI
repeated runs (1–5)
fault injection: error / timeout / empty
task-level tool/model/misleading scenarios
Pareto frontier
per-agent leaderboard
per-task detail
same-task two-agent trace comparison
trace and per-repeat samples
```

## Recommended scope for the hackathon

Do not build a new benchmark platform. Position YAI Scout's benchmark as:

```text
framework-independent agent evaluation
+ repeated-run reliability
+ task-level failure scenarios
+ cost/token/latency/steps/tools
+ same-task trace comparison
```

Do not claim full PS2 coverage until the task suite is broader than
freshness/evidence cases.
