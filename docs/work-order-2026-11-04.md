# 派单：YAI Scout 剩余质量问题修复

- 派单日期：2026-11-04
- 基线版本：`v0.4.2`（最新提交 `e6f0a06`）
- 基线实测：318 tests passed（Python 3.11 / 3.12），coverage 87.20%，ruff / mypy / check_imports / check_version 均绿
- 目标：关闭仍存在的稳定事实核心失败；把 live 固定用例变成可重复检查；让文档与代码一致
- 已关闭、不要重复返工：版本标识已一致（四个来源 0.4.2，本地/远端 tag 均为 `v0.4.2`）；固定回放 `YAI 0.24.0 @ 2026-11-01` 已从 `INSUFFICIENT` 修为 `STALE`，并有单测和 API 测试覆盖

---

## P0-1 修复稳定历史版本 claim 被误判为矛盾

**负责人**：编码代理 / 作者  
**依赖**：无  
**文件**：`src/yai_scout/detector/verify.py`，必要时 `src/yai_scout/detector/freshness.py`  
**测试**：`tests/test_version_relation.py`、`tests/test_replay.py`、`tests/test_fixed_case_api.py`

### 现象

README 承诺 `Python 3.12 (2023)` 为 `FRESH`，但当前 live 固定用例失败：

```text
[FAIL] stable_python_2023: expected=fresh got=['insufficient'] score=40
       只有非权威或过期的支持证据，证据强度不足
```

对应报告 `det_6787ef6bf9f4`：

- claim：`Python 3.12 于 2023 年发布。`
- 类型：`version`
- 时间敏感性：`stable`（窗口 3650 天）
- 证据：`herodevs.com` 的 Python EOL / 版本表（T3）被规则标为 `contradicts`
- 结果：没有 `supports`，最终 `INSUFFICIENT`

### 根因

`ClaimVerifier._relation` 的 VERSION 分支把“证据里出现 `Latest Release` 和更新版本”当成“当前版本 claim 被矛盾”，但该 claim 是**历史发布日期事实**，不是“当前版本是什么”。`Python 3.12 于 2023 年发布` 没有 `current/latest/当前` 语义，现有 `_HISTORICAL_CLAIM_RE` 也没有覆盖“于 YYYY 年发布 / released in YYYY”这类历史表述，于是：

1. 证据中的 `latest` 标记命中，claim 的 3.12 不在 `latest` 集合；
2. 返回 `contradicts`；
3. T3 矛盾不足以判 STALE，最终落到 INSUFFICIENT。

该页是版本/发布日期表，规则却按“最新版本”判矛盾，属于核心关系规则的误判，不是单纯检索噪声。

### 修复要求

- 保留现有“当前版本 claim + 更新 release URL/标题 → contradicts”的规则；不要回退。
- 新增“历史/稳定版本 claim”判定：
  - `claim.temporal_sensitivity is STABLE`，或
  - claim 文本含 `于 YYYY 年发布`、`released in YYYY`、`release date`、`发布日期` 等历史发布日期语义。
- 对历史/稳定版本 claim：
  - 证据同时包含 claim 版本和 claim 年份 → `supports`；
  - 证据只包含 claim 版本、不含年份 → `mentions`，不得仅凭 `latest` 标记判 `contradicts`；
  - 证据只有更新版本、没有 claim 版本 → `mentions` 或保持现有语义，但不要因为“最新版本是 3.15”就判 `contradicts`。
- 不要全局放宽“最新版本矛盾”规则；只对历史/稳定发布日期 claim 例外。
- 不要改五档状态语义或评分权重。

### 必须补的测试

1. `test_stable_release_date_claim_supported_by_version_table`
   - claim：`Python 3.12 于 2023 年发布`
   - 证据标题：`Python End-of-Life Dates`
   - 证据内容：包含 `3.12 | 2023` 和 `3.15 | latest` 的版本表
   - 断言：`supports`（至少不能是 `contradicts`）

2. `test_stable_release_date_claim_not_contradicted_by_latest_only`
   - claim：`Python 3.12 于 2023 年发布`
   - 证据内容：只有 `Latest version: 3.15`
   - 断言：`mentions`，不是 `contradicts`

3. `test_current_version_claim_still_contradicted_by_newer_release`
   - 保留现有 `test_newer_release_url_contradicts_current_claim`，确认没有回退。

4. API 级稳定用例
   - 在 `tests/test_fixed_case_api.py` 或新文件里用 `FakeTavily` 返回上述版本表；
   - `POST /freshness/verify`，`mode=live`，`as_of=2026-11-01`；
   - 断言主 claim 为 `FRESH`，且不是靠缓存。

### 验收

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\test_version_relation.py tests\test_fixed_case_api.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts\demo_fixed_cases.py --check --url http://127.0.0.1:8011
```

必须看到：

- 新增测试在修复前失败、修复后通过；
- `stable_python_2023` 在 live 检查中返回 `FRESH`；
- 现有 `yai_v024_1028` / `yai_v024_1101` / `yai_v025_1101` 仍分别为 `FRESH` / `STALE` / `FRESH`。

---

## P0-2 把固定用例变成可重复检查，避免缓存与当前代码漂移

**负责人**：编码代理 / 作者  
**依赖**：P0-1  
**文件**：`tests/test_fixed_case_api.py`、`scripts/demo_fixed_cases.py`、`benchmarks/demo/responses.json`、`.github/workflows/ci.yml`

### 问题

`scripts/demo_fixed_cases.py` 默认读取 `benchmarks/demo/responses.json`，不执行当前代码；而 `--check` 依赖 live Tavily。结果是：

- 默认 demo 4/4 通过；
- live `--check` 只有 3/4，稳定用例失败；
- 缓存与当前代码已经漂移，但没有测试拦住。

### 修复要求

- 新增离线固定用例测试，至少覆盖：
  - 3 个 replay 用例：用内存 `Store` + `SnapshotSearcher` + v0.24/v0.25 快照；
  - 1 个 stable live 用例：用 `FakeTavily` 返回版本表，走 API 路径，不访问外网。
- 不要在 CI 里调用真实 Tavily 或真实 LLM。
- P0-1 修复后重新录制缓存，禁止手工编辑 JSON：

```powershell
.\.venv\Scripts\python.exe -m uvicorn yai_scout.api.app:app --port 8011
.\.venv\Scripts\python.exe scripts\demo_fixed_cases.py --record --url http://127.0.0.1:8011
.\.venv\Scripts\python.exe scripts\demo_fixed_cases.py
```

- 增加一个缓存一致性测试：读取 `benchmarks/demo/responses.json`，断言四个用例的状态与离线测试结果一致；如果状态不一致，测试失败并提示重新录制。
- 如果 live `--check` 仍受 Tavily 波动影响，保留它作为发布前人工 smoke，不要把 `expected_status` 改成 `insufficient` 来通过。

### 验收

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts\demo_fixed_cases.py
```

必须 4/4；新增离线测试不依赖网络、不 skip。

---

## P1-1 修正 `docs/freshness-eval.md` 与实际评估不一致

**负责人**：编码代理 / 作者  
**依赖**：无  
**文件**：`docs/freshness-eval.md`

### 问题

文档写：

```text
状态判定准确率 20/20 = 100%
分数 MAE 12.06
```

实际运行：

```powershell
.\.venv\Scripts\python.exe scripts\eval_freshness.py
```

输出：

```text
status_accuracy=0.950 score_mae=11.25 (n=20)
  MISS L16: expected=stale actual=insufficient score=None
```

### 修复要求

二选一，但必须代码与文档一致：

1. **默认**：把文档改成实际结果 `19/20 = 95%`、MAE 11.25，并解释 L16：T3 支持且已超过窗口，按当前决策表判 INSUFFICIENT，不把旧 T3 支持当成 STALE 证据。
2. 如果作者认为 L16 应该是 STALE，则修代码并补测试，再把文档改成 20/20；不要只改文档。

不要为了恢复 20/20 而放宽“低权威单源不判 FRESH / 过期证据不判 STALE”的规则。

---

## P1-2 修正 `docs/architecture-shared.md` 与实际仓库结构不一致

**负责人**：编码代理 / 作者  
**依赖**：无  
**文件**：`docs/architecture-shared.md`

### 问题

文档描述 `packages/scout_core/`、`apps/benchmark/`、`apps/freshness/` 的 monorepo 结构，但当前仓库实际是 `src/yai_scout/`，没有这些目录。README 又把它作为 Architecture 链接，读者会误以为代码已这样组织。

### 修复要求

二选一：

1. **默认**：在文档顶部加明确状态说明：“这是计划中的 monorepo 拆分方案；当前实现位于 `src/yai_scout/`，尚未按 packages/apps 拆分。”
2. 或者把目录树和迁移表改成当前 `src/yai_scout` 的实际结构。

不要为了文档去实际重构目录；不要改 `store.py` 或移动模块。

---

## P2-1 补一个真实可达的反馈入口

**负责人**：作者  
**依赖**：无  
**文件**：`README.md`，可选 `.github/ISSUE_TEMPLATE/bug_report.yml`

### 问题

README 没有 issue / feedback / contributing 入口，仓库也没有 CONTRIBUTING、SECURITY 或 issue 模板；当前只能靠读者自己找到 GitHub 默认 Issues。

### 修复要求

- 在 README 增加一行明确的反馈入口，例如：
  ```markdown
  ## Feedback
  Bugs and questions: https://github.com/Gi-Tuu/yai-scout/issues
  ```
- 可选：增加一个最小的 bug report issue template，包含版本、复现步骤、预期/实际、是否使用 live key。
- 不需要社区运营、SLA 或贡献者指南。

---

## 发布口径（避免再次出现版本不一致）

- 如果这些修复要作为新版本发布：把四个来源统一改为 `0.4.3`，在 `CHANGELOG.md` 加 `## [0.4.3]`，创建 `v0.4.3` annotated tag，更新 README 的测试数和新版本说明，运行 `scripts/check_version.py --check-tag`。
- 如果暂不发布：保持 `0.4.2`，把修复写在 `## [Unreleased]`，不要重新打 `v0.4.2`，也不要在 README 宣称已修复。
- 不要只改 `pyproject.toml` 或只打 tag；四个版本来源和 tag 必须同时一致。

---

## 不做

- 不重写 `store.py`（1750 行属于数据层整合，当前可读，不做行为无收益的大改）。
- 不改五档状态枚举、评分权重或公开 API 字段。
- 不新增产品功能、不重做前端、不调整视觉选择。
- 不在 CI 中调用真实 Tavily / LLM / 外网。
- 不手工编辑 `benchmarks/demo/responses.json` 伪造结果。
- 不重新打已经存在的 `v0.4.2` tag。

---

## 完成定义

以下全部满足才算完成：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pytest -q --cov=yai_scout --cov-report=term-missing
.\.venv\Scripts\python.exe -m ruff check src tests scripts examples
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe scripts\check_imports.py
.\.venv\Scripts\python.exe scripts\check_version.py --check-tag
.\.venv\Scripts\python.exe scripts\demo_fixed_cases.py
.\.venv\Scripts\python.exe scripts\eval_freshness.py
```

要求：

- 测试数不少于 318，0 failed / 0 skipped；新增测试不得 skip；
- coverage ≥80%；
- `demo_fixed_cases.py` 4/4；
- live `--check` 4/4；如果 stable 仍受 Tavily 波动影响，必须提供离线确定性测试并在交付说明中注明 live variance，不能改 expected；
- `eval_freshness.py` 输出与 `docs/freshness-eval.md` 一致；
- `check_version.py --check-tag` 返回最新 tag 与声明版本一致；
- `git describe --tags` 与发布口径一致。

## 交付报告格式

1. 变更文件清单；
2. 新增/修改测试清单；
3. `pytest` 通过/失败/跳过数与耗时；
4. `demo_fixed_cases.py` 和 `--check` 的实际输出；
5. `eval_freshness.py` 的实际输出；
6. 文档改动位置；
7. 发布口径（是否升版本/打 tag）与 `git describe --tags`；
8. 未完成或仍有风险的点，明确写“未通过/未测”，不要写成通过。
