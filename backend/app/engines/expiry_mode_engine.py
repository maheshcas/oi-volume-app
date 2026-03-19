from __future__ import annotations

from datetime import datetime
from typing import Any


PHASE_MULTIPLIER_MAP: dict[str, float] = {
    "Opening Drive": 1.0,
    "Midday Compression": 0.7,
    "Compression Phase": 0.85,
    "Positioning Phase": 0.9,
    "Position Build Phase": 0.9,
    "Power Hour": 1.3,
    "Transition": 0.95,
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
    phase_multiplier = PHASE_MULTIPLIER_MAP.get(session_phase or "", 1.0)
    expiry_trap_multiplier = 1.25 if expiry_mode else 1.0
    combined_trap_multiplier = min(1.5, expiry_trap_multiplier * phase_multiplier)
    adjusted_trap_risk = min(adjusted_trap_risk * combined_trap_multiplier, 95.0)

    spot_val = _to_float(spot, 0.0)
    strongest = _to_float(strongest_oi_strike, 0.0)
    gap = max(1.0, _to_float(strike_gap, 1.0))
    pinning_risk = abs(spot_val - strongest) < gap

    support_val = _to_float(support, spot_val)
    resistance_val = _to_float(resistance, spot_val)
    band_width = max(1.0, resistance_val - support_val)
    vol_factor = max(0.6, min(1.4, expiry_multiplier))
    oi_power = 0.15 if pinning_risk else 0.0
    base_move = max(1.0, band_width * (1.0 + oi_power) * vol_factor)
    max_distance = band_width * 3.0
    if bias == "Bullish":
        target1 = resistance_val + min(base_move * 0.8, max_distance)
        target2 = resistance_val + min(base_move * 1.5, max_distance)
    elif bias == "Bearish":
        target1 = support_val - min(base_move * 0.8, max_distance)
        target2 = support_val - min(base_move * 1.5, max_distance)
    else:
        target1 = resistance_val + min(base_move * 0.8, max_distance)
        target2 = support_val - min(base_move * 0.8, max_distance)

    return {
        "days_to_expiry": days_to_expiry,
        "expiry_mode": expiry_mode,
        "expiry_multiplier": expiry_multiplier,
        "trap_risk": round(adjusted_trap_risk, 2),
        "pinning_risk": bool(pinning_risk),
        "adjustedMove": round(adjusted_move, 2),
        "baseMove": round(base_move, 2),
        "bandWidth": round(band_width, 2),
        "target1": round(target1, 2),
        "target2": round(target2, 2),
        "phase_multiplier_reference": phase_multiplier,
        "combined_trap_multiplier": round(combined_trap_multiplier, 4),
    }
