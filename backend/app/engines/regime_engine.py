from typing import Any


def classify_session_regime(oi: dict[str, Any], volume: dict[str, Any], breakout: dict[str, Any], trap: dict[str, Any]) -> str:
    if trap.get("is_trap"):
        return "Trap Risk"
    if breakout.get("breakout_up"):
        return "Trend Day"
    if breakout.get("breakout_down"):
        return "Breakdown"
    buildup = oi.get("buildup_type", "")
    if "Unwinding" in buildup:
        return "Short Covering"
    if volume.get("volume_expansion") and oi.get("alignment") in ("bullish", "bearish"):
        return "Trend Day"
    return "Range Day"


def _normalize_regime_type(regime: str) -> str:
    if regime in ("Trend Day", "Breakdown", "Short Covering"):
        return "trend"
    if regime == "Range Day":
        return "range"
    if regime == "Transition":
        return "transition"
    if regime == "Trap Risk":
        return "trap"
    return "neutral"


def _regime_adjustments(regime_type: str) -> tuple[dict[str, float], dict[str, float]]:
    # Baseline aligned with decision engine defaults.
    adjusted_weights = {
        "oi": 0.30,
        "volume": 0.20,
        "atm": 0.15,
        "breakout": 0.20,
        "regime": 0.15,
    }
    adjusted_thresholds = {
        "breakout_atr_multiplier": 1.20,
        "volume_expansion_threshold": 1.20,
    }

    if regime_type == "trend":
        # Lower breakout threshold by ~20% and increase volume sensitivity by ~15%.
        adjusted_thresholds["breakout_atr_multiplier"] = 0.96
        adjusted_thresholds["volume_expansion_threshold"] = 1.02
    elif regime_type == "range":
        # Increase OI clustering influence and reduce breakout impact by ~30%.
        adjusted_weights["oi"] = 0.36
        adjusted_weights["breakout"] = 0.14
        adjusted_weights["regime"] = 0.18
        adjusted_thresholds["breakout_atr_multiplier"] = 1.56
        adjusted_thresholds["volume_expansion_threshold"] = 1.20
    elif regime_type == "trap":
        adjusted_weights["regime"] = 0.24
        adjusted_weights["breakout"] = 0.12
        adjusted_thresholds["breakout_atr_multiplier"] = 1.35
        adjusted_thresholds["volume_expansion_threshold"] = 1.10

    return adjusted_weights, adjusted_thresholds


def _refined_regime_type(
    *,
    atr_ratio: float,
    score: float,
    last_10_scores: list[float],
    breakout_confirmed: bool,
) -> str:
    mean_score = (sum(last_10_scores) / len(last_10_scores)) if last_10_scores else 0.0
    if atr_ratio > 1.15 and abs(mean_score) > 0.35 and breakout_confirmed:
        return "trend"
    if atr_ratio < 0.9 and abs(score) < 0.25:
        return "range"
    return "transition"


def run_regime_engine(
    oi: dict[str, Any],
    volume: dict[str, Any],
    breakout: dict[str, Any],
    trap: dict[str, Any],
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    regime = classify_session_regime(oi, volume, breakout, trap)
    if context:
        regime_type = _refined_regime_type(
            atr_ratio=float(context.get("atr_ratio", 1.0) or 1.0),
            score=float(context.get("score", 0.0) or 0.0),
            last_10_scores=[float(v) for v in (context.get("last_10_scores") or [])],
            breakout_confirmed=bool(context.get("breakout_confirmed", False)),
        )
        regime = "Trend Day" if regime_type == "trend" else "Range Day" if regime_type == "range" else "Transition"
    else:
        regime_type = _normalize_regime_type(regime)
    adjusted_weights, adjusted_thresholds = _regime_adjustments(regime_type)
    return {
        "regime": regime,
        "regime_type": regime_type,
        "adjusted_weights": adjusted_weights,
        "adjusted_thresholds": adjusted_thresholds,
    }
