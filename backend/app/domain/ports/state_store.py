"""Port interface — market state store.

Abstracts over the in-memory cache so the application layer is not coupled
to the concrete OptionLensCache implementation.
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class IStateStore(Protocol):
    """Read/write contract for the market state cache."""

    async def get_cached_data(self) -> dict[str, Any]:
        """Return the full cached payload (option_chain_data + summary_data)."""
        ...

    async def update_cache(
        self,
        option_chain_data: dict[str, Any],
        summary_data: dict[str, Any],
    ) -> None:
        """Atomically replace cached market data."""
        ...

    async def get_previous_state(self, key: str) -> dict[str, Any] | None:
        """Return the last persisted state snapshot for a stream key."""
        ...

    async def set_previous_state(self, key: str, state: dict[str, Any]) -> None:
        """Persist a new state snapshot for a stream key."""
        ...
