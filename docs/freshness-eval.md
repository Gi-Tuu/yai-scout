# Freshness 评测与校准记录（20 条人工标注）

> 日期：2026-11-01 · 数据：`benchmarks/labeled_claims.json` · 脚本：`scripts/eval_freshness.py`
> 说明：这是**规则层**的状态/分数评估（不调用 Tavily/LLM），用于验证决策表与权重；真实链路的检索噪声另算。

## 1. 标签集

20 条 claim，覆盖：
- pricing（价格）、version（版本）、law（许可证）、leadership（人事）、date（日期）、statistic（换算/常数）、other（标准定义）；
- 稳定/慢变/敏感三档；证据关系 supports/contradicts/mentions/空；来源档位 T1–T4；
- 期望状态：fresh / stale / conflicted / insufficient。

## 2. 结果

| 指标 | 值 |
|---|---|
| 状态判定准确率 | **20/20 = 100%** |
| 分数 MAE（rubric-v1 0.5/0.3/0.2） | 13.41 |
| 分数 MAE（rubric-v2 校准 0.6/0.1/0.3） | **12.06** |
| 网格搜索最优（accuracy 全 1.0 下 MAE 最小） | 0.6 / 0.1 / 0.3 |

> 分数目标值由状态推导（fresh 85 / stale 25 / conflicted 50 / insufficient 30），**不是人类打分**，只用于比较权重相对优劣；不要把它当"人类一致性"。

## 3. 校准结论

- 状态判定（决策表）在 20 条上全对，说明"先关系/权威/时效、再分数"的顺序是有效的。
- 权重从 rubric-v1 更新为 **rubric-v2-calibrated**：
  `relation 0.6 / recency 0.1 / authority 0.3`，MAE 下降约 10%。
- 该权重已写入 `detector/freshness.py`（`WEIGHTS_VERSION = "rubric-v2-calibrated"`）。

## 4. 局限（必须写进提交材料）

1. 标签只标状态，分数目标由规则推导，**不是独立人工评分**；下一步需要 60 条人类打分做真正回归。
2. 评估不包含检索/LLM 噪声；真实链路的误差应单独测（live eval）。
3. 20 条样本小，不能宣称"泛化准确率 100%"；应在报告中写"规则层 20/20，待扩样"。

## 5. 复现

```powershell
.\.venv\Scripts\python.exe scripts\eval_freshness.py
.\.venv\Scripts\python.exe scripts\eval_freshness.py --calibrate
```
