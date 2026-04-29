from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from datetime import datetime, timezone


def _variance(values: list[float]) -> float:
    if not values:
        return 0.0
    mean = sum(values) / len(values)
    return sum((x - mean) ** 2 for x in values) / len(values)


def _extract_float(entry: dict[str, Any], key: str) -> float | None:
    value = entry.get(key)
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _distribution(values: list[float]) -> dict[str, float]:
    if not values:
        return {"min": 0.0, "max": 0.0, "average": 0.0, "variance": 0.0}
    return {
        "min": round(min(values), 4),
        "max": round(max(values), 4),
        "average": round(sum(values) / len(values), 4),
        "variance": round(_variance(values), 6),
    }


def _status(condition_ok: bool) -> str:
    return "ok" if condition_ok else "warning"


def _no_data_response(generated_at: str, message: str) -> dict[str, Any]:
    return {
        "trap_distribution_status": "no_data",
        "wick_variation_status": "no_data",
        "hold_time_status": "no_data",
        "oi_normalization_status": "no_data",
        "volume_normalization_status": "no_data",
        "clarity_status": "no_data",
        "generated_at": generated_at,
        "detail": {"message": message, "cycles_analyzed": 0},
    }


def compute_engine_health(log_path: Path, tail_cycles: int = 200) -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).isoformat()
    if not log_path.exists():
        return _no_data_response(generated_at, f"log file not found: {log_path}")

    lines = log_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    if not lines:
        return _no_data_response(generated_at, "no log rows")

    rows: list[dict[str, Any]] = []
    for line in lines[-max(1, tail_cycles) :]:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                rows.append(obj)
        except json.JSONDecodeError:
            continue

    if not rows:
        return _no_data_response(generated_at, "no valid log rows")

    trap_values = [v for v in (_extract_float(r, "trap_probability") for r in rows) if v is not None]
    wick_values = [v for v in (_extract_float(r, "rejection_wick_score") for r in rows) if v is not None]
    hold_values = [v for v in (_extract_float(r, "time_above_level_ratio") for r in rows) if v is not None]
    oi_values = [v for v in (_extract_float(r, "oi_shift_score") for r in rows) if v is not None]
    vol_values = [v for v in (_extract_float(r, "volume_expansion_score") for r in rows) if v is not None]
    clarity_values = [v for v in (_extract_float(r, "clarity") for r in rows) if v is not None]

    trap_distribution_status = _status((max(trap_values) if trap_values else 0.0) >= 40.0)
    wick_variation_status = _status(any(abs(v) > 1e-9 for v in wick_values))
    hold_time_status = _status(len({round(v, 6) for v in hold_values}) > 2)
    oi_normalization_status = _status(((sum(oi_values) / len(oi_values)) if oi_values else 0.0) <= 0.95)
    volume_normalization_status = _status(((sum(vol_values) / len(vol_values)) if vol_values else 0.0) <= 0.95)
    clarity_status = _status(((sum(clarity_values) / len(clarity_values)) if clarity_values else 0.0) <= 90.0)

    return {
        "trap_distribution_status": trap_distribution_status,
        "wick_variation_status": wick_variation_status,
        "hold_time_status": hold_time_status,
        "oi_normalization_status": oi_normalization_status,
        "volume_normalization_status": volume_normalization_status,
        "clarity_status": clarity_status,
        "generated_at": generated_at,
        "detail": {
            "cycles_analyzed": len(rows),
            "trap_probability": _distribution(trap_values),
            "rejection_wick_score": _distribution(wick_values),
            "time_above_level_ratio": _distribution(hold_values),
            "oi_shift_score": _distribution(oi_values),
            "volume_expansion_score": _distribution(vol_values),
            "clarity": _distribution(clarity_values),
        },
    }
