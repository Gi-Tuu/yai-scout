"""Freshness 策略与权重的单一版本来源。

任何影响判定/分数的规则变更都必须提升对应版本号，并在报告中记录实际执行版本。
历史报告读取时缺失版本字段应保持 `unknown`，不得用当前版本回填。
"""

from __future__ import annotations

POLICY_VERSION = "2026-11-01"
WEIGHTS_VERSION = "rubric-v2-calibrated"
UNKNOWN_VERSION = "unknown"
