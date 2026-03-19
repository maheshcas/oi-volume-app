from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


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
    prev_support: float | None = None,
    prev_resistance: float | None = None,
) -> dict[str, Any]:
    spot_value = _to_float(spot)
    support_value = _to_float(support)
    resistance_value = _to_float(resistance)
    prev_support_value = _to_float(prev_support)
    prev_resistance_value = _to_float(prev_resistance)

    threshold_support = max(50.0, support_value * 0.002) if support_value is not None else None
    threshold_resistance = max(50.0, resistance_value * 0.002) if resistance_value is not None else None
    prev_threshold_support = max(50.0, prev_support_value * 0.002) if prev_support_value is not None else None
    prev_threshold_resistance = max(50.0, prev_resistance_value * 0.002) if prev_resistance_value is not None else None

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
    prev_support_broken = bool(
        prev_support_value is not None
        and spot_value is not None
        and prev_threshold_support is not None
        and spot_value < (prev_support_value - prev_threshold_support)
    )
    prev_resistance_broken = bool(
        prev_resistance_value is not None
        and spot_value is not None
        and prev_threshold_resistance is not None
        and spot_value > (prev_resistance_value + prev_threshold_resistance)
    )
    support_broken = bool(support_broken or prev_support_broken)
    resistance_broken = bool(resistance_broken or prev_resistance_broken)

    support_row = _find_strike_row(rows, support_value)
    resistance_row = _find_strike_row(rows, resistance_value)
    pe_oi_change_pct = _to_float((support_row or {}).get("PE_OIChangePct")) or 0.0
    ce_oi_change_pct = _to_float((support_row or {}).get("CE_OIChangePct")) or 0.0
    res_pe_oi_change_pct = _to_float((resistance_row or {}).get("PE_OIChangePct")) or 0.0
    res_ce_oi_change_pct = _to_float((resistance_row or {}).get("CE_OIChangePct")) or 0.0
    pe_oi_up = pe_oi_change_pct > 5.0
    pe_oi_down = pe_oi_change_pct < -5.0
    ce_oi_up = ce_oi_change_pct > 5.0
    res_pe_oi_up = res_pe_oi_change_pct > 5.0
    res_ce_oi_down = res_ce_oi_change_pct < -5.0

    confirmation_type = None
    material_breach_confirmed = False
    confirmation_via = None
    if resistance_broken and res_ce_oi_down and res_pe_oi_up:
        confirmation_type = "bullish_positioning"
        material_breach_confirmed = True
        confirmation_via = "oi_positioning"
    elif resistance_broken and breach_distance_resistance is not None and threshold_resistance is not None and breach_distance_resistance >= (threshold_resistance * 2.0):
        confirmation_type = "resistance_abandonment"
        material_breach_confirmed = True
        confirmation_via = "distance_fallback"
    elif support_broken and pe_oi_up and ce_oi_up:
        confirmation_type = "bearish_positioning"
        material_breach_confirmed = True
        confirmation_via = "oi_positioning"
    elif support_broken and pe_oi_down:
        confirmation_type = "support_abandonment"
        material_breach_confirmed = True
        confirmation_via = "oi_abandonment"
    elif support_broken and breach_distance_support is not None and threshold_support is not None and breach_distance_support >= (threshold_support * 2.0):
        confirmation_type = "support_abandonment"
        material_breach_confirmed = True
        confirmation_via = "distance_fallback"
    elif prev_support_broken:
        confirmation_type = "support_abandonment"
        material_breach_confirmed = True
        confirmation_via = "previous_level_override"
    elif prev_resistance_broken:
        confirmation_type = "resistance_abandonment"
        material_breach_confirmed = True
        confirmation_via = "previous_level_override"

    if material_breach_confirmed:
        side = "support" if "support" in str(confirmation_type or "") or bool(support_broken and not resistance_broken) else "resistance"
        dist = float(breach_distance_support or 0.0) if side == "support" else float(breach_distance_resistance or 0.0)
        logger.debug(
            "breach confirmed: side=%s dist=%.0f type=%s via=%s",
            side,
            dist,
            confirmation_type,
            confirmation_via,
        )

    if support_broken and not material_breach_confirmed:
        logger.debug(
            "breach unconfirmed: side=support dist=%.0f pe_oi=%.1f%% ce_oi=%.1f%% prev_support=%s",
            float(breach_distance_support or 0.0),
            float(pe_oi_change_pct),
            float(ce_oi_change_pct),
            prev_support_value,
        )
    if resistance_broken and not material_breach_confirmed:
        logger.debug(
            "breach unconfirmed: side=resistance dist=%.0f pe_oi=%.1f%% ce_oi=%.1f%% prev_resistance=%s",
            float(breach_distance_resistance or 0.0),
            float(res_pe_oi_change_pct),
            float(res_ce_oi_change_pct),
            prev_resistance_value,
        )

    return {
        "support_broken": support_broken,
        "resistance_broken": resistance_broken,
        "material_breach_confirmed": material_breach_confirmed,
        "confirmation_type": confirmation_type,
        "support_pe_oi_change_pct": round(pe_oi_change_pct, 2),
        "support_ce_oi_change_pct": round(ce_oi_change_pct, 2),
        "resistance_pe_oi_change_pct": round(res_pe_oi_change_pct, 2),
        "resistance_ce_oi_change_pct": round(res_ce_oi_change_pct, 2),
        "breach_distance_support": round(float(breach_distance_support), 2)
        if breach_distance_support is not None
        else None,
        "breach_distance_resistance": round(float(breach_distance_resistance), 2)
        if breach_distance_resistance is not None
        else None,
        "prev_support_broken": prev_support_broken,
        "prev_resistance_broken": prev_resistance_broken,
    }
