from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
import asyncio


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class OptionLensCache:
    """
    Process-local async-safe cache.
    Lock protects concurrent read/write and fetch-state transitions.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self.last_update: datetime | None = None
        self.option_chain_data: dict[str, Any] = {}
        self.summary_data: dict[str, Any] = {}
        self.last_successful_fetch: datetime | None = None
        self.is_fetching: bool = False
        self.stale_data: bool = True
        self.metrics: dict[str, Any] = {
            "fetch_count": 0,
            "last_fetch_latency_ms": None,
            "last_error": None,
        }
        self.previous_scores: dict[str, float] = {}
        self.score_history: dict[str, list[float]] = {}
        self.previous_states: dict[str, Any] = {}

    async def get_cached_data(self, *, include_internal: bool = False) -> dict[str, Any]:
        async with self._lock:
            payload = {
                "last_update": self.last_update,
                "option_chain_data": deepcopy(self.option_chain_data),
                "summary_data": deepcopy(self.summary_data),
                "last_successful_fetch": self.last_successful_fetch,
                "is_fetching": self.is_fetching,
                "stale_data": self.stale_data,
                "metrics": deepcopy(self.metrics),
            }
            if include_internal:
                payload["previous_scores"] = deepcopy(self.previous_scores)
                payload["score_history"] = deepcopy(self.score_history)
                payload["previous_states"] = deepcopy(self.previous_states)
            return payload

    async def update_cache(self, new_option_chain: dict[str, Any], new_summary: dict[str, Any]) -> None:
        now = utc_now()
        async with self._lock:
            self.option_chain_data = deepcopy(new_option_chain)
            self.summary_data = deepcopy(new_summary)
            self.last_update = now
            self.last_successful_fetch = now
            self.stale_data = False

    async def get_last_update_time(self) -> datetime | None:
        async with self._lock:
            return self.last_update

    async def get_previous_score(self, key: str) -> float | None:
        async with self._lock:
            value = self.previous_scores.get(key)
            return float(value) if value is not None else None

    async def set_previous_score(self, key: str, score: float) -> None:
        async with self._lock:
            self.previous_scores[key] = float(score)

    async def get_score_history(self, key: str, limit: int = 10) -> list[float]:
        async with self._lock:
            values = self.score_history.get(key, [])
            return [float(v) for v in values[-max(1, int(limit)) :]]

    async def append_score_history(self, key: str, score: float, maxlen: int = 200) -> None:
        async with self._lock:
            values = self.score_history.get(key, [])
            values.append(float(score))
            if len(values) > maxlen:
                values = values[-maxlen:]
            self.score_history[key] = values

    async def get_previous_state(self, key: str) -> Any:
        async with self._lock:
            return deepcopy(self.previous_states.get(key))

    async def set_previous_state(self, key: str, state: Any) -> None:
        async with self._lock:
            self.previous_states[key] = deepcopy(state)

    async def begin_fetch(self) -> bool:
        """
        Returns False if a fetch is already running; True when caller acquired fetch ownership.
        """
        async with self._lock:
            if self.is_fetching:
                return False
            self.is_fetching = True
            return True

    async def end_fetch(self) -> None:
        async with self._lock:
            self.is_fetching = False

    async def mark_fetch_success(self, latency_ms: float) -> None:
        now = utc_now()
        async with self._lock:
            self.metrics["fetch_count"] = int(self.metrics.get("fetch_count", 0) or 0) + 1
            self.metrics["last_fetch_latency_ms"] = round(float(latency_ms), 2)
            self.metrics["last_error"] = None
            self.last_successful_fetch = now
            self.last_update = now
            self.stale_data = False

    async def mark_fetch_failure(self, error: str) -> None:
        async with self._lock:
            self.metrics["last_error"] = error
            self._recompute_stale_locked()

    async def recompute_stale(self, stale_after_seconds: int = 60) -> bool:
        async with self._lock:
            self._recompute_stale_locked(stale_after_seconds=stale_after_seconds)
            return self.stale_data

    def _recompute_stale_locked(self, stale_after_seconds: int = 60) -> None:
        if not self.last_successful_fetch:
            self.stale_data = True
            return
        age_seconds = (utc_now() - self.last_successful_fetch).total_seconds()
        self.stale_data = age_seconds > stale_after_seconds


cache = OptionLensCache()
