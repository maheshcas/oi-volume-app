from __future__ import annotations

from typing import Any


def compute_early_reversal_probability(
    *,
    momentum_exhaustion: bool,
    trap_risk: float | int,
    bias_stability_score: float | int,
    atr_ratio: float | int,
    alignment_ratio: float | int,
) -> dict[str, Any]:
    reversal_score = 0

    if bool(momentum_exhaustion):
        reversal_score += 30

    if float(trap_risk) > 40:
        reversal_score += 25

    if float(bias_stability_score) < 50:
        reversal_score += 20

    if float(atr_ratio) < 0.9:
        reversal_score += 15

    if float(alignment_ratio) < 0.5:
        reversal_score += 10

    return {"reversal_probability": min(reversal_score, 95)}

