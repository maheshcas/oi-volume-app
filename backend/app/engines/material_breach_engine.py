from __future__ import annotations

from typing import Any


def _to_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def detect_material_breach(
    spot: float | None,
    support: float | None,
    resistance: float | None,
) -> dict[str, Any]:
    spot_value = _to_float(spot)
    support_value = _to_float(support)
    resistance_value = _to_float(resistance)

    threshold_support = max(50.0, support_value * 0.002) if support_value is not None else None
    threshold_resistance = max(50.0, resistance_value * 0.002) if resistance_value is not None else None

    breach_distance_support = (
        support_value - spot_value
        if support_value is not None and spot_value is not None
        else None
    )
    breach_distance_resistance = (
        spot_value - resistance_value
        if resistance_value is not None and spot_value is not None
        else None
    )

    support_broken = bool(
        support_value is not None
        and spot_value is not None
        and threshold_support is not None
        and spot_value < (support_value - threshold_support)
    )
    resistance_broken = bool(
        resistance_value is not None
        and spot_value is not None
        and threshold_resistance is not None
        and spot_value > (resistance_value + threshold_resistance)
    )

    return {
        "support_broken": support_broken,
        "resistance_broken": resistance_broken,
        "breach_distance_support": round(float(breach_distance_support), 2)
        if breach_distance_support is not None
        else None,
        "breach_distance_resistance": round(float(breach_distance_resistance), 2)
        if breach_distance_resistance is not None
        else None,
    }
