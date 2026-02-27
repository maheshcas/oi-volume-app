import math
from typing import Any

DEFAULT_WEIGHTS = {
    "oi": 0.30,
    "volume": 0.20,
    "atm": 0.15,
    "breakout": 0.20,
    "regime": 0.15,
}

REGIME_WEIGHTS: dict[str, dict[str, float]] = {
    "Trend Day": {
        "oi": 0.32,
        "volume": 0.22,
        "atm": 0.12,
        "breakout": 0.24,
        "regime": 0.10,
    },
    "Breakdown": {
        "oi": 0.32,
        "volume": 0.22,
        "atm": 0.12,
        "breakout": 0.24,
        "regime": 0.10,
    },
    "Range Day": {
        "oi": 0.34,
        "volume": 0.18,
        "atm": 0.18,
        "breakout": 0.12,
        "regime": 0.18,
    },
    "Trap Risk": {
        "oi": 0.24,
        "volume": 0.18,
        "atm": 0.18,
        "breakout": 0.14,
        "regime": 0.26,
    },
    "Short Covering": {
        "oi": 0.30,
        "volume": 0.24,
        "atm": 0.14,
        "breakout": 0.20,
        "regime": 0.12,
    },
}


def _validate_range(name: str, value: float, min_value: float, max_value: float) -> None:
    if not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    if value < min_value or value > max_value:
        raise ValueError(f"{name} must be in range [{min_value}, {max_value}]")


def probability_formula_v2(inputs: dict[str, float]) -> dict[str, int]:
    """
    Probability Formula v2
    Returns integer bull/bear probabilities (sum=100) and confidence (0-100).
    """
    required = [
        "oi_bull_component",
        "oi_bear_component",
        "volume_strength_score",
        "breakout_up_score",
        "breakout_down_score",
        "atm_participation_score",
        "pcr_bias_score",
        "volatility_factor",
        "trap_probability",
    ]
    missing = [k for k in required if k not in inputs]
    if missing:
        raise ValueError(f"Missing required inputs: {', '.join(missing)}")

    oi_bull_component = float(inputs["oi_bull_component"])
    oi_bear_component = float(inputs["oi_bear_component"])
    volume_strength_score = float(inputs["volume_strength_score"])
    breakout_up_score = float(inputs["breakout_up_score"])
    breakout_down_score = float(inputs["breakout_down_score"])
    atm_participation_score = float(inputs["atm_participation_score"])
    pcr_bias_score = float(inputs["pcr_bias_score"])
    volatility_factor = float(inputs["volatility_factor"])
    trap_probability = float(inputs["trap_probability"])

    _validate_range("oi_bull_component", oi_bull_component, 0.0, 1.0)
    _validate_range("oi_bear_component", oi_bear_component, 0.0, 1.0)
    _validate_range("volume_strength_score", volume_strength_score, 0.0, 1.0)
    _validate_range("breakout_up_score", breakout_up_score, 0.0, 1.0)
    _validate_range("breakout_down_score", breakout_down_score, 0.0, 1.0)
    _validate_range("atm_participation_score", atm_participation_score, 0.0, 1.0)
    _validate_range("pcr_bias_score", pcr_bias_score, -1.0, 1.0)
    _validate_range("volatility_factor", volatility_factor, 0.0, 1.0)
    _validate_range("trap_probability", trap_probability, 0.0, 1.0)

    # STEP 1: Raw scores
    bull_raw = (
        (0.25 * oi_bull_component)
        + (0.20 * volume_strength_score)
        + (0.15 * breakout_up_score)
        + (0.10 * atm_participation_score)
        + (0.10 * max(pcr_bias_score, 0.0))
        + (0.10 * volatility_factor)
        - (0.10 * trap_probability)
    )

    bear_raw = (
        (0.25 * oi_bear_component)
        + (0.20 * volume_strength_score)
        + (0.15 * breakout_down_score)
        + (0.10 * atm_participation_score)
        + (0.10 * abs(min(pcr_bias_score, 0.0)))
        + (0.10 * volatility_factor)
        - (0.10 * trap_probability)
    )

    # STEP 2: Softmax normalization (stable)
    m = max(bull_raw, bear_raw)
    bull_exp = math.exp(bull_raw - m)
    bear_exp = math.exp(bear_raw - m)
    denom = bull_exp + bear_exp
    prob_bull = bull_exp / denom
    prob_bear = bear_exp / denom

    # STEP 3: Confidence
    confidence = abs(prob_bull - prob_bear) * ((oi_bull_component + oi_bear_component) / 2.0) * 100.0
    confidence = max(0.0, min(100.0, confidence))

    # STEP 4: Trap adjustment
    if trap_probability > 0.6:
        confidence *= 0.7

    bull_pct = int(round(prob_bull * 100))
    bull_pct = max(0, min(100, bull_pct))
    bear_pct = 100 - bull_pct

    return {
        "probability_bull": bull_pct,
        "probability_bear": bear_pct,
        "confidence": int(round(max(0.0, min(100.0, confidence)))),
    }


def master_arbitration_layer(
    oi: dict[str, Any],
    volume: dict[str, Any],
    breakout: dict[str, Any],
    trap: dict[str, Any],
    regime: dict[str, Any],
    regime_type: str | None = None,
    weights_override: dict[str, float] | None = None,
    previous_score: float | None = None,
    alpha: float = 0.4,
    pcr_bias_score: float = 0.0,
    volatility_factor: float = 0.5,
    atr_value: float | None = None,
    avg_atr: float | None = None,
) -> dict[str, Any]:
    def _clamp(x: float, lo: float, hi: float) -> float:
        return max(lo, min(hi, float(x)))

    def _sign(x: float, eps: float = 1e-6) -> int:
        if x > eps:
            return 1
        if x < -eps:
            return -1
        return 0

    # 1) Each engine score in [-1, +1]
    oi_alignment = str(oi.get("alignment", "mixed"))
    oi_strength = _clamp(float(oi.get("oi_strength", 0.0) or 0.0), 0.0, 1.0)
    oi_score = 0.0
    if oi_alignment == "bullish":
        oi_score = oi_strength
    elif oi_alignment == "bearish":
        oi_score = -oi_strength

    rvr_ce = _clamp(float(volume.get("rvr", {}).get("ce", 0.0) or 0.0), 0.0, 1.0)
    rvr_pe = _clamp(float(volume.get("rvr", {}).get("pe", 0.0) or 0.0), 0.0, 1.0)
    volume_direction = _clamp(rvr_pe - rvr_ce, -1.0, 1.0)
    volume_expansion = bool(volume.get("volume_expansion"))
    volume_score = _clamp(volume_direction * (1.0 if volume_expansion else 0.7), -1.0, 1.0)

    atm_participation = _clamp(float(volume.get("atm_participation", 0.0) or 0.0), 0.0, 1.0)
    atm_dir = 1.0 if oi_alignment == "bullish" else -1.0 if oi_alignment == "bearish" else 0.0
    atm_score = _clamp(atm_participation * atm_dir, -1.0, 1.0)

    breakout_score = 1.0 if breakout.get("breakout_up") else -1.0 if breakout.get("breakout_down") else 0.0

    mapped_regime = str(regime.get("regime") or "")
    if mapped_regime == "Trend Day":
        regime_score = 0.5 if oi_alignment != "bearish" else -0.5
    elif mapped_regime == "Breakdown":
        regime_score = -0.8
    elif mapped_regime == "Short Covering":
        regime_score = 0.6
    elif mapped_regime == "Trap Risk":
        regime_score = 0.0
    else:
        regime_score = 0.0

    engine_scores = {
        "oi": _clamp(oi_score, -1.0, 1.0),
        "volume": _clamp(volume_score, -1.0, 1.0),
        "atm": _clamp(atm_score, -1.0, 1.0),
        "breakout": _clamp(breakout_score, -1.0, 1.0),
        "regime": _clamp(regime_score, -1.0, 1.0),
    }

    # 2) Weighted aggregation (regime-based with safe fallback and normalization)
    regime_used = str(regime_type or regime.get("regime_type") or regime.get("regime") or "default")
    if weights_override:
        selected_weights = {k: float(weights_override.get(k, DEFAULT_WEIGHTS[k])) for k in DEFAULT_WEIGHTS.keys()}
        regime_used = f"{regime_used}:custom"
    else:
        selected_weights = REGIME_WEIGHTS.get(regime_used, DEFAULT_WEIGHTS)
    raw_weight_sum = sum(float(v) for v in selected_weights.values())
    if raw_weight_sum <= 0:
        selected_weights = DEFAULT_WEIGHTS
        raw_weight_sum = sum(DEFAULT_WEIGHTS.values())
        regime_used = "default"
    weights = {k: float(selected_weights.get(k, 0.0)) / raw_weight_sum for k in DEFAULT_WEIGHTS.keys()}

    # 3) Aggregate score
    raw_score = sum(engine_scores[k] * weights[k] for k in weights.keys())
    raw_score = _clamp(raw_score, -1.0, 1.0)

    # Bias smoothing (EMA): first run uses raw score.
    alpha = _clamp(alpha, 0.0, 1.0)
    if previous_score is None:
        score = raw_score
    else:
        score = (alpha * raw_score) + ((1.0 - alpha) * _clamp(previous_score, -1.0, 1.0))
        score = _clamp(score, -1.0, 1.0)

    # 4) Convert to probabilities
    bull_prob = _clamp((score + 1.0) / 2.0, 0.0, 1.0)
    bear_prob = 1.0 - bull_prob

    # 5) Spread
    spread = abs(bull_prob - bear_prob)

    # 6) Agreement ratio
    score_sign = _sign(score)
    agreeing = 0
    for val in engine_scores.values():
        if _sign(val) == score_sign:
            agreeing += 1
    agreement_ratio = agreeing / max(1, len(engine_scores))

    # 7/8) Confidence
    confidence = (spread * 0.6) + (agreement_ratio * 0.4)

    # Optional confidence stabilizer:
    # confidence *= clamp(atr_value / avg_atr, 0.8, 1.2)
    # Falls back to mapped volatility_factor when explicit ATR inputs are unavailable.
    if atr_value is not None and avg_atr is not None and float(avg_atr) > 0:
        raw_vol_ratio = float(atr_value) / float(avg_atr)
    else:
        raw_vol_ratio = 0.8 + (0.4 * _clamp(float(volatility_factor), 0.0, 1.0))
    if raw_vol_ratio > 1.2:
        volatility_state = "Expanding"
    elif raw_vol_ratio < 0.8:
        volatility_state = "Contracting"
    else:
        volatility_state = "Stable"
    volatility_modifier = _clamp(raw_vol_ratio, 0.8, 1.2)
    confidence = confidence * volatility_modifier

    confidence_percent = int(round(confidence * 100))
    confidence_percent = max(15, min(confidence_percent, 95))

    bull_pct = int(round(bull_prob * 100))
    bull_pct = max(0, min(100, bull_pct))
    bear_pct = 100 - bull_pct

    if bull_pct > 55:
        bias = "Bullish"
    elif bear_pct > 55:
        bias = "Bearish"
    else:
        bias = "Neutral"

    if confidence_percent >= 75:
        strength_label = "Strong"
    elif confidence_percent >= 50:
        strength_label = "Moderate"
    else:
        strength_label = "Weak"

    regime_out = "Range"
    if mapped_regime in ("Trend Day", "Breakdown"):
        regime_out = "Trend"
    elif mapped_regime == "Trap Risk":
        regime_out = "Trap Risk"
    elif mapped_regime == "Range Day":
        regime_out = "Range"

    trap_probability = _clamp(float(trap.get("trap_probability_pct", 0) or 0) / 100.0, 0.0, 1.0)
    if trap_probability > 0.6 or trap.get("is_trap"):
        regime_out = "Trap Risk"

    driver_map = {
        "oi": ("OI pressure", "OI support"),
        "volume": ("Volume-led downside", "Volume-led upside"),
        "atm": ("ATM build-up downside", "ATM build-up upside"),
        "breakout": ("Breakdown pressure", "Breakout pressure"),
        "regime": ("Regime downside", "Regime upside"),
    }
    weighted_contrib = {k: engine_scores[k] * weights[k] for k in weights.keys()}
    top_drivers = sorted(weighted_contrib.items(), key=lambda kv: abs(kv[1]), reverse=True)[:2]
    primary_drivers = []
    for key, val in top_drivers:
        neg_label, pos_label = driver_map.get(key, (key, key))
        primary_drivers.append(pos_label if val >= 0 else neg_label)

    if bias == "Bearish":
        summary_statement = "Call writers dominating near resistance; downside pressure intact."
    elif bias == "Bullish":
        summary_statement = "Put support strengthening near key levels; upside pressure intact."
    else:
        summary_statement = "Two-sided positioning near spot; market structure remains range-bound."

    return {
        "bias": bias,
        "regime": regime_out,
        "probability_bull": bull_pct,
        "probability_bear": bear_pct,
        "confidence": confidence_percent,
        "strength_label": strength_label,
        "bull_probability": bull_pct,
        "bear_probability": bear_pct,
        "confidence_percent": confidence_percent,
        "weighted_score": round(score, 4),
        "raw_weighted_score": round(raw_score, 4),
        "structure_score": round(score, 4),
        "alignment_ratio": round(agreement_ratio, 4),
        "primary_drivers": primary_drivers,
        "summary_statement": summary_statement,
        "regime_used": regime_used,
        "weight_distribution": {k: round(v, 4) for k, v in weights.items()},
        "engine_scores": {k: round(v, 4) for k, v in engine_scores.items()},
        "volatility_ratio": round(float(raw_vol_ratio), 4),
        "volatility_state": volatility_state,
        "volatility_modifier": round(float(volatility_modifier), 4),
        "explanation": summary_statement,
    }
