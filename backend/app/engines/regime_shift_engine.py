from __future__ import annotations


def _sign(value: float) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def detect_regime_shift(
    *,
    previous_smoothed_score: float,
    current_smoothed_score: float,
    previous_regime: str,
    current_regime: str,
    previous_alignment: float,
    current_alignment: float,
    previous_atr_ratio: float,
    current_atr_ratio: float,
) -> dict[str, object]:
    shift_detected = False
    shift_reason: str | None = None

    if _sign(previous_smoothed_score) != _sign(current_smoothed_score):
        if abs(current_smoothed_score - previous_smoothed_score) > 0.25:
            shift_detected = True
            shift_reason = "Directional Bias Flip"
    elif previous_regime != current_regime:
        shift_detected = True
        shift_reason = "Regime Transition"
    elif abs(current_atr_ratio - previous_atr_ratio) > 0.2:
        shift_detected = True
        shift_reason = "Volatility Expansion"
    elif abs(current_alignment - previous_alignment) > 0.3:
        shift_detected = True
        shift_reason = "Structure Realignment"

    return {
        "regime_shift_alert": shift_detected,
        "regime_shift_reason": shift_reason,
    }

