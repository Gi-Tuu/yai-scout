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
        self._last_sweep = time.monotonic()

    def _roll_day(self) -> None:
        today = datetime.now(UTC).date().isoformat()
        if today != self._day:
            self._day = today
            self._daily_used = {bucket: 0 for bucket in BUCKETS}
            self._events.clear()
            self._global_events.clear()
            self._last_sweep = time.monotonic()

    def _sweep(self, now: float) -> None:
        """Drop per-client buckets whose last event is outside the window."""
        if now - self._last_sweep < 60.0:
            return
        cutoff = now - 60.0
        stale = [
            key for key, events in self._events.items()
            if not events or events[-1] <= cutoff
        ]
        for key in stale:
            del self._events[key]
        self._last_sweep = now

    def check(self, bucket: str, client: str) -> tuple[bool, int]:
        """返回 (allowed, retry_after_seconds)。允许时同时记账。"""
        if bucket not in self.daily:
            raise ValueError(f"unknown bucket: {bucket}")
        now = time.monotonic()
        with self._lock:
            self._roll_day()
            self._sweep(now)
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
                "buckets": len(self._events),
            }

    @staticmethod
    def client_key(
        headers: dict[str, str], fallback: str, *, trust_proxy: bool = True
    ) -> str:
        """Resolve the client IP behind the Render/Cloudflare proxy.

        Cloudflare supplies authoritative client-IP headers. Using the last
        X-Forwarded-For hop alone is wrong here: the chain ends in an internal
        Render address, so every client would share the same rate-limit bucket.
        """
        if not trust_proxy:
            return fallback or "unknown"
        lowered = {key.lower(): value for key, value in headers.items()}
        for name in ("cf-connecting-ip", "true-client-ip"):
            value = str(lowered.get(name, "")).strip()
            if value:
                return value
        forwarded = lowered.get("x-forwarded-for", "")
        if forwarded:
            # Fallback for direct/proxy deployments without Cloudflare headers.
            last = forwarded.split(",")[-1].strip()
            if last:
                return last
        return fallback or "unknown"



