from __future__ import annotations

from typing import Any


def _to_float(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _normalize(values: list[float]) -> list[float]:
    if not values:
        return []
    lo = min(values)
    hi = max(values)
    if hi <= lo:
        return [1.0 for _ in values]
    return [max(0.0, min(1.0, (value - lo) / (hi - lo))) for value in values]


def build_liquidity_map(*, rows: list[dict[str, Any]], spot: float | int | None) -> dict[str, Any]:
    if not rows:
        return {
            "put_wall": None,
            "call_wall": None,
            "battle_zone": None,
            "liquidity_void": [],
        }

    spot_num = _to_float(spot)
    strikes = [_to_float(row.get("strike")) for row in rows]
    max_strike_range = max(1.0, max(strikes) - min(strikes)) if strikes else 1.0

    total_oi_values = [_to_float(row.get("CE_OI")) + _to_float(row.get("PE_OI")) for row in rows]
    total_volume_values = [_to_float(row.get("CE_Volume")) + _to_float(row.get("PE_Volume")) for row in rows]
    normalized_oi = _normalize(total_oi_values)
    normalized_volume = _normalize(total_volume_values)

    scored_rows: list[dict[str, Any]] = []
    battle_threshold = max(total_oi_values) * 0.5 if total_oi_values else 0.0
    for idx, row in enumerate(rows):
        strike = _to_float(row.get("strike"))
        ce_oi = _to_float(row.get("CE_OI"))
        pe_oi = _to_float(row.get("PE_OI"))
        proximity_to_spot = 0.0
        if spot_num > 0:
            proximity_to_spot = 1.0 - (abs(strike - spot_num) / max_strike_range)
            proximity_to_spot = max(0.0, min(1.0, proximity_to_spot))
        liquidity_score = (
            0.5 * normalized_oi[idx]
            + 0.3 * normalized_volume[idx]
            + 0.2 * proximity_to_spot
        )
        scored_rows.append(
            {
                "strike": strike,
                "ce_oi": ce_oi,
                "pe_oi": pe_oi,
                "normalized_oi": round(normalized_oi[idx], 4),
                "normalized_volume": round(normalized_volume[idx], 4),
                "proximity_to_spot": round(proximity_to_spot, 4),
                "liquidity_score": round(max(0.0, min(1.0, liquidity_score)), 4),
                "is_battle_zone": ce_oi > battle_threshold and pe_oi > battle_threshold,
            }
        )

    put_candidates = [row for row in scored_rows if row["strike"] <= spot_num and row["liquidity_score"] > 0.7]
    call_candidates = [row for row in scored_rows if row["strike"] >= spot_num and row["liquidity_score"] > 0.7]
    battle_candidates = [row for row in scored_rows if row["is_battle_zone"]]

    put_wall = max(put_candidates, key=lambda row: row["liquidity_score"])["strike"] if put_candidates else None
    call_wall = max(call_candidates, key=lambda row: row["liquidity_score"])["strike"] if call_candidates else None
    battle_zone = max(battle_candidates, key=lambda row: row["liquidity_score"])["strike"] if battle_candidates else None

    sorted_scored_rows = sorted(scored_rows, key=lambda row: row["strike"])
    liquidity_void: list[list[float]] = []
    for idx in range(len(sorted_scored_rows) - 1):
        current_row = sorted_scored_rows[idx]
        next_row = sorted_scored_rows[idx + 1]
        if current_row["liquidity_score"] < 0.2 and next_row["liquidity_score"] < 0.2:
            liquidity_void.append([current_row["strike"], next_row["strike"]])

    return {
        "put_wall": put_wall,
        "call_wall": call_wall,
        "battle_zone": battle_zone,
        "liquidity_void": liquidity_void,
    }
