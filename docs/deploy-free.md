# 免费在线 Demo 部署指南

> 目标：**$0** 拿到一个评委可访问的 URL，不绑卡、不买域名。
> 结论先说：**主用 Render 免费 Web Service；备用 Hugging Face Docker Space；临时演示用 Cloudflare Tunnel。**

## 0. 三种免费路径对比

| 方案 | 费用 | 需要信用卡 | 冷启动 | 公网访问 | 适合 |
|---|---|---|---|---|---|
| **Render Free Web Service**（Docker） | $0 | 通常不需要（以注册页为准） | 休眠后 30–90s | 稳定子域名 `*.onrender.com` | **主 Demo** |
| **Hugging Face Docker Space** | $0 | 不需要 | 休眠后 30–60s | `*.hf.space`，国内访问可能不稳 | 备用 |
| **Cloudflare Quick Tunnel** | $0 | 不需要 | 无 | 随机 `*.trycloudflare.com`，每次重启变 | 临时演示/录视频 |
| GitHub Codespaces（补充） | 免费额度 60h/月 | 不需要 | 无 | 端口可设为 Public | 开发/临时 |

> 三者都**不要**提交 `.env`；key 一律走平台 Secrets。

## 1. Render（推荐，10 分钟）

仓库已带 [`render.yaml`](../render.yaml)（Blueprint：Docker、free plan、`/api/healthz` 健康检查）。

### 步骤

1. 打开 https://render.com ，用 **GitHub 登录**（不需要先绑卡）。
2. **New → Blueprint** → 选择 `Gi-Tuu/yai-scout` → Apply。
3. 在创建页面填环境变量（Secrets）：
   - `TAVILY_API_KEY` = 你的 key
   - `OPENAI_API_KEY` = 你的 DeepSeek/suanli key
   - `OPENAI_BASE_URL` = `https://api.suanli.cn/v1`
   - `LLM_MODEL` = `deepseek/deepseek-v4.1-flash-1017`
4. 首次构建约 3–6 分钟；成功后地址形如 `https://yai-scout.onrender.com`。
5. 验证：`https://<你的域名>/api/healthz` 返回 `{"status":"ok",...}`，再打开 `/benchmark`、`/freshness`。

### 注意

- **免费层会休眠**（15 分钟无请求）；下次访问冷启动 30–90s。演示前 2 分钟打开一次预热。
- 磁盘是临时的：SQLite、快照重启即丢；live 模式不受影响，replay 需要现场重新抓快照。
- 750 实例小时/月，够用；不要跑 24/7 压测。
- 如果注册时被要求绑卡：直接换 Hugging Face 方案，不要为 Demo 绑卡。

### 可选：保活

用免费的 uptime 监控（UptimeRobot / cron-job.org）每 10 分钟请求一次 `/api/healthz`。
用途：避免评审时冷启动；代价是占用免费实例小时（约 720h/月，仍在 750h 内，但请自行确认平台条款）。

## 2. Hugging Face Docker Space（备用，15 分钟）

仓库已带模板：[`deploy/huggingface/`](../deploy/huggingface/)。

1. 登录 https://huggingface.co → **New Space** → SDK 选 **Docker** → 免费 CPU。
2. 在 Space 仓库里放这两个文件：`deploy/huggingface/Dockerfile`、`deploy/huggingface/README.md`（Dockerfile 会在构建时 clone 公开 GitHub 仓库）。
3. **Settings → Variables and secrets** 加同样的四个变量（两个 secret）。
4. 等待 Build 完成，访问 `https://<user>-<space>.hf.space`。

注意：
- 国内直连 `hf.space` 可能不稳定；评委在海外通常没问题。
- 免费 Space 空闲后会休眠；首次请求慢。
- 不要在 Space 里写 key 到文件，只用 Secrets。

## 3. Cloudflare Quick Tunnel（零部署，立刻有 URL）

```powershell
# 1) 本地起服务
.\.venv\Scripts\python.exe -m uvicorn yai_scout.api.app:app --host 127.0.0.1 --port 8010

# 2) 另开一个终端，下载 cloudflared（只需一次）
#    https://github.com/cloudflare/cloudflared/releases/latest → cloudflared-windows-amd64.exe
./cloudflared.exe tunnel --url http://127.0.0.1:8010
```

会输出 `https://xxxx.trycloudflare.com`。

注意：
- 电脑必须保持开机、网络稳定；URL 每次重启都会变。
- 公开 URL = 任何人都能调用你的 key；演示完立即 Ctrl+C 关闭。
- 适合：录 Demo 视频、评审当天临时演示；不适合作为长期提交链接。

## 4. Key 与成本安全

- 免费 Tavily 1,000 credits/月、DeepSeek 按量；公开 Demo 可能被滥用。
- 建议：
  1. 用单独的低额度 key（不要用主 key）；
  2. 设置预算上限（代码里已有 `MAX_TAVILY_CREDITS` 等环境变量，可在平台 Secrets 里覆盖）；
  3. 演示结束后轮换 key；
  4. 不把 key 写进 README/Release/视频。
- 本次提交的材料里只写"在线 Demo：<URL>"，不写 key。

## 5. 演示前检查清单

- [ ] `/api/healthz` 200，`tavily: key`、`llm: true`
- [ ] `/benchmark` 能跑 1 次 3 Agent × 2 题
- [ ] `/freshness` 能检测 1 段答案并出证据
- [ ] 预热一次（避免冷启动）
- [ ] 备用录屏已下载到本地
