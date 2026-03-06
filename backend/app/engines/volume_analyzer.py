from datetime import datetime, timezone
from typing import Any, Literal


def _parse_epoch_seconds(timestamp_text: str | None) -> int:
    if not timestamp_text:
        return int(datetime.now(timezone.utc).timestamp())
    for fmt in ("%d-%b-%Y %H:%M:%S", "%d-%b-%Y %H:%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            return int(datetime.strptime(timestamp_text, fmt).replace(tzinfo=timezone.utc).timestamp())
        except ValueError:
            continue
    return int(datetime.now(timezone.utc).timestamp())


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


def run_volume_analysis(
    features: dict[str, Any],
    expansion_threshold: float = 1.2,
    previous_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rows = features["rows"]
    atm_row = features["atm_row"]
    if not rows or not atm_row:
        return {
            "volume_expansion": False,
            "volume_expansion_score": 0.0,
            "volume_ratio": 0.0,
            "rvr": {"ce": 0.0, "pe": 0.0},
            "atm_participation": 0.0,
            "volume_state": {},
        }

    prev = previous_state or {}
    ts = _parse_epoch_seconds(features.get("meta", {}).get("timestamp"))
    current_total_volume = sum((float(r.get("CE_Volume") or 0) + float(r.get("PE_Volume") or 0)) for r in rows)
    hist = [float(x) for x in (prev.get("volume_history", []) or []) if isinstance(x, (int, float))]
    hist = (hist + [current_total_volume])[-20:]
    avg_volume_last_20 = sum(hist) / max(1, len(hist))
    volume_ratio = current_total_volume / max(1.0, avg_volume_last_20)
    volume_expansion_score = min(1.0, volume_ratio / 2.0)
    is_expansion = bool(volume_expansion_score > max(0.4, min(0.95, expansion_threshold / 2.0)))

    return {
        "volume_expansion": is_expansion,
        "volume_expansion_score": round(volume_expansion_score, 4),
        "volume_ratio": round(volume_ratio, 4),
        "rvr": {
            "ce": compute_relative_volume_rank(atm_row, rows, "CE"),
            "pe": compute_relative_volume_rank(atm_row, rows, "PE"),
        },
        "atm_participation": atm_participation_score(features),
        "volume_state": {
            "volume_prev_ts": ts,
            "volume_history": [round(v, 2) for v in hist],
        },
    }
