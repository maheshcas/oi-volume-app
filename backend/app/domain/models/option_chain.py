"""Domain models for raw option chain data."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class StrikeRow(BaseModel):
    """One strike row from the option chain (CE + PE combined)."""

    strike: float
    ce_oi: int = 0
    pe_oi: int = 0
    ce_change_oi: int = 0
    pe_change_oi: int = 0
    ce_volume: int = 0
    pe_volume: int = 0
    ce_ltp: float = 0.0
    pe_ltp: float = 0.0
    ce_iv: float = 0.0
    pe_iv: float = 0.0


class OptionChainSnapshot(BaseModel):
    """Normalised option chain for one symbol/expiry at a point in time."""

    symbol: str
    expiry: str
    spot_price: float
    timestamp: str
    strikes: list[StrikeRow] = Field(default_factory=list)
    total_ce_oi: int = 0
    total_pe_oi: int = 0
    total_ce_volume: int = 0
    total_pe_volume: int = 0

    @property
    def pcr(self) -> Optional[float]:
        """Put-Call Ratio by OI."""
        return (self.total_pe_oi / self.total_ce_oi) if self.total_ce_oi > 0 else None
