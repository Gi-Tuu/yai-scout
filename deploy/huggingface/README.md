---
title: YAI Scout
emoji: 🔎
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: Evidence-first research agent + freshness-aware agent benchmark
---

# YAI Scout

Two entry points sharing one evidence core:

- `/benchmark` — cross-architecture agent evaluation
- `/freshness` — claim-level stale-answer detector
- `/inspector` — evidence inspector
- `/compare` — temporal drift

## Space setup

1. Create a **Docker Space** on Hugging Face.
2. Upload `Dockerfile` and this `README.md` to the Space repository (the Dockerfile clones the public GitHub repo at build time).
3. In **Settings → Variables and secrets**, add:
   - `TAVILY_API_KEY` (secret)
   - `OPENAI_API_KEY` (secret)
   - `OPENAI_BASE_URL` = `https://api.suanli.cn/v1`
   - `LLM_MODEL` = `deepseek/deepseek-v4.1-flash-1017`
4. Rebuild the Space. First build takes a few minutes.

Free CPU Spaces sleep after inactivity; the first request after sleep may take 30–60s.
