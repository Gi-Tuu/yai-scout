"""时间对比引擎：两份 Freshness 报告 → claim 级漂移报告。

注意：当前没有真实历史快照，跨 as_of 的对比只能标 `simulated`；
不代表"真实历史检索结果"，UI/报告必须显示该标记。
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

from ..domain.models import DetectorReport, FreshnessVerdict

NUMBER_RE = re.compile(r"\d[\d,\.]*")


class EvidenceChange(BaseModel):
    url: str
    change: Literal["content_changed", "kind_changed", "date_changed"]
    old_hash: str = ""
    new_hash: str = ""
    old_kind: str = ""
    new_kind: str = ""
    old_published_at: str | None = None
    new_published_at: str | None = None


class ClaimDiff(BaseModel):
    claim_key: str
    text_left: str = ""
    text_right: str = ""
    numbers_left: list[str] = Field(default_factory=list)
    numbers_right: list[str] = Field(default_factory=list)
    change: Literal["stable", "changed", "new", "removed"]
    status_left: str | None = None
    status_right: str | None = None
    freshness_delta: float | None = None
    evidence_added: list[str] = Field(default_factory=list)
    evidence_removed: list[str] = Field(default_factory=list)
    evidence_changes: list[EvidenceChange] = Field(default_factory=list)
    content_hash_changed: bool = False


class DriftReport(BaseModel):
    left_id: str
    right_id: str
    left_as_of: str
    right_as_of: str
    mode: Literal["live", "replay", "simulated"]
    diffs: list[ClaimDiff] = Field(default_factory=list)
    summary: dict[str, int] = Field(default_factory=dict)
    warning: str = ""


def claim_key(text: str) -> str:
    """把数字替换成占位符，让"同一事实不同值"落到同一个 key。

    Known limitation: period/quarter numbers are also removed, so two
    distinct facts can collide (e.g. "Q1 revenue 500" and "Q2 revenue 600").
    This key is kept for backward compatibility with existing anchors.
    """
    normalized = " ".join(text.lower().split())
    normalized = NUMBER_RE.sub("#", normalized)
    return normalized.strip("。 .")


def _evidence_urls(verdict: FreshnessVerdict | None) -> set[str]:
    if verdict is None:
        return set()
    return {item.url for item in verdict.evidence}


def compare_reports(left: DetectorReport, right: DetectorReport) -> DriftReport:
    left_verdicts = {v.claim_id: v for v in left.verdicts}
    right_verdicts = {v.claim_id: v for v in right.verdicts}
    left_map = {claim_key(c.text): c for c in left.claims}
    right_map = {claim_key(c.text): c for c in right.claims}
    keys = sorted(set(left_map) | set(right_map))

    diffs: list[ClaimDiff] = []
    summary = {"stable": 0, "changed": 0, "new": 0, "removed": 0}
    for key in keys:
        lc = left_map.get(key)
        rc = right_map.get(key)
        change: Literal["stable", "changed", "new", "removed"]
        if lc is None and rc is not None:
            change = "new"
        elif lc is not None and rc is None:
            change = "removed"
        elif lc is not None and rc is not None:
            change = "changed" if lc.numbers != rc.numbers else "stable"
        else:
            continue
        lv = left_verdicts.get(lc.id) if lc else None
        rv = right_verdicts.get(rc.id) if rc else None
        left_urls = _evidence_urls(lv)
        right_urls = _evidence_urls(rv)
        left_evidence = {item.url: item for item in (lv.evidence if lv else [])}
        right_evidence = {item.url: item for item in (rv.evidence if rv else [])}
        changes: list[EvidenceChange] = []
        for url in sorted(left_urls & right_urls):
            old = left_evidence[url]
            new = right_evidence[url]
            if (old.content_hash or new.content_hash) and old.content_hash != new.content_hash:
                changes.append(
                    EvidenceChange(
                        url=url,
                        change="content_changed",
                        old_hash=old.content_hash,
                        new_hash=new.content_hash,
                    )
                )
            elif old.evidence_kind is not new.evidence_kind:
                changes.append(
                    EvidenceChange(
                        url=url,
                        change="kind_changed",
                        old_kind=old.evidence_kind.value,
                        new_kind=new.evidence_kind.value,
                    )
                )
            elif old.published_at != new.published_at:
                changes.append(
                    EvidenceChange(
                        url=url,
                        change="date_changed",
                        old_published_at=old.published_at,
                        new_published_at=new.published_at,
                    )
                )
        left_score = lv.score if lv and lv.score is not None else None
        right_score = rv.score if rv and rv.score is not None else None
        delta = (
            round(float(right_score) - float(left_score), 1)
            if left_score is not None and right_score is not None
            else None
        )
        diffs.append(
            ClaimDiff(
                claim_key=key,
                text_left=lc.text if lc else "",
                text_right=rc.text if rc else "",
                numbers_left=list(lc.numbers) if lc else [],
                numbers_right=list(rc.numbers) if rc else [],
                change=change,
                status_left=lv.status.value if lv else None,
                status_right=rv.status.value if rv else None,
                freshness_delta=delta,
                evidence_added=sorted(right_urls - left_urls),
                evidence_removed=sorted(left_urls - right_urls),
                evidence_changes=changes,
                content_hash_changed=any(
                    item.change == "content_changed" for item in changes
                ),
            )
        )
        summary[change] += 1

    if left.mode == "replay" and right.mode == "replay":
        mode: Literal["live", "replay", "simulated"] = "replay"
        warning = "历史对比基于真实快照（GitHub Releases 官方历史），证据时间可追溯。"
    elif left.as_of != right.as_of:
        mode = "simulated"
        warning = "历史对比为模拟时间场景（无真实历史快照），不代表当时的真实检索结果。"
    else:
        mode = "live"
        warning = ""
    return DriftReport(
        left_id=left.id,
        right_id=right.id,
        left_as_of=left.as_of,
        right_as_of=right.as_of,
        mode=mode,
        diffs=diffs,
        summary=summary,
        warning=warning,
    )


