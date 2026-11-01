# Submission Deck Outline（10 slides）

> 用途：提交 PPT / 评审 5 小时窗口的 10 页材料。中英双语可选；每页不超过 5 个要点。
> 叙事：两个独立作品 → 共同证据底座 → 各自差异化 → 可复现/可审计 → 局限与路线。

## Slide 1 — Title

- YAI Scout: evidence-first research + freshness-aware agent benchmark
- Two tracks: Bifrost-02 · Tavily-01
- GitHub / live demo / team

## Slide 2 — Problem

- Agents answer fluently, but evidence may be stale, unsupported or conflicting.
- Benchmarks measure accuracy, not whether the evidence is still current.
- Stale answers are invisible in normal QA.

## Slide 3 — Two projects, one core

- Project A: benchmark different agent architectures (HTTP/Python/CLI/LLM).
- Project B: claim-level stale-answer detection with evidence.
- Shared: claims, temporal sensitivity, source tiers, snapshots, scoring policy, SQLite.

## Slide 4 — Freshness pipeline

- Answer → claims → temporal class → Tavily evidence → relation → status/score.
- Statuses: FRESH / STALE / CONFLICTED / INSUFFICIENT / UNKNOWN.
- Explainable score: relation / recency / authority / coverage; versioned policy.

## Slide 5 — Freshness demo evidence

- Example: Tavily 500 credits → STALE; official source 1,000.
- Stable fact with old source → FRESH (no age penalty).
- Evidence Inspector: source URL, timestamp, relation reason, score breakdown, suggestion.

## Slide 6 — Benchmark

- 24 tasks (21 public + 3 hidden/compromised metadata), four categories.
- Multi-dimensional leaderboard + Pareto frontier.
- Cross-architecture adapters; fairness: same dataset/target time/budget.

## Slide 7 — Reproducibility & governance

- Experiment Manifest: config hash, dataset hash, model/tool/version, code/lock, snapshots.
- `result_hash` + `/verify`; immutable runs; revisions via `supersedes`.
- Hidden isolation; legacy SQLite compatibility; tests on Python 3.11/3.12.

## Slide 8 — Results / evidence

- Freshness rule-layer: 20/20 status agreement, MAE 12.06 (20 labels).
- Real replay: GitHub release history, STALE at 2026-10-28 → FRESH at 2026-11-01.
- Benchmark: 3 architectures; mock baseline vs LLM vs external HTTP (show table).

## Slide 9 — AI usage & safety

- AI at bounded joints (claim extraction, relation, suggestions, synthesis).
- Deterministic code owns budgets, evidence, status, scoring; JSON schema-checked.
- Secrets never in manifests; public demo rate-limited (4/min, 60/20 per day).

## Slide 10 — Limits & roadmap

- Wayback unreachable → replay limited to official history; no fabricated snapshots.
- 20 labels → 60 human-scored; more adapters/datasets.
- Hidden questions compromised → private replacements outside repo.
- Ask: feedback on evaluation protocol / adapters.

## Design notes

- Font: 24pt+ body; 40pt titles; max 6 lines per slide.
- Colors: dark background (#0b0f14), amber accent (#f5a524), green/red for status.
- One architecture diagram (slide 3), one leaderboard screenshot (slide 6), one inspector screenshot (slide 5).
- Do not claim "state of the art" or "secret hidden set".
