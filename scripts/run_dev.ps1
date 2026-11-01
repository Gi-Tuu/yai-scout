# 开发服务器：激活 venv 并启动 uvicorn（热重载）
param([int]$Port = 8010)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
$py = Join-Path (Get-Location) ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { throw "未找到 .venv，请先运行: uv sync --extra dev" }

& $py -m uvicorn yai_scout.api.app:app --host 127.0.0.1 --port $Port --reload

