# Final Submission Checklist — 必须项

> 项目：YAI Scout · Tavily Track **Problem 05**（track-local Tavily-01）  
> 截止：**2026-11-15 23:59 IST**（北京 2026-11-16 02:29）  
> 当前：`v0.3.6` · build `69b24e5161fd` · 202 tests · CI/CodeQL 绿

## 1. 只交这 5 样

- [ ] **GitHub 仓库**：<https://github.com/Gi-Tuu/yai-scout>
- [ ] **可访问 Demo**：<https://yai-scout.onrender.com/freshness>
- [ ] **3 分钟视频**：公开/不列出链接（YouTube/Drive）
- [ ] **提交表单**：选择题号 **05**，填 repo/demo/video
- [ ] **最终提交确认**：11/15 前收到确认

## 2. 视频必须拍到（3 分钟）

- [ ] 同一个 YAI `0.24.0` 答案：
  - `as_of=2026-10-28` → FRESH
  - `as_of=2026-11-01` → STALE
- [ ] 粘贴答案 → claim → Tavily 证据 → 每 claim 状态 + 修正
- [ ] **Bifrost 本地证明**：`healthz gateway=bifrost` + Bifrost 日志 `POST /v1/chat/completions 200`
- [ ] 架构一句话：Tavily 研究 / Bifrost 模型网关 / 确定性代码判定
- [ ] repo 页面 + 限制说明（不吹独立准确率）

## 3. Repo 必须具备

- [ ] `README.md`：项目是什么、怎么跑、架构、Tavily/Bifrost 角色
- [ ] `docs/track-tavily.md`：Tavily 05 映射
- [ ] `docs/submission.md`：官方要求 → 证据
- [ ] `docs/bifrost-integration.md`：本地接入方式
- [ ] setup：`uv sync` / `.env.example` / Docker
- [ ] 测试/演示命令可跑

## 4. 提交表单只写这些

- **Primary problem**：Problem 05 — Stale-answer detector
- **Tavily**：实时检索、逐 claim 证据
- **Bifrost**：claim 抽取/判定/改写的模型网关
- **Demo**：固定 case + 线上链接
- **Repository**：GitHub URL
- **Video**：视频 URL
- **Limitations**：公开 Render 为 direct fallback；Bifrost 在本地视频验证；`AUTO_UPDATE=false`

## 5. 最后 30 分钟检查

```powershell
# 线上版本
curl https://yai-scout.onrender.com/api/healthz
# "version":"0.3.6"

# 本地
.\.venv\Scripts\python.exe -m pytest -q        # 202 passed
.\.venv\Scripts\python.exe -m ruff check src tests scripts examples
.\.venv\Scripts\python.exe -m mypy
```

- [ ] Demo 打开不白屏，冷启动可接受
- [ ] 视频链接无权限墙
- [ ] 表单题号是 **05**，不是 Tavily 第 5 题
- [ ] 不写“独立人工验证通过”“公开 Demo 走 Bifrost”
- [ ] `AUTO_UPDATE` 保持 false
- [ ] 提交后保存确认截图/邮件

## 6. 明确不做（提交前）

- 不再找人标 30 题；
- 不打开自动更新；
- 不追 P2 新功能；
- 不改 Gate 阈值迎合标签；
- 不把 benchmark 当第二项目提交。
