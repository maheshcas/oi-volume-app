from __future__ import annotations

from typing import Any


def _to_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _find_strike_row(rows: list[dict[str, Any]] | None, strike: float | None) -> dict[str, Any] | None:
    if not rows or strike is None:
        return None
    for row in rows:
        row_strike = _to_float(row.get("strike"))
        if row_strike is None:
            continue
        if abs(row_strike - strike) < 1e-6:
            return row
    return None


def detect_material_breach(
    spot: float | None,
    support: float | None,
    resistance: float | None,
    rows: list[dict[str, Any]] | None = None,
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

    support_row = _find_strike_row(rows, support_value)
    pe_oi_change_pct = _to_float((support_row or {}).get("PE_OIChangePct")) or 0.0
    ce_oi_change_pct = _to_float((support_row or {}).get("CE_OIChangePct")) or 0.0
    pe_oi_up = pe_oi_change_pct > 5.0
    pe_oi_down = pe_oi_change_pct < -5.0
    ce_oi_up = ce_oi_change_pct > 5.0

    confirmation_type = None
    material_breach_confirmed = False
    if support_broken and pe_oi_up and ce_oi_up:
        confirmation_type = "bearish_positioning"
        material_breach_confirmed = True
    elif support_broken and pe_oi_down:
        confirmation_type = "support_abandonment"
        material_breach_confirmed = True

    return {
        "support_broken": support_broken,
        "resistance_broken": resistance_broken,
        "material_breach_confirmed": material_breach_confirmed,
        "confirmation_type": confirmation_type,
        "support_pe_oi_change_pct": round(pe_oi_change_pct, 2),
        "support_ce_oi_change_pct": round(ce_oi_change_pct, 2),
        "breach_distance_support": round(float(breach_distance_support), 2)
        if breach_distance_support is not None
        else None,
        "breach_distance_resistance": round(float(breach_distance_resistance), 2)
        if breach_distance_resistance is not None
        else None,
    }
