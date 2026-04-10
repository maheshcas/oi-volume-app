from datetime import datetime, timezone
from typing import Any, Literal


OIAlignment = Literal["bullish", "bearish", "mixed"]


def _parse_epoch_seconds(timestamp_text: str | None) -> int:
    if not timestamp_text:
        return int(datetime.now(timezone.utc).timestamp())
    for fmt in ("%d-%b-%Y %H:%M:%S", "%d-%b-%Y %H:%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            return int(datetime.strptime(timestamp_text, fmt).replace(tzinfo=timezone.utc).timestamp())
        except ValueError:
            continue
    return int(datetime.now(timezone.utc).timestamp())


def detect_buildup_type(row: dict[str, Any]) -> str:
    ce_doi = float(row.get("CE_DeltaOI") or 0)
    pe_doi = float(row.get("PE_DeltaOI") or 0)
    if pe_doi > 0 and ce_doi < 0:
        return "Bullish Build-up"
    if ce_doi > 0 and pe_doi < 0:
        return "Bearish Build-up"
    if ce_doi > 0 and pe_doi > 0:
        return "Two-sided Writing"
    if ce_doi < 0 and pe_doi < 0:
        return "Unwinding"
    return "Mixed"


def calculate_oi_strength(features: dict[str, Any]) -> float:
    rows = features["rows"]
    atm_row = features["atm_row"]
    if not rows or not atm_row:
        return 0.0
    atm_abs = abs(atm_row["CE_DeltaOI"]) + abs(atm_row["PE_DeltaOI"])
    avg_abs = sum(abs(r["CE_DeltaOI"]) + abs(r["PE_DeltaOI"]) for r in rows) / max(1, len(rows))
    return min(1.0, atm_abs / max(1.0, avg_abs))


def calculate_concentration_score(rows: list[dict[str, Any]], option_type: Literal["CE", "PE"]) -> float:
    key = "CE_OI" if option_type == "CE" else "PE_OI"
    values = sorted((float(r.get(key) or 0) for r in rows), reverse=True)
    total = sum(values)
    if total <= 0:
        return 0.0
    return round(sum(values[:3]) / total, 4)


def run_oi_analysis(features: dict[str, Any], previous_state: dict[str, Any] | None = None) -> dict[str, Any]:
    rows = features["rows"]
    atm_row = features["atm_row"]
    if not rows or not atm_row:
        return {
            "alignment": "mixed",
            "buildup_type": "Mixed",
            "oi_strength": 0.0,
            "concentration": {},
            "oi_shift_score": 0.0,
            "oi_velocity": 0.0,
            "avg_oi_velocity": 0.0,
            "oi_velocity_score": 0.0,
            "writer_balance_score": 0.0,
            "oi_bias": 0.0,
            "oi_state": {},
        }

    ce_doi = float(atm_row["CE_DeltaOI"])
    pe_doi = float(atm_row["PE_DeltaOI"])
    if pe_doi > ce_doi:
        alignment: OIAlignment = "bullish"
    elif ce_doi > pe_doi:
        alignment = "bearish"
    else:
        alignment = "mixed"

    # Shift score normalized against rolling 20-cycle OI-change baseline.
    # This avoids saturation at 1.0 in quiet sessions.
    default_shift = calculate_oi_strength(features)
    writer_balance_score = round(
        min(1.0, abs(pe_doi - ce_doi) / max(1.0, abs(pe_doi) + abs(ce_doi))),
        4,
    )

    meta = features.get("meta", {}) or {}
    current_ts = _parse_epoch_seconds(meta.get("timestamp"))
    current_oi = float(atm_row.get("CE_OI", 0.0) or 0.0) + float(atm_row.get("PE_OI", 0.0) or 0.0)

    prev = previous_state or {}
    previous_oi = float(prev.get("oi_prev_value", current_oi) or current_oi)
    previous_ts = int(prev.get("oi_prev_ts", current_ts) or current_ts)
    time_delta = max(1, current_ts - previous_ts)
    oi_change = current_oi - previous_oi
    oi_velocity = oi_change / float(time_delta)

    shift_history = [float(x) for x in (prev.get("oi_shift_history", []) or []) if isinstance(x, (int, float))]
    shift_history = (shift_history + [abs(oi_change)])[-20:]
    avg_oi_change = sum(shift_history) / max(1, len(shift_history))
    oi_shift_score = round(
        min(1.0, abs(oi_change) / max(1.0, avg_oi_change)),
        4,
    )
    if avg_oi_change <= 0:
        # Keep variance realistic: if there is no observed OI change baseline,
        # emit 0 for flat moves and fallback only for actual change.
        oi_shift_score = round(default_shift if abs(oi_change) > 0 else 0.0, 4)

    velocity_history = [float(x) for x in (prev.get("oi_velocity_history", []) or []) if isinstance(x, (int, float))]
    velocity_history = (velocity_history + [oi_velocity])[-20:]
    avg_oi_velocity = sum(abs(v) for v in velocity_history) / max(1, len(velocity_history))
    oi_velocity_score = round(min(1.0, abs(oi_velocity) / max(1e-6, avg_oi_velocity * 2.0)), 4)

    oi_bias_magnitude = (0.5 * oi_shift_score) + (0.3 * oi_velocity_score) + (0.2 * writer_balance_score)
    if alignment == "bullish":
        oi_bias = oi_bias_magnitude
    elif alignment == "bearish":
        oi_bias = -oi_bias_magnitude
    else:
        oi_bias = 0.0

    # Absolute OI scale context — percentile rank vs rolling 20-cycle window.
    # Lets downstream engines distinguish NIFTY (millions of OI) from thin symbols.
    total_chain_oi = sum(
        float(r.get("CE_OI") or 0.0) + float(r.get("PE_OI") or 0.0) for r in rows
    )
    oi_scale_history: list[float] = [
        float(x) for x in (prev.get("oi_scale_history", []) or []) if isinstance(x, (int, float))
    ]
    oi_scale_history = (oi_scale_history + [total_chain_oi])[-20:]
    scale_rank = sum(1 for v in oi_scale_history if v <= total_chain_oi) / max(1, len(oi_scale_history))
    if scale_rank >= 0.8:
        oi_scale_label = "High OI session"
    elif scale_rank <= 0.2:
        oi_scale_label = "Low OI session"
    else:
        oi_scale_label = "Normal OI session"

    return {
        "alignment": alignment,
        "buildup_type": detect_buildup_type(atm_row),
        "oi_strength": oi_shift_score,
        "concentration": {
            "ce": calculate_concentration_score(rows, "CE"),
            "pe": calculate_concentration_score(rows, "PE"),
        },
        "oi_shift_score": oi_shift_score,
        "oi_velocity": round(oi_velocity, 6),
        "avg_oi_velocity": round(avg_oi_velocity, 6),
        "oi_velocity_score": oi_velocity_score,
        "writer_balance_score": writer_balance_score,
        "oi_bias": round(max(-1.0, min(1.0, oi_bias)), 4),
        "total_chain_oi": round(total_chain_oi, 0),
        "oi_scale_percentile": round(scale_rank, 4),
        "oi_scale_label": oi_scale_label,
        "oi_state": {
            "oi_prev_value": round(current_oi, 4),
            "oi_prev_ts": current_ts,
            "oi_velocity_history": [round(v, 6) for v in velocity_history],
            "oi_shift_history": [round(v, 4) for v in shift_history],
            "oi_scale_history": [round(v, 0) for v in oi_scale_history],
        },
    }
