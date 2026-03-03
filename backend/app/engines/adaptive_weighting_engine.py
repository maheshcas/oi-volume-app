from __future__ import annotations

from typing import Any


def _adjust_weight(weight: float, accuracy: float) -> float:
    if accuracy > 0.65:
        weight *= 1.05
    elif accuracy < 0.45:
        weight *= 0.95
    return weight


def compute_adaptive_weights(
    *,
    engine_stats: dict[str, float | int],
    current_weights: dict[str, float | int],
) -> dict[str, Any]:
    new_weights = {
        "oi": _adjust_weight(float(current_weights.get("oi", 0.30) or 0.30), float(engine_stats.get("oi_accuracy", 0.55) or 0.55)),
        "volume": _adjust_weight(
            float(current_weights.get("volume", 0.25) or 0.25),
            float(engine_stats.get("volume_accuracy", 0.55) or 0.55),
        ),
        "breakout": _adjust_weight(
            float(current_weights.get("breakout", 0.20) or 0.20),
            float(engine_stats.get("breakout_accuracy", 0.55) or 0.55),
        ),
        "sr": _adjust_weight(float(current_weights.get("sr", 0.15) or 0.15), float(engine_stats.get("sr_accuracy", 0.55) or 0.55)),
    }

    for key in new_weights:
        new_weights[key] = min(max(float(new_weights[key]), 0.10), 0.40)

    total = sum(new_weights.values())
    if total <= 0:
        # Fallback safety
        new_weights = {"oi": 0.30, "volume": 0.25, "breakout": 0.20, "sr": 0.15}
        total = sum(new_weights.values())

    for key in new_weights:
        new_weights[key] = float(new_weights[key]) / total

    return {"adaptive_weights": new_weights}

