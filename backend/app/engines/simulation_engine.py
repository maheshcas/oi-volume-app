from __future__ import annotations

from typing import Any

from app.engines.breakout_engine import run_breakout_engine
from app.engines.oi_analyzer import run_oi_analysis
from app.engines.preprocessing import build_feature_frame, normalize_chain
from app.engines.sr_engine import run_sr_engine
from app.engines.trap_engine import run_trap_engine
from app.engines.volume_analyzer import run_volume_analysis
from app.services.parser import build_oi_volume_summary


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
        if out != out:  # NaN check
            return default
        return out
    except (TypeError, ValueError):
        return default


def _extract_spot(snapshot: dict[str, Any]) -> float | None:
    records = snapshot.get("records", {}) or {}
    spot = records.get("underlyingValue", snapshot.get("underlyingValue"))
    parsed = _to_float(spot, default=float("nan"))
    if parsed != parsed:
        return None
    return parsed


def _extract_timestamp(snapshot: dict[str, Any], fallback_index: int) -> str:
    records = snapshot.get("records", {}) or {}
    ts = records.get("timestamp") or snapshot.get("timestamp")
    if ts:
        return str(ts)
    return f"snapshot_{fallback_index}"


def _actual_move_label(next_spot: float, support: float | None, resistance: float | None) -> str:
    if resistance is not None and next_spot > resistance:
        return "breakout_up"
    if support is not None and next_spot < support:
        return "breakout_down"
    return "range"


def _predicted_label(breakout: dict[str, Any], trap: dict[str, Any]) -> str:
    if trap.get("is_trap"):
        return "trap"
    if breakout.get("breakout_up"):
        return "breakout_up"
    if breakout.get("breakout_down"):
        return "breakout_down"
    return "range"


def _result_label(predicted: str, actual: str) -> str:
    if predicted == "trap":
        if actual in ("breakout_up", "breakout_down"):
            return "false_positive"
        return "correct"
    if predicted == actual:
        return "correct"
    if predicted == "range" and actual in ("breakout_up", "breakout_down"):
        return "false_negative"
    if predicted in ("breakout_up", "breakout_down") and actual == "range":
        return "false_positive"
    return "incorrect"


def simulate_breakout_performance(historical_data: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Simulates breakout/trap prediction quality using a time-ordered list
    of historical option-chain snapshots.
    """
    if len(historical_data) < 2:
        return {
            "totalSimulations": 0,
            "hitRate": 0.0,
            "falsePositiveRate": 0.0,
            "falseNegativeRate": 0.0,
            "accuracyOverTime": [],
            "breakoutDetail": [],
        }

    breakout_detail: list[dict[str, Any]] = []
    accuracy_over_time: list[dict[str, Any]] = []
    total = 0
    correct = 0
    false_positive = 0
    false_negative = 0

    for idx in range(len(historical_data) - 1):
        current = historical_data[idx]
        nxt = historical_data[idx + 1]

        spot_now = _extract_spot(current)
        spot_next = _extract_spot(nxt)
        if spot_now is None or spot_next is None:
            continue

        rows = build_oi_volume_summary(current)
        if not rows:
            continue

        symbol = str((current.get("records", {}) or {}).get("underlying", "NIFTY"))
        expiry = str((current.get("records", {}) or {}).get("expiryDate", ""))
        timestamp = _extract_timestamp(current, idx)

        normalized = normalize_chain(rows)
        features = build_feature_frame(
            normalized,
            spot=spot_now,
            symbol=symbol,
            expiry=expiry,
            timestamp=timestamp,
        )
        oi = run_oi_analysis(features)
        volume = run_volume_analysis(features)
        sr = run_sr_engine(features)
        breakout = run_breakout_engine(features, sr)
        trap = run_trap_engine(features, breakout, oi, volume)

        support = sr.get("support", {}).get("strike")
        resistance = sr.get("resistance", {}).get("strike")

        predicted = _predicted_label(breakout, trap)
        actual = _actual_move_label(spot_next, _to_float(support, 0.0) if support is not None else None, _to_float(resistance, 0.0) if resistance is not None else None)
        result = _result_label(predicted, actual)

        total += 1
        if result == "correct":
            correct += 1
        elif result == "false_positive":
            false_positive += 1
        elif result == "false_negative":
            false_negative += 1

        breakout_detail.append(
            {
                "date": timestamp,
                "predicted": predicted,
                "actual": actual,
                "result": result,
                "support": support,
                "resistance": resistance,
                "spotNow": round(spot_now, 2),
                "spotNext": round(spot_next, 2),
                "trapProbability": trap.get("trap_probability_pct"),
            }
        )
        accuracy_over_time.append(
            {
                "date": timestamp,
                "accuracy": round((correct / total) * 100.0, 2),
            }
        )

    if total == 0:
        return {
            "totalSimulations": 0,
            "hitRate": 0.0,
            "falsePositiveRate": 0.0,
            "falseNegativeRate": 0.0,
            "accuracyOverTime": [],
            "breakoutDetail": [],
        }

    return {
        "totalSimulations": total,
        "hitRate": round((correct / total) * 100.0, 2),
        "falsePositiveRate": round((false_positive / total) * 100.0, 2),
        "falseNegativeRate": round((false_negative / total) * 100.0, 2),
        "accuracyOverTime": accuracy_over_time,
        "breakoutDetail": breakout_detail,
    }
