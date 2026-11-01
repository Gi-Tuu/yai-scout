# Submission Playbook（2026-11-01 更新）

> 依据：主办方 2026-11-01 回复（`research/organizer-reply-2026-11-01.md`）：表单字段即将更新；
> 允许合并项目；两轨评委分别评审；15 日前可继续 commit；
> Tavily credits 将另行发送。
> 目标：在表单未定稿前，两套包装都准备好，随时可提交。

## 1. 倒排（北京时间）

| 日期 | 动作 | 产物 |
|---|---|---|
| 11/01–11/02 | 合并治理分支，发布 `v0.2.0`；线上冒烟 | tag + release + smoke |
| 11/03–11/08 | P1 收尾：60 条标注、限流/成本保护、Evidence Inspector 打磨 | 数据 + 截图 |
| 11/09–11/11 | 录 Demo、写 PPT、提交文案 | 视频 + 10 页 deck |
| **11/12** | **功能冻结**；只允许文档/修复/部署 | freeze 标签 |
| 11/13–11/14 | 双套材料打包、链接检查、离线备份 | 最终包 |
| **11/15 12:00** | 目标提交时间（预留 14h 缓冲） | 提交成功截图 |
| 11/15 23:59 IST = **11/16 02:29 北京** | 硬截止 | — |

> 主办方确认 15 日前可继续 commit，但**不要卡点**：提交流程未知，预留缓冲。

## 2. 两套提交形态

### 方案 A（默认）：一个仓库 + 一次提交 + 两轨章节

- 表单：GitHub 链接 = `https://github.com/Gi-Tuu/yai-scout`
- README 顶部写清：
  - `Project A — YAI Scout Benchmark → Bifrost Track, Problem 02`
  - `Project B — YAI Scout Freshness → Tavily Track, Problem 01`
- 视频：3–4 分钟，前 2 分钟 A、后 2 分钟 B（章节字幕）
- PPT：10 页（A 5 页 + B 5 页 + 共享底座 1 页）
- 评委按赛道分别评审（主办方确认），一份材料同时进入两轨。

**适用**：表单仍只有一个提交入口（当前 API 为 `allow_multiple_submissions=false`）。

### 方案 B（备选）：两次独立提交

- 仅当表单更新后允许第二次提交 / Track 选择时启用。
- A 与 B 各自：独立 README、2 分钟视频、5 页 PPT、独立验收说明。
- 仓库仍是同一个，但每条提交只指向对应入口与文档。

**决策规则**：
1. 表单更新后先截图字段；
2. 若出现 Track 字段 / 允许两次提交 → B；
3. 否则 → A（默认）。

## 3. 提交材料清单（两套共用）

| 材料 | 要求 | 位置 |
|---|---|---|
| GitHub | 公开、可 clone、License/NOTICE 完整 | `Gi-Tuu/yai-scout` |
| README | 两轨映射、Quick start、在线 Demo、AI 使用说明 | 根 README |
| 在线 Demo | Render 地址 + 冷启动说明 | README / 视频 |
| 视频 | ≤4 分钟、英文字幕、含失败兜底 | YouTube/Drive 链接 |
| PPT | 10 页内、含架构图/指标/局限 | PDF 上传 |
| AI 使用说明 | 哪些环节用 AI、哪些是确定性代码 | README + PPT |
| 复现 | 测试命令、Docker、release tag | README/Release |

## 4. 提交前检查（Go/No-Go）

- [ ] `main` 与 release tag 一致；CI（3.11/3.12 + Docker）全绿
- [ ] 在线 Demo `/api/healthz` 200；`/benchmark`、`/freshness` 可打开
- [ ] 无密钥/隐私进入仓库、PPT、视频
- [ ] 两轨映射在 README、视频、PPT 三处一致
- [ ] 免责/局限写清楚（Wayback 不可达、隐藏题 compromised、数据集规模）
- [ ] 提交页截图 + 邮件确认存档
- [ ] 本地离线备份（源码 zip、视频、PPT）

## 5. 失败兜底

- 表单字段未更新 → 按方案 A 提交，材料已兼容；
- 平台崩溃/超时 → 提前 12h 提交，保留截图与邮件；
- 线上 Demo 冷启动 → 视频内说明 + 提前预热；
- 评委问隐藏题 → 直接说明"已公开历史泄露、标记 compromised，不宣称保密"。
