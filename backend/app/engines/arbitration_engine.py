from __future__ import annotations

from typing import Any


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def _normalize_regime(regime: str) -> str:
    r = str(regime or "").strip().lower()
    if "trend" in r or "breakdown" in r:
        return "Trend"
    if "range" in r:
        return "Range"
    return "Transition"


def _regime_weights(regime: str) -> dict[str, float]:
    normalized = _normalize_regime(regime)
    if normalized == "Trend":
        return {"oi": 0.30, "volume": 0.25, "price": 0.25, "breakout": 0.20}
    if normalized == "Range":
        # Rule-set as requested; sum intentionally < 1 in source, normalized below.
        base = {"oi": 0.40, "volume": 0.20, "price": 0.15, "breakout": 0.10}
        total = sum(base.values())
        return {k: v / total for k, v in base.items()}
    return {"oi": 0.25, "volume": 0.25, "price": 0.25, "breakout": 0.25}


def run_arbitration(
    oi_score: float,
    volume_score: float,
    price_score: float,
    breakout_score: float,
    trap_risk: float,
    regime: str,
    previous_score: float,
) -> dict[str, Any]:
    """
    Signal arbitration framework.
    Scores expected in [-1.0, +1.0], trap_risk in [0.0, 1.0].
    """
    w = _regime_weights(regime)

    oi_score = _clamp(oi_score, -1.0, 1.0)
    volume_score = _clamp(volume_score, -1.0, 1.0)
    price_score = _clamp(price_score, -1.0, 1.0)
    breakout_score = _clamp(breakout_score, -1.0, 1.0)
    trap_risk = _clamp(trap_risk, 0.0, 1.0)
    previous_score = _clamp(previous_score, -1.0, 1.0)

    final_raw_score = (
        oi_score * w["oi"]
        + volume_score * w["volume"]
        + price_score * w["price"]
        + breakout_score * w["breakout"]
        - trap_risk * 0.25
    )
    final_raw_score = _clamp(final_raw_score, -1.0, 1.0)

    smoothed_score = (0.6 * previous_score) + (0.4 * final_raw_score)
    smoothed_score = _clamp(smoothed_score, -1.0, 1.0)

    if smoothed_score > 0.2:
        bias = "Bullish"
    elif smoothed_score < -0.2:
        bias = "Bearish"
    else:
        bias = "Neutral"

    return {
        "raw_score": round(final_raw_score, 4),
        "smoothed_score": round(smoothed_score, 4),
        "bias": bias,
        "weights": w,
        "regime_used": _normalize_regime(regime),
    }
