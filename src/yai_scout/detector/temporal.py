"""Temporal Sensitivity 分类（规则版，输出可解释理由）。

四档与默认有效期窗口：
STABLE 3650 天 / SLOW 730 / SENSITIVE 180 / VOLATILE 30。
LLM 只做兜底分类，不允许改分数。
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from ..domain.models import Claim, ClaimType, TemporalSensitivity

POLICY_VERSION = "2026-11-01"
DEFAULT_WINDOWS: dict[TemporalSensitivity, int] = {
    TemporalSensitivity.STABLE: 3650,
    TemporalSensitivity.SLOW: 730,
    TemporalSensitivity.SENSITIVE: 180,
    TemporalSensitivity.VOLATILE: 30,
}

VOLATILE_RE = re.compile(
    r"排名|榜单|股价|市值|实时|当前人数|最新排名|latest ranking|stock price", re.I
)
CURRENT_RE = re.compile(r"当前|目前|现在|最新|截至|current|latest|now", re.I)
STABLE_RE = re.compile(
    r"定理|定律|常数|公式|历史事件|已于|成立于|theorem|constant|definition", re.I
)
MATH_RE = re.compile(r"等于多少|换算|公里|英里|千米|数学|物理", re.I)
PAST_DATE_RE = re.compile(r"(19|20)\d{2}\s*年")
PAST_RELEASE_RE = re.compile(
    r"(?:19|20)\d{2}\s*年[^。；;]{0,20}(?:发布|成立|推出|上线)"
    r"|(?:发布|成立|推出|上线)[^。；;]{0,20}(?:19|20)\d{2}\s*年"
)


def _parse_time(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC)
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return datetime.now(UTC)
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt


def classify_temporal(
    claim: Claim, *, target_time: str | None = None
) -> tuple[TemporalSensitivity, int, list[str]]:
    """返回 (sensitivity, validity_window_days, reasons)。"""
    text = claim.text
    reasons: list[str] = []
    target_dt = _parse_time(target_time or claim.target_time)

    if VOLATILE_RE.search(text):
        sensitivity = TemporalSensitivity.VOLATILE
        reasons.append("含排名/股价/实时类信号")
    elif PAST_RELEASE_RE.search(text) and not CURRENT_RE.search(text):
        sensitivity = TemporalSensitivity.STABLE
        reasons.append("过去年份的发布/成立事实")
    elif STABLE_RE.search(text):
        sensitivity = TemporalSensitivity.STABLE
        reasons.append("含定理/常数/历史事件等稳定信号")
    elif MATH_RE.search(text):
        sensitivity = TemporalSensitivity.STABLE
        reasons.append("数学/换算类事实")
    elif claim.type is ClaimType.DATE:
        years = [int(y) for y in PAST_DATE_RE.findall(text)]
        if years and max(years) < target_dt.year and not CURRENT_RE.search(text):
            sensitivity = TemporalSensitivity.STABLE
            reasons.append("指向过去的确定日期")
        else:
            sensitivity = TemporalSensitivity.SENSITIVE
            reasons.append("日期类，需要时效判断")
    elif claim.type is ClaimType.PRICING or claim.type is ClaimType.VERSION:
        sensitivity = TemporalSensitivity.SENSITIVE
        reasons.append("价格/版本类，变化频率高")
    elif claim.type is ClaimType.STATISTIC:
        sensitivity = TemporalSensitivity.SENSITIVE
        reasons.append("统计数字，通常按季度更新")
    elif claim.type is ClaimType.LAW:
        if CURRENT_RE.search(text):
            sensitivity = TemporalSensitivity.SENSITIVE
            reasons.append("法规且含'最新/生效'限定")
        else:
            sensitivity = TemporalSensitivity.SLOW
            reasons.append("法规框架，变化较慢")
    elif claim.type is ClaimType.LEADERSHIP:
        sensitivity = TemporalSensitivity.SLOW
        reasons.append("人事类，变化较慢但会变")
    else:
        sensitivity = TemporalSensitivity.SENSITIVE
        reasons.append("默认保守：需要核验")

    return sensitivity, DEFAULT_WINDOWS[sensitivity], reasons


def apply_temporal_classification(claim: Claim, *, target_time: str | None = None) -> Claim:
    """就地返回带 target_time / sensitivity / window 的 claim 副本。"""
    effective_target = target_time or claim.target_time
    sensitivity, window, _ = classify_temporal(claim, target_time=effective_target)
    return claim.model_copy(
        update={
            "target_time": effective_target,
            "temporal_sensitivity": sensitivity,
            "validity_window_days": window,
        }
    )
