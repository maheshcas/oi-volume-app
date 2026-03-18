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
    if regime in ("Trend Day", "Breakdown", "Breakdown Day", "Short Covering"):
        return "trend"
    if regime == "Range Day":
        return "range"
    if regime == "Transition":
        return "transition"
    if regime in ("Trap Risk", "Trap Day"):
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


def _apply_regime_hysteresis(
    *,
    detected_regime: str,
    current_committed_regime: str | None,
    candidate_regime: str | None,
    candidate_regime_count: int,
) -> tuple[str, str | None, int]:
    detected = str(detected_regime or "")
    committed = str(current_committed_regime or "")
    candidate = str(candidate_regime or "") or None
    count = int(candidate_regime_count or 0)

    if not committed:
        return detected, None, 0
    if detected == committed:
        return committed, None, 0
    if candidate and detected == candidate:
        count += 1
    else:
        candidate = detected
        count = 1
    if count >= 3:
        return detected, None, 0
    return committed, candidate, count


def run_regime_engine(
    oi: dict[str, Any],
    volume: dict[str, Any],
    breakout: dict[str, Any],
    trap: dict[str, Any],
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base_regime = classify_session_regime(oi, volume, breakout, trap)
    regime = base_regime
    if context:
        regime_type = _refined_regime_type(
            atr_ratio=float(context.get("atr_ratio", 1.0) or 1.0),
            score=float(context.get("score", 0.0) or 0.0),
            last_10_scores=[float(v) for v in (context.get("last_10_scores") or [])],
            breakout_confirmed=bool(context.get("breakout_confirmed", False)),
        )
        # Only override the base classification when the refined pass has a strong
        # trend/range read. Otherwise keep the base regime so hysteresis can
        # accumulate a real pending candidate across cycles.
        if regime_type == "trend":
            regime = "Trend Day"
        elif regime_type == "range":
            regime = "Range Day"
        else:
            regime = base_regime
    else:
        regime_type = _normalize_regime_type(regime)
    committed_regime, next_candidate_regime, next_candidate_regime_count = _apply_regime_hysteresis(
        detected_regime=regime,
        current_committed_regime=context.get("current_committed_regime") if context else None,
        candidate_regime=context.get("candidate_regime") if context else None,
        candidate_regime_count=int(context.get("candidate_regime_count", 0) or 0) if context else 0,
    )
    committed_regime_type = _normalize_regime_type(committed_regime)
    adjusted_weights, adjusted_thresholds = _regime_adjustments(committed_regime_type)
    return {
        "regime": committed_regime,
        "regime_type": committed_regime_type,
        "detected_regime": regime,
        "candidate_regime": next_candidate_regime,
        "candidate_regime_count": next_candidate_regime_count,
        "adjusted_weights": adjusted_weights,
        "adjusted_thresholds": adjusted_thresholds,
    }
