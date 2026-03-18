from __future__ import annotations

from typing import Any


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def compute_breakout_probability(
    *,
    spot: float | None,
    support: float | None,
    resistance: float | None,
    alignment_score: float,
    volume_expansion_score: float,
    oi_bias: float,
    trap_probability: float,
    support_zone_pressure: float,
    resistance_zone_pressure: float,
    breakout_strength: float,
    clarity: float,
    directional_force: dict[str, Any] | None,
    day_trend: str | None,
) -> dict[str, Any]:
    spot_value = float(spot or 0.0)
    support_value = float(support or 0.0)
    resistance_value = float(resistance or 0.0)
    range_size = max(1.0, resistance_value - support_value)

    dist_to_resistance = max(1.0, resistance_value - spot_value)
    dist_to_support = max(1.0, spot_value - support_value)

    resistance_proximity = 1.0 - min(1.0, dist_to_resistance / range_size)
    support_proximity = 1.0 - min(1.0, dist_to_support / range_size)
    proximity_weight_up = _clamp((spot_value - support_value) / range_size, 0.0, 1.0)
    proximity_weight_down = _clamp(1.0 - proximity_weight_up, 0.0, 1.0)

    bull_force = _clamp(float((directional_force or {}).get("bull", 0.0) or 0.0) / 100.0, 0.0, 1.0)
    bear_force = _clamp(float((directional_force or {}).get("bear", 0.0) or 0.0) / 100.0, 0.0, 1.0)
    alignment = float(alignment_score or 0.0)
    oi_bias_value = float(oi_bias or 0.0)
    volume = _clamp(float(volume_expansion_score or 0.0), 0.0, 1.0)
    breakout = _clamp(float(breakout_strength or 0.0), 0.0, 1.0)
    clarity_value = _clamp(float(clarity or 0.0) / 100.0, 0.0, 1.0)
    support_pressure = _clamp(float(support_zone_pressure or 0.0) / 100.0, 0.0, 1.0)
    resistance_pressure = _clamp(float(resistance_zone_pressure or 0.0) / 100.0, 0.0, 1.0)

    up_prob_raw = (
        (resistance_proximity * 0.20)
        + (max(0.0, alignment) * 0.15)
        + (max(0.0, oi_bias_value) * 0.15)
        + (volume * 0.10)
        + (resistance_pressure * 0.15)
        + (breakout * 0.15)
        + (clarity_value * 0.05)
        + (bull_force * 0.05)
    )
    down_prob_raw = (
        (support_proximity * 0.20)
        + (max(0.0, -alignment) * 0.15)
        + (max(0.0, -oi_bias_value) * 0.15)
        + (volume * 0.10)
        + (support_pressure * 0.15)
        + (breakout * 0.15)
        + (clarity_value * 0.05)
        + (bear_force * 0.05)
    )

    up_prob_raw *= 0.6 + (0.4 * proximity_weight_up)
    down_prob_raw *= 0.6 + (0.4 * proximity_weight_down)

    trap_factor = 1.0 - min(0.5, float(trap_probability or 0.0) / 200.0)
    up_breakout_probability = round(min(100.0, up_prob_raw * trap_factor * 100.0), 1)
    down_breakout_probability = round(min(100.0, down_prob_raw * trap_factor * 100.0), 1)

    def _classify(probability: float) -> str:
        if probability >= 65.0:
            return "High"
        if probability >= 45.0:
            return "Moderate"
        return "Low"

    return {
        "upside": up_breakout_probability,
        "downside": down_breakout_probability,
        "upside_state": _classify(up_breakout_probability),
        "downside_state": _classify(down_breakout_probability),
        "day_trend_context": str(day_trend or "Neutral"),
    }
