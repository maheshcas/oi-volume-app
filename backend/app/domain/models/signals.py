"""Domain models for trade signals, plans, and guidance."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class StrikeGuidance(BaseModel):
    """Recommended option strikes for entry."""

    call_strike: Optional[float] = None
    put_strike: Optional[float] = None
    atm_strike: Optional[float] = None
    direction: Optional[str] = None
    rationale: Optional[str] = None


class TradePlan(BaseModel):
    """High-level trade plan for the current market state."""

    action: Optional[str] = None
    entry_zone: Optional[str] = None
    stop_zone: Optional[str] = None
    target_zone: Optional[str] = None
    bias: Optional[str] = None
    confidence: Optional[float] = Field(None, ge=0, le=100)
    rationale: Optional[str] = None
    strike_guidance: Optional[StrikeGuidance] = None


class TradeSignal(BaseModel):
    """A single actionable trade signal emitted by the engine pipeline."""

    symbol: str
    expiry: Optional[str] = None
    signal_type: str
    direction: Optional[str] = None
    confidence: Optional[float] = Field(None, ge=0, le=100)
    spot_price: Optional[float] = None
    support: Optional[float] = None
    resistance: Optional[float] = None
    trap_probability: Optional[float] = Field(None, ge=0, le=100)
    plan: Optional[TradePlan] = None
    timestamp: Optional[str] = None
