"""基于已存快照的检索器：用于真实历史回放（replay）。

只读本地 `snapshot` 表，不访问互联网；`target_time` 之后的快照不会被使用。
这是"没有 Wayback 时仍不伪造历史"的实现路径：证据全部来自已保存的真实快照。
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import UTC, datetime

from ..domain.models import EvidenceSnapshot
from ..retrieval.tavily import SearchResult
from ..sources.snapshot import resolve_snapshot_path, snapshot_eligible
from ..store import Store

TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9\.\-]{1,}|[\u4e00-\u9fff]{2,}|\d+(?:\.\d+)+")
SENTENCE_SPLIT = re.compile(r"(?<=[。！？.!?])\s*|\n+")
STOPWORDS = {
    "release",
    "version",
    "name",
    "url",
    "notes",
    "published_at",
    "latest",
    "official",
    "2026",
    "the",
    "and",
    "for",
    "with",
}


def _tokens(text: str) -> set[str]:
    tokens: set[str] = set()
    for match in TOKEN_RE.findall(text):
        token = match.lower()
        tokens.add(token)
        for part in re.split(r"[-_.]", token):
            if len(part) >= 2:
                tokens.add(part)
    return tokens


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt


class SnapshotSearcher:
    """在本地快照中按关键词检索；返回 SearchResult（published_date = 快照时间）。"""

    def __init__(
        self, store: Store, *, target_time: str | None = None, max_chars: int = 400
    ) -> None:
        self.store = store
        self.target_time = target_time
        self.max_chars = max_chars

    def _candidates(self, target_time: str | None) -> Iterator[EvidenceSnapshot]:
        target = _parse_time(target_time) if target_time else None
        offset = 0
        while True:
            page = self.store.list_snapshots_page(offset=offset, limit=500)
            if not page:
                return
            for snapshot in page:
                if target is None:
                    yield snapshot
                    continue
                if snapshot_eligible(snapshot, target):
                    yield snapshot
            offset += len(page)

    async def search(
        self,
        query: str,
        *,
        depth: str | None = None,
        max_results: int | None = None,
    ) -> tuple[list[SearchResult], float]:
        query_tokens = _tokens(query) - STOPWORDS
        limit = max_results or 4
        results: list[SearchResult] = []
        for snapshot in self._candidates(self.target_time):
            try:
                text = resolve_snapshot_path(
                    self.store, snapshot.text_path
                ).read_text(encoding="utf-8")
            except OSError:
                continue
            url_overlap = len(query_tokens & (_tokens(snapshot.url) - STOPWORDS))
            if url_overlap == 0 and not query_tokens:
                continue
            best = ""
            best_score = 0.0
            for sentence in SENTENCE_SPLIT.split(text):
                sentence = " ".join(sentence.split())
                if not sentence:
                    continue
                overlap = len(query_tokens & (_tokens(sentence) - STOPWORDS))
                if overlap > best_score:
                    best_score = float(overlap)
                    best = sentence
            total_score = best_score + 2.0 * url_overlap
            if total_score == 0 or (url_overlap == 0 and best_score < 2):
                continue  # 与 claim 主题无关的快照不能当证据
            if not best and text:
                best = text[: self.max_chars]
            head = text[:160]
            content = best if head in best else f"{head} {best}"
            if best:
                results.append(
                    SearchResult(
                        title=f"{snapshot.title or snapshot.url}",
                        url=snapshot.url,
                        content=content[: self.max_chars],
                        score=min(1.0, total_score / 6.0),
                        published_date=snapshot.published_at,
                    )
                )
            if len(results) >= limit:
                break
        return results, 0.0





