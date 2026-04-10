from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_WEIGHTS = {"oi": 0.35, "volume": 0.25, "breakout": 0.20, "sr": 0.20}
MAX_SESSIONS = 20
MAX_SIGNAL_OUTCOMES = 200  # rolling cap on intraday signal outcome records
MIN_WEIGHT = 0.15
MAX_WEIGHT = 0.45
ADJUSTMENT_COOLDOWN_SESSIONS = 3
DEFAULT_STORE = Path(__file__).resolve().parents[2] / "data" / "adaptive_calibration.json"


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(x)))


def _normalize(weights: dict[str, float]) -> dict[str, float]:
    total = sum(float(v) for v in weights.values())
    if total <= 0:
        return dict(DEFAULT_WEIGHTS)
    return {k: float(v) / total for k, v in weights.items()}


def _load_store(path: Path = DEFAULT_STORE) -> dict[str, Any]:
    if not path.exists():
        return {"weights": dict(DEFAULT_WEIGHTS), "sessions": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"weights": dict(DEFAULT_WEIGHTS), "sessions": []}


def _save_store(payload: dict[str, Any], path: Path = DEFAULT_STORE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def record_signal_outcome(
    *,
    signal_type: str,
    predicted_direction: str,
    actual_outcome: str,
    confidence: float,
    timestamp: str | None = None,
    path: Path = DEFAULT_STORE,
) -> dict[str, Any]:
    """
    Record a real-time signal outcome for intraday feedback.

    signal_type: "oi", "breakout", "trap", "sr", or "bias"
    predicted_direction: "Bullish" | "Bearish" | "Neutral"
    actual_outcome: "correct" | "incorrect" | "neutral"
    confidence: 0-100

    Outcomes accumulate during the session and feed into calibration at EOD.
    Returns per-type accuracy summary from rolling outcomes.
    """
    store = _load_store(path)
    outcomes: list[dict[str, Any]] = list(store.get("signal_outcomes", []))

    ts = timestamp or datetime.now(timezone.utc).isoformat()
    outcomes.append({
        "ts": ts,
        "signal_type": str(signal_type),
        "predicted": str(predicted_direction),
        "outcome": str(actual_outcome),
        "confidence": float(_clamp(confidence, 0.0, 100.0)),
    })
    outcomes = outcomes[-MAX_SIGNAL_OUTCOMES:]

    # Compute rolling per-type accuracy from the last 50 outcomes.
    recent = outcomes[-50:]
    type_stats: dict[str, dict[str, int]] = {}
    for rec in recent:
        stype = str(rec.get("signal_type", "unknown"))
        if stype not in type_stats:
            type_stats[stype] = {"correct": 0, "total": 0}
        type_stats[stype]["total"] += 1
        if str(rec.get("outcome", "")) == "correct":
            type_stats[stype]["correct"] += 1

    accuracy_summary: dict[str, float] = {}
    for stype, counts in type_stats.items():
        if counts["total"] > 0:
            accuracy_summary[stype] = round(counts["correct"] / counts["total"] * 100.0, 1)

    store["signal_outcomes"] = outcomes
    store["rolling_accuracy"] = accuracy_summary
    _save_store(store, path)
    return {"accuracy_summary": accuracy_summary, "total_outcomes": len(outcomes)}


def load_rolling_accuracy(path: Path = DEFAULT_STORE) -> dict[str, float]:
    """Return the latest per-signal-type rolling accuracy (0-100 scale)."""
    store = _load_store(path)
    return dict(store.get("rolling_accuracy", {}))


def load_adaptive_weights(path: Path = DEFAULT_STORE) -> dict[str, float]:
    store = _load_store(path)
    weights = store.get("weights") if isinstance(store.get("weights"), dict) else dict(DEFAULT_WEIGHTS)
    parsed = {
        "oi": _clamp(float(weights.get("oi", DEFAULT_WEIGHTS["oi"])), MIN_WEIGHT, MAX_WEIGHT),
        "volume": _clamp(float(weights.get("volume", DEFAULT_WEIGHTS["volume"])), MIN_WEIGHT, MAX_WEIGHT),
        "breakout": _clamp(float(weights.get("breakout", DEFAULT_WEIGHTS["breakout"])), MIN_WEIGHT, MAX_WEIGHT),
        "sr": _clamp(float(weights.get("sr", DEFAULT_WEIGHTS["sr"])), MIN_WEIGHT, MAX_WEIGHT),
    }
    return _normalize(parsed)


def update_end_of_day_calibration(
    *,
    bias_accuracy: float,
    breakout_accuracy: float,
    trap_accuracy: float,
    clarity_vs_outcome_accuracy: float,
    oi_accuracy: float | None = None,
    session_date: date | None = None,
    path: Path = DEFAULT_STORE,
) -> dict[str, float]:
    store = _load_store(path)
    sessions = list(store.get("sessions", []))
    weights = load_adaptive_weights(path)
    cooldowns_raw = store.get("adjustment_cooldowns", {})
    cooldowns: dict[str, int] = {
        key: max(0, int((cooldowns_raw or {}).get(key, 0) or 0))
        for key in ("oi", "volume", "breakout", "sr")
    }
    # Advance cooldown clocks once per calibration session.
    cooldowns = {key: max(0, value - 1) for key, value in cooldowns.items()}

    session_key = (session_date or date.today()).isoformat()
    sessions = [s for s in sessions if s.get("date") != session_key]
    sessions.append(
        {
            "date": session_key,
            "bias_accuracy": float(bias_accuracy),
            "breakout_accuracy": float(breakout_accuracy),
            "trap_accuracy": float(trap_accuracy),
            "clarity_vs_outcome_accuracy": float(clarity_vs_outcome_accuracy),
            "oi_accuracy": float(oi_accuracy if oi_accuracy is not None else bias_accuracy),
        }
    )
    sessions = sessions[-MAX_SESSIONS:]

    def _apply_weight_adjustment(weight_key: str, delta: float) -> bool:
        if cooldowns.get(weight_key, 0) > 0:
            return False
        current = float(weights.get(weight_key, DEFAULT_WEIGHTS.get(weight_key, 0.25)))
        updated = _clamp(current + float(delta), MIN_WEIGHT, MAX_WEIGHT)
        if abs(updated - current) < 1e-9:
            return False
        weights[weight_key] = updated
        cooldowns[weight_key] = ADJUSTMENT_COOLDOWN_SESSIONS
        return True

    last10 = sessions[-10:]
    if last10:
        breakout_mean = sum(float(s.get("breakout_accuracy", 0.0)) for s in last10) / len(last10)
        oi_mean = sum(float(s.get("oi_accuracy", s.get("bias_accuracy", 0.0))) for s in last10) / len(last10)
        sr_mean = sum(float(s.get("sr_accuracy", s.get("bias_accuracy", 0.0))) for s in last10) / len(last10)
        volume_mean = sum(float(s.get("volume_accuracy", s.get("bias_accuracy", 0.0))) for s in last10) / len(last10)
        if breakout_mean < 45.0:
            _apply_weight_adjustment("breakout", -0.05)
        if oi_mean > 60.0:
            _apply_weight_adjustment("oi", +0.05)
        if sr_mean < 45.0:
            _apply_weight_adjustment("sr", -0.03)
        if volume_mean > 60.0:
            _apply_weight_adjustment("volume", +0.03)

    # Also blend in intraday rolling accuracy if we have enough signal outcomes.
    rolling = dict(store.get("rolling_accuracy", {}))
    if rolling.get("breakout") is not None and rolling["breakout"] < 40.0:
        _apply_weight_adjustment("breakout", -0.03)
    if rolling.get("oi") is not None and rolling["oi"] > 65.0:
        _apply_weight_adjustment("oi", +0.03)
    # Clear intraday outcomes after EOD calibration so next session starts fresh.
    store["signal_outcomes"] = []
    store["rolling_accuracy"] = {}

    weights = _normalize(weights)
    store["weights"] = weights
    store["sessions"] = sessions
    store["adjustment_cooldowns"] = cooldowns
    _save_store(store, path)
    return weights
