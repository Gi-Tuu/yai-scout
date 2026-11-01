# 依赖与复用登记（YAI Agent Core）

> 目的：满足 Charter §5.1「记录复用版本与 commit SHA」、许可证合规与可复现构建。
> 最后更新：2026-11-01

## YAI Agent Core（唯一复用的外部 Agent 内核）

| 项目 | 值 |
|---|---|
| 包名 | `yai-agent-core` |
| 版本 | **0.25.0** |
| 发布点 | PyPI 0.25.0 ↔ Git tag `v0.25.0` → commit **`614f3106c7237b8bee662b925748b56c4da6d890`** |
| 审计时仓库 HEAD | `ce4773d67c6ee658c32c6559c91d02aa10dab18d`（tag 后 4 个提交，含 pypdf 升级；**不是** 0.25.0，未使用） |
| 许可证 | MIT（保留版权与许可声明） |
| Python | >=3.11（本项目用 3.12） |
| 依赖方式 | **PyPI 钉死**：`pyproject.toml` → `"yai-agent-core==0.25.0"`；`uv.lock` 锁定 |
| 当前启用的 extras | 无（G0 只 import 顶层符号与 `spi.ModelProvider`） |
| 计划启用的 extras | `[llm,server,openapi,mcp,otel]`（用到哪个开哪个，内核本体零第三方硬依赖） |
| 安装位置 | `.venv/Lib/site-packages/yai_core`（仓库内**没有**任何 YAI 源码副本） |
| 一致性校验 | 已用 `git hash-object` 对比：PyPI 0.25.0 的 `__init__.py` / `types.py` / `core.py` / `config.py` / `kernel/loop.py` / `spi/model.py` / `batteries/fastapi_server/app.py` 与本地仓库 tag `v0.25.0` **逐字节一致**；tag 与 HEAD 的差异仅 `docs/IMPLEMENTATION_STATUS.md` 与 `uv.lock`（代码无差异） |
| 接入面 | 仅 `src/yai_scout/kernel/yai_adapter.py`（约 50 行，只 import `__all__` 公共符号 + `spi.ModelProvider`） |
| 未修改主仓库 | 是。`E:\Competition\YAI Agent Core` 只读审计；其 3 个未提交改动为本项目开始前既有，与本项目无关 |

### 为什么用依赖而不是 copy 源码

1. **可复现**：版本 + `uv.lock` 锁定，任何人 `uv sync` 得到同一份代码；copy 会变成"某天的快照"，无法追溯。
2. **不污染、不修改上游**：符合"不直接修改 YAI 主仓库"的要求。
3. **许可证与边界干净**：MIT 声明随包分发；Scout 自研部分（证据台账 / 验证 / 报告）与内核边界清晰。
4. **升级隔离**：0.x 迭代快（3 周 0.8→0.25），只改 `yai_adapter.py` + 跑契约测试即可升级。
5. **赛事规则友好**：既有库可复用，但"核心项目赛期内开发"——我们复用的是内核，自研的是研究流水线与证据层。

### 什么情况下才需要 copy / 改安装源

| 场景 | 做法 | 是否建议 |
|---|---|---|
| 需要 `shell/employee` 委托薄壳（**不在 wheel 里**，只在 sdist） | `yai-agent-core @ git+https://github.com/Gi-Tuu/yai-agent-core.git@<tag-sha>` | 不建议；Director 自己控并发，不需要子员工 |
| PyPI 不可用 / 需要完全离线构建 | `uv sync --offline`（依赖本机 uv 缓存）；或预先 `uv pip download` 存 wheel | 可选（评审现场有网则不需要） |
| 要改内核行为 | 先在上游提 issue；确需本地改则 fork 并记录 diff | 不建议（会破坏"不修改主仓库"叙述） |

## 其他运行时依赖

| 包 | 版本约束 | 用途 | 许可证 |
|---|---|---|---|
| `fastapi` | >=0.115 | HTTP / SSE | MIT |
| `starlette` | （fastapi 传递） | ASGI | BSD-3-Clause |
| `uvicorn[standard]` | >=0.30 | ASGI server | BSD-3-Clause |
| `pydantic` / `pydantic-settings` | >=2.7 / >=2.4 | 模型与配置 | MIT |
| `httpx` | >=0.27 | Tavily REST + 测试 MockTransport | BSD-3-Clause |

**开发依赖**：pytest（MIT）、pytest-asyncio（Apache-2.0）、ruff（MIT）、mypy（MIT）。

**明确排除**：GPL / AGPL / BSL（例如 Pathway 为 BSL 1.1，不在产品代码中使用）。

## 可复现构建

```powershell
uv sync --frozen --extra dev     # 严格按 uv.lock 安装
uv run pytest -q
```

升级流程：改 `pyproject.toml` → `uv lock` → 跑 `tests/`（尤其 `tests/test_kernel.py` 契约测试）→ 更新本文件 → 提交。
