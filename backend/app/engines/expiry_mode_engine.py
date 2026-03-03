from __future__ import annotations

from datetime import datetime
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


def _days_to_expiry(expiry_text: str | None) -> int | None:
    if not expiry_text:
        return None
    for fmt in ("%d-%b-%Y", "%d-%b-%y", "%d %b %Y"):
        try:
            expiry_dt = datetime.strptime(expiry_text.strip(), fmt).date()
            return (expiry_dt - datetime.now().date()).days
        except ValueError:
            continue
    return None


def run_expiry_adaptive_mode(
    *,
    expiry: str | None,
    spot: float | int | None,
    support: float | int | None,
    resistance: float | int | None,
    expected_move: float | int | None,
    bias: str,
    trap_risk: float | int | None,
    session_phase: str | None,
    strongest_oi_strike: float | int | None,
    strike_gap: float | int | None,
) -> dict[str, Any]:
    days_to_expiry = _days_to_expiry(expiry)
    expiry_mode = days_to_expiry == 0

    expiry_multiplier = 0.7 if expiry_mode else 1.0
    adjusted_move = _to_float(expected_move, 0.0) * expiry_multiplier

    adjusted_trap_risk = _to_float(trap_risk, 0.0)
    if expiry_mode:
        adjusted_trap_risk = min(adjusted_trap_risk * 1.25, 95.0)

    spot_val = _to_float(spot, 0.0)
    strongest = _to_float(strongest_oi_strike, 0.0)
    gap = max(1.0, _to_float(strike_gap, 1.0))
    pinning_risk = abs(spot_val - strongest) < gap

    support_val = _to_float(support, spot_val)
    resistance_val = _to_float(resistance, spot_val)
    if bias == "Bullish":
        target1 = resistance_val + (adjusted_move * 0.6)
        target2 = resistance_val + (adjusted_move * 1.0)
    elif bias == "Bearish":
        target1 = support_val - (adjusted_move * 0.6)
        target2 = support_val - (adjusted_move * 1.0)
    else:
        target1 = spot_val + adjusted_move
        target2 = spot_val - adjusted_move

    return {
        "days_to_expiry": days_to_expiry,
        "expiry_mode": expiry_mode,
        "expiry_multiplier": expiry_multiplier,
        "trap_risk": round(adjusted_trap_risk, 2),
        "pinning_risk": bool(pinning_risk),
        "adjustedMove": round(adjusted_move, 2),
        "target1": round(target1, 2),
        "target2": round(target2, 2),
        "phase_multiplier_reference": PHASE_MULTIPLIER_MAP.get(session_phase or "", 1.0),
    }

