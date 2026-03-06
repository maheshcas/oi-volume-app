from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

DEFAULT_WEIGHTS = {"oi": 0.35, "volume": 0.25, "breakout": 0.20, "sr": 0.20}
MAX_SESSIONS = 20
MIN_WEIGHT = 0.15
MAX_WEIGHT = 0.45
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

    last10 = sessions[-10:]
    if last10:
        breakout_mean = sum(float(s.get("breakout_accuracy", 0.0)) for s in last10) / len(last10)
        oi_mean = sum(float(s.get("oi_accuracy", s.get("bias_accuracy", 0.0))) for s in last10) / len(last10)
        if breakout_mean < 45.0:
            weights["breakout"] = _clamp(weights["breakout"] - 0.05, MIN_WEIGHT, MAX_WEIGHT)
        if oi_mean > 60.0:
            weights["oi"] = _clamp(weights["oi"] + 0.05, MIN_WEIGHT, MAX_WEIGHT)

    weights = _normalize(weights)
    store["weights"] = weights
    store["sessions"] = sessions
    _save_store(store, path)
    return weights
