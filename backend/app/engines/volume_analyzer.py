from typing import Any, Literal


def detect_volume_expansion(features: dict[str, Any], threshold: float = 1.2) -> bool:
    rows = features["rows"]
    atm_row = features["atm_row"]
    if not rows or not atm_row:
        return False
    avg_total = sum(r["CE_Volume"] + r["PE_Volume"] for r in rows) / max(1, len(rows))
    atm_total = atm_row["CE_Volume"] + atm_row["PE_Volume"]
    return atm_total > (avg_total * threshold)


def compute_relative_volume_rank(
    row: dict[str, Any], rows: list[dict[str, Any]], option_type: Literal["CE", "PE"]
) -> float:
    key = "CE_Volume" if option_type == "CE" else "PE_Volume"
    values = sorted((float(r.get(key) or 0) for r in rows))
    if not values:
        return 0.0
    target = float(row.get(key) or 0)
    rank = sum(1 for v in values if v <= target) / len(values)
    return round(rank, 4)


def atm_participation_score(features: dict[str, Any]) -> float:
    rows = features["rows"]
    atm_row = features["atm_row"]
    totals = features["totals"]
    if not rows or not atm_row:
        return 0.0
    atm_total = atm_row["CE_Volume"] + atm_row["PE_Volume"]
    total = (totals.get("ce_total_vol", 0) or 0) + (totals.get("pe_total_vol", 0) or 0)
    return round(min(1.0, atm_total / max(1.0, total * 0.15)), 4)


def run_volume_analysis(features: dict[str, Any]) -> dict[str, Any]:
    rows = features["rows"]
    atm_row = features["atm_row"]
    if not rows or not atm_row:
        return {"volume_expansion": False, "rvr": {"ce": 0.0, "pe": 0.0}, "atm_participation": 0.0}

    return {
        "volume_expansion": detect_volume_expansion(features),
        "rvr": {
            "ce": compute_relative_volume_rank(atm_row, rows, "CE"),
            "pe": compute_relative_volume_rank(atm_row, rows, "PE"),
        },
        "atm_participation": atm_participation_score(features),
    }
