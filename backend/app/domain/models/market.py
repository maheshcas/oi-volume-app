"""Domain models for market state — bias, regime, and session context."""
from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


class Bias(str, Enum):
    BULLISH = "Bullish"
    BEARISH = "Bearish"
    NEUTRAL = "Neutral"


class Regime(str, Enum):
    TREND = "Trend"
    RANGE_PLAY = "Range Play"
    TRANSITION = "Transition Phase"
    BALANCED = "Balanced Structure"
    BALANCED_WAIT = "Balanced / Wait"


class SessionPhase(str, Enum):
    PRE_MARKET = "Pre-Market"
    OPENING = "Opening"
    MORNING = "Morning"
    MIDDAY = "Midday"
    AFTERNOON = "Afternoon"
    CLOSING = "Closing"
    POST_MARKET = "Post-Market"


class MarketState(BaseModel):
    """Snapshot of the current market state for one symbol/expiry."""

    symbol: str
    expiry: Optional[str] = None
    spot_price: Optional[float] = None

    # Core signals
    bias: Optional[Bias] = None
    regime: Optional[Regime] = None
    session_phase: Optional[str] = None
    trade_action: Optional[str] = None
    trade_readiness: Optional[float] = None
    readiness_state: Optional[str] = None

    # Structural levels
    support: Optional[float] = Field(None, description="Current support strike")
    resistance: Optional[float] = Field(None, description="Current resistance strike")
    previous_support: Optional[float] = None
    previous_resistance: Optional[float] = None

    # Risk indicators
    trap_probability: Optional[float] = Field(None, ge=0, le=100)
    trap_type: Optional[str] = None
    directional_pressure_score: Optional[float] = None
    dps_adjusted: Optional[float] = None

    class Config:
        use_enum_values = True
