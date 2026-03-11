from __future__ import annotations

from typing import Any


def _to_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def generate_market_insight(
    *,
    support: float | int | None,
    resistance: float | int | None,
    support_center: float | int | None,
    resistance_center: float | int | None,
    support_zone_pressure: float | int | None,
    resistance_zone_pressure: float | int | None,
    oi_velocity: float | int | None,
    volume_expansion: float | int | None,
    trap_probability: float | int | None,
    market_structure_score: float | int | None,
    spot: float | int | None,
    pe_oi_change_near_support: float | int | None = None,
    ce_oi_change_near_resistance: float | int | None = None,
) -> dict[str, Any]:
    sup = _to_float(support)
    res = _to_float(resistance)
    sup_center = _to_float(support_center)
    res_center = _to_float(resistance_center)
    sup_pressure = (_to_float(support_zone_pressure) or 0.0) / 100.0
    res_pressure = (_to_float(resistance_zone_pressure) or 0.0) / 100.0
    oi_vel = max(0.0, min(1.0, _to_float(oi_velocity) or 0.0))
    vol_exp = max(0.0, min(1.0, _to_float(volume_expansion) or 0.0))
    trap = _to_float(trap_probability) or 0.0
    mss = _to_float(market_structure_score) or 0.0
    spot_value = _to_float(spot)
    pe_change = _to_float(pe_oi_change_near_support) or 0.0
    ce_change = _to_float(ce_oi_change_near_resistance) or 0.0

    institutional_structure: dict[str, float | None] = {
        "put_wall": sup_center,
        "call_wall": res_center,
    }
    insights: list[str] = []

    if sup is not None and res is not None and spot_value is not None and spot_value > 0:
        width_ratio = abs(res - sup) / spot_value
        if width_ratio < 0.004:
            insights.append("Market compressing between institutional walls.")

    if pe_change > 10.0:
        insights.append("Put writers accumulating near support.")

    if ce_change > 10.0:
        insights.append("Call writers defending resistance.")

    breakout_pressure = (0.4 * max(sup_pressure, res_pressure)) + (0.3 * oi_vel) + (0.3 * vol_exp)
    if breakout_pressure > 0.6:
        insights.append("Breakout probability rising.")

    if trap >= 60:
        insights.append("Trap risk is elevated near active boundaries.")
    elif mss >= 70:
        insights.append("Structure remains supportive for directional continuation.")

    deduped: list[str] = []
    seen: set[str] = set()
    for item in insights:
        if item not in seen:
            deduped.append(item)
            seen.add(item)

    return {
        "institutional_structure": institutional_structure,
        "market_insight": deduped,
    }
