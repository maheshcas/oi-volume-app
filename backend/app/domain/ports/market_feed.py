"""Port interface — market data feed.

Any class implementing this Protocol can be used as a market data source.
The infrastructure layer (NSE, BSE adapters) implements these methods.
"""
from __future__ import annotations

from typing import Any, Optional, Protocol, runtime_checkable


@runtime_checkable
class IMarketFeed(Protocol):
    """Abstract contract for fetching live market data."""

    def fetch_option_chain(
        self,
        symbol: str,
        expiry: Optional[str] = None,
        instrument_type: str = "Indices",
    ) -> dict[str, Any]:
        """Return raw option chain data for the given symbol/expiry."""
        ...

    def fetch_contract_info(self, symbol: str) -> dict[str, Any]:
        """Return available expiry dates and strike prices."""
        ...

    def fetch_index_data(self) -> dict[str, Any]:
        """Return live index spot prices."""
        ...
