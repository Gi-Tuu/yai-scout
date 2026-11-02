"""公开 Demo 的成本/速率保护（单进程内存实现）。

用途：公开 URL 暴露了 Tavily/LLM key，必须限制单 IP 突发与全局日调用量；
Render 单实例场景下内存计数足够，重启清零（可接受，且在文档中说明）。
"""

from __future__ import annotations

import time
from collections import deque
from datetime import UTC, datetime, timedelta
from threading import Lock

BUCKETS = ("detector", "benchmark", "anchor", "research")


class UsageLimiter:
    def __init__(
        self,
        *,
        per_minute: int,
        daily: dict[str, int],
    ) -> None:
        self.per_minute = max(1, per_minute)
        self.daily = {bucket: max(1, daily.get(bucket, 1)) for bucket in BUCKETS}
        self._events: dict[tuple[str, str], deque[float]] = {}
        self._global_events: deque[float] = deque()
        self._day = datetime.now(UTC).date().isoformat()
        self._daily_used: dict[str, int] = {bucket: 0 for bucket in BUCKETS}
        self._lock = Lock()

    def _roll_day(self) -> None:
        today = datetime.now(UTC).date().isoformat()
        if today != self._day:
            self._day = today
            self._daily_used = {bucket: 0 for bucket in BUCKETS}
            self._events.clear()
            self._global_events.clear()

    def check(self, bucket: str, client: str) -> tuple[bool, int]:
        """返回 (allowed, retry_after_seconds)。允许时同时记账。"""
        if bucket not in self.daily:
            raise ValueError(f"unknown bucket: {bucket}")
        now = time.monotonic()
        with self._lock:
            self._roll_day()
            if self._daily_used[bucket] >= self.daily[bucket]:
                tomorrow = datetime.now(UTC) + timedelta(days=1)
                midnight = datetime(
                    tomorrow.year, tomorrow.month, tomorrow.day, tzinfo=UTC
                )
                retry = int((midnight - datetime.now(UTC)).total_seconds())
                return False, max(1, retry)
            cutoff = now - 60.0
            while self._global_events and self._global_events[0] <= cutoff:
                self._global_events.popleft()
            if len(self._global_events) >= self.per_minute:
                retry = int(self._global_events[0] + 60.0 - now) + 1
                return False, max(1, retry)
            key = (bucket, client)
            events = self._events.setdefault(key, deque())
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= self.per_minute:
                retry = int(events[0] + 60.0 - now) + 1
                return False, max(1, retry)
            events.append(now)
            self._global_events.append(now)
            self._daily_used[bucket] += 1
        return True, 0

    def usage(self) -> dict[str, object]:
        with self._lock:
            self._roll_day()
            return {
                "day": self._day,
                "per_minute": self.per_minute,
                "daily_limit": dict(self.daily),
                "daily_used": dict(self._daily_used),
            }

    @staticmethod
    def client_key(headers: dict[str, str], fallback: str) -> str:
        """Render/代理场景取 X-Forwarded-For 第一个地址。"""
        forwarded = headers.get("x-forwarded-for", "")
        if forwarded:
            first = forwarded.split(",")[0].strip()
            if first:
                return first
        return fallback or "unknown"



