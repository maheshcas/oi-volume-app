from __future__ import annotations


def detect_momentum_exhaustion(
    *,
    smoothed_score: float,
    previous_smoothed_score: float,
    volume_ratio: float,
    previous_volume_ratio: float,
    oi_delta: float,
    previous_oi_delta: float,
    atr_ratio: float,
    previous_atr_ratio: float,
) -> dict[str, object]:
    exhaustion = False
    exhaustion_type: str | None = None

    if smoothed_score > 0.4:
        if (
            volume_ratio < previous_volume_ratio
            and oi_delta < previous_oi_delta
            and atr_ratio < previous_atr_ratio
        ):
            exhaustion = True
            exhaustion_type = "Bullish Exhaustion"
    elif smoothed_score < -0.4:
        if (
            volume_ratio < previous_volume_ratio
            and oi_delta < previous_oi_delta
            and atr_ratio < previous_atr_ratio
        ):
            exhaustion = True
            exhaustion_type = "Bearish Exhaustion"

    return {
        "momentum_exhaustion": exhaustion,
        "exhaustion_type": exhaustion_type,
    }

