# Positioning: Freshness Audit Layer

> 日期：2026-11-01 · 适用：Tavily Track（stale-answer detector）· 目标：在“没有重复造轮子”的前提下，把 YAI Scout 的差异讲清楚。

## 1. 一句话定位

**Audit whether the answer you already have is still true — claim by claim, with dated evidence and a correction.**

中文：**我们审计“你手里已有的答案”是否仍然成立**，而不是再生成一个答案。

## 2. 市场地图

| 层 | 代表 | 他们回答 | 他们不回答 | 与我们的关系 |
|---|---|---|---|---|
| 带引用的答案引擎 | Perplexity、[Tavily Research](https://docs.tavily.com/documentation/api-reference/endpoint/research)、Exa、Deep Research | “现在最新的是什么？” | “你已有的旧答案现在还能信吗？” | 互补：他们生成，我们审计 |
| Grounding / 幻觉评估 | [Vectara HHEM](https://docs.vectara.com/docs/hallucination-and-evaluation/hallucination-evaluation)、[Ragas Faithfulness](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/faithfulness/)、[Cleanlab TLM](https://help.cleanlab.ai/tlm/)、[Dataiku grounding verification](https://www.dataiku.com/blog/grounding-verification-in-ai) | “答案是否被检索证据支持？” | “证据本身是否过期？” | 不同轴：support ≠ freshness |
| 时序记忆 / 知识图谱 | [Zep/Graphiti](https://github.com/getzep/graphiti)、[MemStrata](https://arxiv.org/abs/2606.26511)、Supermemory | “如何在记忆层保留时间有效性？” | “不改造上游，如何审计任意模型输出？” | 互补：他们要求拥有记忆/RAG 栈 |
| 事实核查 / 引用验证 | [Evidence-Based Temporal Fact Verification](https://arxiv.org/abs/2407.15291)、[Consensus citation verification](https://docs.consensus.app/use-cases/citation-verification)、[SemanticCite](https://arxiv.org/html/2511.16198v1) | “claim 是否被证据支持/引用是否真实？” | “它是否已过期、当前值是什么？” | 学术上最近，但多为二分类/研究原型 |
| 新鲜度 QA benchmark | [FreshQA / FreshLLMs](https://arxiv.org/abs/2310.03214) | “模型能否回答最新问题？” | “如何审计一段已有答案？” | 评测对象不同 |
| 数据管道新鲜度 | [Atlan LLM freshness scoring](https://atlan.com/know/llm-knowledge-base-freshness-scoring/) | “知识库/embedding 是否过期？” | “某条 claim 的证据是否过期？” | 层不同：pipeline vs answer |
| 直接“stale answer detector” | **未发现同定位成熟产品**（截至 2026-11-01 公开资料） | — | — | 机会窗口，但不是无人区 |

## 3. 我们是什么 / 不是什么

| 是 | 不是 |
|---|---|
| **Post-hoc audit**：输入任意模型已有答案 | 不是新的 answer engine / research agent |
| **Model-agnostic**：Perplexity、Tavily Research、DeepSeek、企业 RAG 都可审计 | 不要求替换模型或重建 RAG |
| **Claim-level temporal audit**：claim 级、带时间敏感性与有效期 | 不是整段答案的“可信/不可信”二分类 |
| **状态机**：FRESH / STALE / CONFLICTED / INSUFFICIENT | 不是“旧来源 = 过期”的简单规则 |
| **带修正**：当前值 + 建议改写 | 不只给红绿灯 |
| **As-of replay**：同一答案在历史时点是否成立 | 不是只查“今天” |
| **可审计**：证据 URL、发布时间、来源等级、score breakdown、hash | 不是黑盒 hallucination score |
| **Benchmark**：freshness-aware agent 评测 | 不是单一检测器 demo |

## 4. 四个可守差异

1. **审计已有答案，而不是生成新答案**  
   企业已有大量 answer/docs/agent output；换 answer engine 成本高，审计层可以后挂。

2. **区分“支持”与“新鲜”**  
   一条 claim 可以被 2024 年权威页面完全支持（grounding 满分），但当前值已经变了（freshness 失败）。HHEM/Ragas/Cleanlab 不覆盖这条轴。

3. **给出当前值与修正**  
   fact-check 通常输出 supported/refuted；我们输出旧值 → 当前值、权威来源、建议改写。

4. **as-of replay + 可复现证据**  
   同一答案在 2026-10-28 是 FRESH，在 2026-11-01 是 STALE；证据带时间戳与快照。对应审计、合规、事故复盘。

## 5. 必须避开的说法

| 不要说 | 原因 |
|---|---|
| “首个 claim-level 时序验证” | 已有 [Evidence-Based Temporal Fact Verification](https://arxiv.org/abs/2407.15291) 等研究 |
| “首个 stale answer detector” | fact-check、grounding、memory 都在相邻层；只能说“未发现同定位成熟产品” |
| “比 Perplexity 更不容易过期” | 他们卖生成时 live index；我们审计已有答案，不是同一比较对象 |
| “解决了记忆新鲜度” | Zep/Graphiti/MemStrata 已做 bi-temporal memory；我们不替代 |
| “行业空白” | 只能说“公开资料中未发现同时满足 post-hoc + claim-level + temporal status + correction + replay 的产品” |

## 6. Tavily Track 的契合点

- 问题陈述就是 stale-answer detector；我们直接回答“答案是否过期、当前值是什么”。
- Tavily 是**证据源**：每次审计都调用 Tavily 获取当前页面；我们让 Tavily 的价值从“生成时检索”延伸到“生成后审计/CI”。
- 与 Tavily Research 不是竞争：Research 生成带引用报告；我们审计任何报告的 claim 是否仍成立。
- 对赞助商叙事：**“Tavily finds what is current; Scout verifies what you already said is still current.”**

## 7. 30 秒评审叙事

> “Perplexity and Tavily make answers fresher at generation time. But enterprises already have millions of answers, docs, and agent outputs. We audit whether those answers are still true — claim by claim, using dated evidence from Tavily — and we tell you the current value. We are not another answer engine; we are the missing freshness QA layer.”

## 8. 商业场景（赛后）

1. **Freshness CI**：文档/客服答案发布前跑一次，STALE 则阻断。
2. **Answer audit API**：给 agent 平台/客服系统做后置校验。
3. **Compliance / incident review**：as-of replay 回答“当时是否成立”。
4. **Benchmark**：给 agent 厂商做 freshness 维度评测。

## 9. 相关设计

- 锚点优先检索与记忆更新：[`docs/spec-anchor-retrieval.md`](spec-anchor-retrieval.md)
- 新鲜度评分规则：[`docs/spec-freshness-scoring.md`](spec-freshness-scoring.md)
- 评测记录：[`docs/freshness-eval.md`](freshness-eval.md)
