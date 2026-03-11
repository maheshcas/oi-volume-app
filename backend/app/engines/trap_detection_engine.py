from __future__ import annotations

from typing import Any


def _safe_number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _extract_step(strikes: list[float]) -> float:
    if len(strikes) < 2:
        return 50.0
    ordered = sorted(set(strikes))
    diffs = [ordered[idx + 1] - ordered[idx] for idx in range(len(ordered) - 1)]
    positive_diffs = [diff for diff in diffs if diff > 0]
    return min(positive_diffs) if positive_diffs else 50.0


def detect_trap(option_chain: dict[str, Any]) -> dict[str, Any]:
    spot = _safe_number(option_chain.get("spot"))
    rows = option_chain.get("data") or []
    if not rows:
        return {
            "support": None,
            "resistance": None,
            "trap_score": 0.0,
            "trap_risk": "Low",
            "trap_type": "Range Trap",
        }

    strikes = [_safe_number(row.get("strike")) for row in rows]
    strike_step = _extract_step(strikes)
    max_distance = strike_step * 10

    filtered_rows = [
        row for row in rows
        if abs(_safe_number(row.get("strike")) - spot) <= max_distance
    ]
    if not filtered_rows:
        filtered_rows = rows

    total_ce_oi = sum(_safe_number((row.get("CE") or {}).get("oi")) for row in filtered_rows)
    total_pe_oi = sum(_safe_number((row.get("PE") or {}).get("oi")) for row in filtered_rows)

    resistance_row = max(filtered_rows, key=lambda row: _safe_number((row.get("CE") or {}).get("oi")))
    support_row = max(filtered_rows, key=lambda row: _safe_number((row.get("PE") or {}).get("oi")))

    resistance = int(_safe_number(resistance_row.get("strike")))
    support = int(_safe_number(support_row.get("strike")))

    ce_at_resistance = _safe_number((resistance_row.get("CE") or {}).get("oi"))
    pe_at_support = _safe_number((support_row.get("PE") or {}).get("oi"))

    ce_change = _safe_number((resistance_row.get("CE") or {}).get("oi_change"))
    pe_change = _safe_number((support_row.get("PE") or {}).get("oi_change"))

    ce_concentration = (ce_at_resistance / total_ce_oi) if total_ce_oi > 0 else 0.0
    pe_concentration = (pe_at_support / total_pe_oi) if total_pe_oi > 0 else 0.0

    compression = abs(resistance - support) / spot if spot > 0 else 1.0
    ce_growth = (ce_change / ce_at_resistance) if ce_at_resistance > 0 else 0.0
    pe_growth = (pe_change / pe_at_support) if pe_at_support > 0 else 0.0

    raw_score = (
        (ce_concentration * 30.0)
        + (pe_concentration * 30.0)
        + ((1.0 - compression) * 20.0)
        + (max(ce_growth, 0.0) * 10.0)
        + (max(pe_growth, 0.0) * 10.0)
    )
    trap_score = round(max(0.0, min(100.0, raw_score)), 2)

    if trap_score > 70:
        trap_risk = "High"
    elif trap_score > 40:
        trap_risk = "Moderate"
    else:
        trap_risk = "Low"

    near_resistance = spot > 0 and abs(spot - resistance) / spot <= 0.003
    near_support = spot > 0 and abs(spot - support) / spot <= 0.003

    if near_resistance and ce_change > 0:
        trap_type = "Bull Trap"
    elif near_support and pe_change > 0:
        trap_type = "Bear Trap"
    else:
        trap_type = "Range Trap"

    return {
        "support": support,
        "resistance": resistance,
        "trap_score": trap_score,
        "trap_risk": trap_risk,
        "trap_type": trap_type,
    }
