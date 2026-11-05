"""Concurrency guards for long-lived SSE streams."""

from __future__ import annotations

from threading import Lock


class StreamLimiter:
    def __init__(self, *, max_total: int, max_per_key: int) -> None:
        self.max_total = max(1, max_total)
        self.max_per_key = max(1, max_per_key)
        self._lock = Lock()
        self._active: dict[str, int] = {}
        self._total = 0

    def acquire(self, key: str) -> bool:
        with self._lock:
            if self._total >= self.max_total:
                return False
            if self._active.get(key, 0) >= self.max_per_key:
                return False
            self._active[key] = self._active.get(key, 0) + 1
            self._total += 1
            return True

    def release(self, key: str) -> None:
        with self._lock:
            count = self._active.get(key, 0)
            if count <= 0:
                return
            if count == 1:
                self._active.pop(key, None)
            else:
                self._active[key] = count - 1
            self._total = max(0, self._total - 1)

    def usage(self) -> dict[str, int]:
        with self._lock:
            return {
                "active": self._total,
                "max_total": self.max_total,
                "max_per_key": self.max_per_key,
            }
