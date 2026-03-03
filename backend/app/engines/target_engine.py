from __future__ import annotations

from typing import Any

PHASE_MULTIPLIER_MAP: dict[str, float] = {
    "Opening Drive": 1.0,
    "Midday Compression": 0.7,
    "Positioning Phase": 0.9,
    "Power Hour": 1.3,
    "Transition": 1.0,
}


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def _infer_session_phase(timestamp_text: str | None) -> str:
    if not timestamp_text:
        return "Transition"

    import re

    match = re.search(r"(\d{1,2}):(\d{2})", str(timestamp_text))
    if not match:
        return "Transition"

    hh = int(match.group(1))
    mm = int(match.group(2))
    minutes = (hh * 60) + mm

    if 9 * 60 + 15 <= minutes < 10 * 60 + 30:
        return "Opening Drive"
    if 10 * 60 + 30 <= minutes < 13 * 60 + 30:
        return "Midday Compression"
    if 13 * 60 + 30 <= minutes < 14 * 60 + 30:
        return "Positioning Phase"
    if 14 * 60 + 30 <= minutes <= 15 * 60 + 30:
        return "Power Hour"
    return "Transition"


def run_target_engine(
    features: dict[str, Any],
    sr: dict[str, Any],
    breakout: dict[str, Any],
    oi: dict[str, Any],
    trap: dict[str, Any],
    volume: dict[str, Any],
    decision: dict[str, Any] | None = None,
    regime: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _ = (breakout, oi, trap, volume, regime)  # keep signature compatibility; unused in retail mode

    spot = _to_float(features.get("meta", {}).get("spot"), 0.0)
    support = _to_float(sr.get("support", {}).get("strike"), spot)
    resistance = _to_float(sr.get("resistance", {}).get("strike"), spot)
    bias = str((decision or {}).get("bias", "Neutral"))
    session_phase = _infer_session_phase(features.get("meta", {}).get("timestamp"))

    atm_row = features.get("atm_row") or {}
    atm_ce_ltp = _to_float(atm_row.get("CE_LastPrice"), 0.0)
    atm_pe_ltp = _to_float(atm_row.get("PE_LastPrice"), 0.0)
    expected_move = max(1.0, atm_ce_ltp + atm_pe_ltp)
    multiplier = PHASE_MULTIPLIER_MAP.get(session_phase, 1.0)
    adjusted_move = expected_move * multiplier

    if bias == "Bullish":
        target1 = resistance + (adjusted_move * 0.6)
        target2 = resistance + (adjusted_move * 1.0)
    elif bias == "Bearish":
        target1 = support - (adjusted_move * 0.6)
        target2 = support - (adjusted_move * 1.0)
    else:
        target1 = spot + adjusted_move
        target2 = spot - adjusted_move

    return {
        "support": round(support, 2),
        "resistance": round(resistance, 2),
        "target1": round(target1, 2),
        "target2": round(target2, 2),
        "target_1": round(target1, 2),
        "target_2": round(target2, 2),
        "expected_move": round(expected_move, 2),
        "upper": round(spot + adjusted_move, 2),
        "lower": round(spot - adjusted_move, 2),
        "session_phase": session_phase,
        "phase_multiplier_used": round(multiplier, 2),
    }
