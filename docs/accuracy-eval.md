# Accuracy Gate 独立标注评估（v0）

> 日期：2026-11-02 · 标注者：`001` · 数据：60 条盲标 worksheet（`holdout_worksheet.json`）  
> 评估脚本：`scripts/eval_accuracy_gate.py --labels ... --key ...`

## 1. 结果

```text
cases=60
agreement=1.000
gate_auto=18
auto_precision=1.000
false_update_rate=0.000
review_coverage=0.000 (0/18)
confusion: 18 auto / 22 review / 10 reject / 10 no_change 全部一致
```

## 2. 必须写进材料的局限

**这组标签与隐藏 key 完全一致（60/60）**，这是一个强警告信号：

- 可能标注者按同一套规则作答（我在 `/label` 前给过规则讲解）；
- 也可能看到了 key（不应发生）；
- 也可能是题目过于规则化，没有真正歧义。

因此：

- **不能把它写成“独立人工验证通过 / false update rate 0%”**；
- 它只能证明“规则可被按规则执行的人复现”，不是泛化准确率；
- 真正的独立验证需要：**未看规则说明的第二标注者 + 有歧义的对抗样本 + 计算 inter-annotator agreement**。

## 3. 当前可对外表述

- 规则层 60 条：agreement 1.000（设计一致性）；
- 人工标签 `001`：与规则层 60/60 一致（按规则标注）；
- **false update rate 尚无独立意义**，因为 ground truth 与规则同源；
- `AUTO_UPDATE` 保持默认关闭。

## 4. 下一步

1. 找第二标注者，不看规则说明，只按 60 题判断；
2. 比较 `labeler_001` 与 `labeler_002`：inter-annotator agreement；
3. 对分歧题做裁决，形成真正 ground truth；
4. 用裁决后的标签重算 agreement / false update rate；
5. 加入对抗样本（镜像、单位歧义、旧证据、冲突），避免 100% 过于容易。

## 5. 复现

```powershell
.\.venv\Scripts\python.exe scripts\eval_accuracy_gate.py `
  --labels benchmarks\accuracy_gate\independent_labels_001.json `
  --key benchmarks\accuracy_gate\holdout_key.json
```


## Private worksheet (v0.3.6 tooling)

The public key is compromised. A 30-case private worksheet (cases only, no
answers) is now available; labels stay outside the repo. Metrics are only
meaningful after an independent annotator and adjudication.

```powershell
python scripts/eval_accuracy_gate.py `
  --worksheet benchmarks/accuracy_gate/private_worksheet.json `
  --labels accuracy_labels_private_<name>.json
```
