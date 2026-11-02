# Accuracy Gate 标注协议（v0）

> 用途：为 `docs/spec-accuracy-gate.md` 的 Gate 规则提供可评估标签；不是生产真值。

## 1. 标注对象

每条样本描述：

- 当前 Anchor（旧值、来源、时间、hash）；
- 一条或多条 Observation（新来源、值、时间、来源等级、独立性分组）；
- claim 的 temporal sensitivity；
- 期望决策：`auto_update / review / reject / no_change`。

**不标注 freshness**；只标注“是否允许把候选值写回记忆”。

## 2. 决策定义

| 决策 | 含义 |
|---|---|
| `auto_update` | 满足 Gate 高置信条件，可自动追加新 Anchor + 更新记忆 |
| `review` | 需要人工/评审确认；候选保留 |
| `reject` | 不采用候选（无权威/更旧/仅低权威/不可达） |
| `no_change` | 归一化后与当前值相同；不产生更新 |

## 3. 标注流程

1. 两名标注者独立标注（不看到彼此结果）；
2. 分歧由第三人裁决；
3. 记录 `labeler_a` / `labeler_b` / `adjudicated`；
4. 只有裁决后的标签进入 Gate 评估；
5. 任何标签修改都提升 `version` 并写 changelog。

## 4. 判断顺序（与 Gate 一致）

```text
1 无 observation / 不可达 → reject
2 归一化值 == anchor.value → no_change
3 归一化不确定 → review
4 observation 比 anchor 更旧 → reject
5 存在 T1/T2 冲突 → review
6 ≥2 个独立 T1/T2 组且一致 → auto_update
7 仅 1 个 T1/T2 组 → review
8 只有 T3/T4 → reject
```

## 5. 独立性判定

- 独立组 = 发布组织/注册域，不是单个 URL；
- 同一组织的 docs、CDN、wiki、镜像算同一组；
- 转载/聚合站不算独立权威；
- 若无法判断独立性，标 `review`，不要猜。

## 6. 来源等级

| 等级 | 示例 |
|---|---|
| T1 | 官方定价页、官方文档、官方 release |
| T2 | 官方仓库、官方帮助中心、可核验的一手 API 元数据 |
| T3 | 行业媒体、社区文档、二手整理 |
| T4 | 博客、论坛、营销页、不可核验转载 |

## 7. 歧义处理

以下一律 `review`，不要自动归一化：

- 单位缺失或与 claim 不一致（credits vs USD）；
- 千分位/小数点歧义（`1.000`）；
- 版本 `0.25` vs `0.25.0`；
- 日期无时区且跨日；
- 许可证非标准写法；
- 同一独立组内部冲突。

## 8. 独立标注工作流

```powershell
# 1) 生成 60 条盲标题目（已生成，可重跑）
python scripts/make_labeling_worksheet.py
#    → benchmarks/accuracy_gate/holdout_worksheet.json
#    → benchmarks/accuracy_gate/holdout_key.json（标注者不要打开）

# 2) 打开盲标页面
#    http://127.0.0.1:8010/label
#    输入 labeler 名字，逐题选择 4 类决策；localStorage 自动保存
#    完成后“导出 labels JSON”

# 3) 评估独立标签
python scripts/eval_accuracy_gate.py \
  --labels accuracy_labels_<name>.json \
  --key benchmarks/accuracy_gate/holdout_key.json
```

输出：agreement、gate auto precision、false update rate、review coverage、confusion。

## 9. 评估指标

| 指标 | 目标 |
|---|---|
| Gate agreement（与裁决标签一致率） | ≥0.85 |
| Auto-update precision | ≥0.95 |
| False update rate | ≤0.05 |
| Review coverage（应更新但送审） | ≤0.4 |
| Reject precision | ≥0.9 |

**False update rate 优先于覆盖率**：宁可送审，不可错写。

## 9. v0 结果与局限

- 60 条 v0 标签上 gate agreement = 1.000（18/22/10/10）；\n- labeler `001` 独立结果 60/60 与 key 一致 → 视为“按规则标注”，不是独立 ground truth；见 `docs/accuracy-eval.md`。
- 标签由规则同一作者设计，存在**过拟合**，不能当作泛化证据；
- 扩到 60 条时必须由第二人独立标注/裁决，并加入 adversarial cases（镜像、歧义、旧证据、冲突）。

## 10. 数据集约定

- 文件：`benchmarks/accuracy_gate/labeled_cases.json`
- `synthetic_metadata: true`：事实来自公开资料，来源元数据为合成；
- 60 条 v0 样本，覆盖四类决策；
- 每条含 `expected.reason` 和 `gate_version`；
- 后续扩到 60 条时保持同一 schema，提升 `version`。

## 11. 禁止事项

- 不把 LLM 判断当成人工标签；
- 不用未核验的“行业常识”补标签；
- 不为了让 Gate 好看而修改标签；
- 不把 accuracy 标签用于 freshness 分数。






## Private worksheet

The original 60-case key is public, so its 60/60 is rule-following, not
independent validation.

Use the private worksheet instead:

```powershell
python scripts/make_private_worksheet.py   # 30 cases, no expected decisions
# annotate: /label?worksheet=private
python scripts/eval_accuracy_gate.py `
  --worksheet benchmarks/accuracy_gate/private_worksheet.json `
  --labels accuracy_labels_private_<name>.json
```

- `private_worksheet.json` contains **cases only**; answers are never committed;
- exported label files are **gitignored**;
- two annotators + `adjudicate_labels.py` for disagreements;
- do not update labels to make metrics look better.
