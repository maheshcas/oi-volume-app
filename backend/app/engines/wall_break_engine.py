from __future__ import annotations

from typing import Any


def _to_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _find_row(rows: list[dict[str, Any]], strike_value: float | int | None) -> dict[str, Any] | None:
    strike_num = _to_float(strike_value)
    if strike_num is None:
        return None
    for row in rows:
        try:
            if float(row.get("strike")) == strike_num:
                return row
        except (TypeError, ValueError):
            continue
    return None


def detect_wall_break(
    *,
    spot: float | int | None,
    support: float | int | None,
    resistance: float | int | None,
    support_center: float | int | None,
    resistance_center: float | int | None,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    spot_num = _to_float(spot)
    support_num = _to_float(support_center if support_center is not None else support)
    resistance_num = _to_float(resistance_center if resistance_center is not None else resistance)

    result = {
        "wall_break_signal": False,
        "wall_break_direction": None,
        "wall_break_reason": None,
    }

    if spot_num is None:
        return result

    resistance_row = _find_row(rows, resistance_num)
    support_row = _find_row(rows, support_num)

    if resistance_num is not None and resistance_num > 0:
        near_resistance = abs(spot_num - resistance_num) / resistance_num <= 0.003
        ce_oi_change_near_resistance = _to_float((resistance_row or {}).get("CE_OIChangePct")) or 0.0
        pe_oi_change_near_resistance = _to_float((resistance_row or {}).get("PE_OIChangePct")) or 0.0
        if near_resistance and ce_oi_change_near_resistance < -5.0 and pe_oi_change_near_resistance > 5.0:
            return {
                "wall_break_signal": True,
                "wall_break_direction": "upside",
                "wall_break_reason": "Call writers covering near resistance.",
            }

    if support_num is not None and support_num > 0:
        near_support = abs(spot_num - support_num) / support_num <= 0.003
        pe_oi_change_near_support = _to_float((support_row or {}).get("PE_OIChangePct")) or 0.0
        ce_oi_change_near_support = _to_float((support_row or {}).get("CE_OIChangePct")) or 0.0
        if near_support and pe_oi_change_near_support < -5.0 and ce_oi_change_near_support > 5.0:
            return {
                "wall_break_signal": True,
                "wall_break_direction": "downside",
                "wall_break_reason": "Put writers covering near support.",
            }

    return result
