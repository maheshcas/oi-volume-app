from __future__ import annotations

from typing import Any


def generate_auto_exit_suggestion(
    *,
    bias: str,
    momentum_exhaustion: bool,
    reversal_probability: float | int,
    regime_shift_alert: bool,
    confidence: float | int,
) -> dict[str, Any]:
    _ = confidence  # kept for interface completeness

    exit_signal = False
    exit_reason: str | None = None

    if bias == "Bullish":
        if bool(momentum_exhaustion) or float(reversal_probability) > 60 or bool(regime_shift_alert):
            exit_signal = True
            exit_reason = "Momentum Weakening / Reversal Risk"
    elif bias == "Bearish":
        if bool(momentum_exhaustion) or float(reversal_probability) > 60 or bool(regime_shift_alert):
            exit_signal = True
            exit_reason = "Downside Exhaustion / Reversal Risk"

    return {
        "exit_signal": exit_signal,
        "exit_reason": exit_reason,
    }

