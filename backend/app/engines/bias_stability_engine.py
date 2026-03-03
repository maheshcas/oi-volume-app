from __future__ import annotations

import statistics
from typing import Any


def compute_bias_stability(last_10_smoothed_scores: list[float] | None) -> dict[str, Any]:
    scores = [float(x) for x in (last_10_smoothed_scores or []) if x is not None]
    if len(scores) < 2:
        return {
            "bias_stability_label": "Moderate",
            "bias_stability_score": 55,
        }

    std_dev = float(statistics.stdev(scores))

    if std_dev < 0.15:
        stability = "High"
        stability_score = 80
    elif std_dev < 0.30:
        stability = "Moderate"
        stability_score = 55
    else:
        stability = "Low"
        stability_score = 30

    return {
        "bias_stability_label": stability,
        "bias_stability_score": stability_score,
    }

