"""Cached, budgeted discovery wrapper for anchor revalidation.

Purpose: admin-triggered revalidation must not burn Tavily credits on every
changed anchor. Cache by query, enforce a daily call budget; failures return
empty results and never crash revalidation.
"""

from __future__ import annotations

import time
from collections import OrderedDict
from collections.abc import Callable
from datetime import UTC, datetime

from ..retrieval.tavily import SearchResult
from .verify import Searcher


class CachedDiscovery:
    def __init__(
        self,
        searcher: Searcher,
        *,
        ttl_seconds: int = 3600,
        daily_budget: int = 50,
        max_cache_entries: int = 256,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.searcher = searcher
        self.ttl_seconds = max(0, ttl_seconds)
        self.daily_budget = max(0, daily_budget)
        self.max_cache_entries = max(1, max_cache_entries)
        self._clock = clock
        self._cache: OrderedDict[
            tuple[str, int | None], tuple[float, list[SearchResult], float]
        ] = OrderedDict()
        self._day = datetime.now(UTC).date().isoformat()
        self._calls = 0
        self._cache_hits = 0
        self._budget_denied = 0

    def _roll_day(self) -> None:
        today = datetime.now(UTC).date().isoformat()
        if today != self._day:
            self._day = today
            self._calls = 0
            self._cache_hits = 0
            self._budget_denied = 0

    async def search(
        self,
        query: str,
        *,
        depth: str | None = None,
        max_results: int | None = None,
    ) -> tuple[list[SearchResult], float]:
        self._roll_day()
        key = (query, max_results)
        cached = self._cache.get(key)
        now = self._clock()
        if cached and now - cached[0] <= self.ttl_seconds:
            self._cache_hits += 1
            self._cache.move_to_end(key)
            return cached[1], cached[2]
        if self._calls >= self.daily_budget:
            self._budget_denied += 1
            return [], 0.0
        try:
            results, credits = await self.searcher.search(
                query, depth=depth, max_results=max_results
            )
        except Exception:  # noqa: BLE001 - discovery is best-effort
            return [], 0.0
        self._calls += 1
        self._cache[key] = (now, results, credits)
        self._cache.move_to_end(key)
        while len(self._cache) > self.max_cache_entries:
            self._cache.popitem(last=False)
        return results, credits

    def usage(self) -> dict[str, int | str]:
        self._roll_day()
        return {
            "day": self._day,
            "calls": self._calls,
            "cache_hits": self._cache_hits,
            "budget_denied": self._budget_denied,
            "daily_budget": self.daily_budget,
            "ttl_seconds": self.ttl_seconds,
            "cache_size": len(self._cache),
            "max_cache_entries": self.max_cache_entries,
        }
