import math
from typing import Any


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
    pcr_bias_score: float = 0.0,
    volatility_factor: float = 0.5,
) -> dict[str, Any]:
    oi_alignment = str(oi.get("alignment", "mixed"))
    oi_strength = float(oi.get("oi_strength", 0.0) or 0.0)
    ce_conc = float(oi.get("concentration", {}).get("ce", 0.0) or 0.0)
    pe_conc = float(oi.get("concentration", {}).get("pe", 0.0) or 0.0)

    if oi_alignment == "bullish":
        oi_bull_component = min(1.0, (0.6 * oi_strength) + (0.4 * pe_conc))
        oi_bear_component = min(1.0, 0.4 * ce_conc)
    elif oi_alignment == "bearish":
        oi_bear_component = min(1.0, (0.6 * oi_strength) + (0.4 * ce_conc))
        oi_bull_component = min(1.0, 0.4 * pe_conc)
    else:
        oi_bull_component = min(1.0, pe_conc * 0.8)
        oi_bear_component = min(1.0, ce_conc * 0.8)

    rvr_ce = float(volume.get("rvr", {}).get("ce", 0.0) or 0.0)
    rvr_pe = float(volume.get("rvr", {}).get("pe", 0.0) or 0.0)
    atm_participation = float(volume.get("atm_participation", 0.0) or 0.0)
    volume_strength_score = min(
        1.0,
        (0.5 * atm_participation) + (0.25 * rvr_ce) + (0.25 * rvr_pe) + (0.1 if volume.get("volume_expansion") else 0.0),
    )

    breakout_up_score = 1.0 if breakout.get("breakout_up") else 0.0
    breakout_down_score = 1.0 if breakout.get("breakout_down") else 0.0
    trap_probability = min(1.0, max(0.0, float(trap.get("trap_probability_pct", 0) or 0) / 100.0))

    probs = probability_formula_v2(
        {
            "oi_bull_component": oi_bull_component,
            "oi_bear_component": oi_bear_component,
            "volume_strength_score": volume_strength_score,
            "breakout_up_score": breakout_up_score,
            "breakout_down_score": breakout_down_score,
            "atm_participation_score": atm_participation,
            "pcr_bias_score": pcr_bias_score,
            "volatility_factor": volatility_factor,
            "trap_probability": trap_probability,
        }
    )

    prob_bull = probs["probability_bull"]
    prob_bear = probs["probability_bear"]
    confidence = probs["confidence"]

    if prob_bull > 55:
        bias = "Bullish"
    elif prob_bear > 55:
        bias = "Bearish"
    else:
        bias = "Neutral"

    regime_out = "Range"
    mapped = regime.get("regime")
    if mapped in ("Trend Day", "Breakdown"):
        regime_out = "Trend"
    elif mapped == "Trap Risk":
        regime_out = "Trap Risk"
    elif mapped == "Range Day":
        regime_out = "Range"

    if trap_probability > 0.6 or trap.get("is_trap"):
        regime_out = "Trap Risk"

    explanation = (
        f"Prob-v2 arbitration: Bull {prob_bull}%, Bear {prob_bear}%, "
        f"OI align={oi_alignment}, volume_expansion={bool(volume.get('volume_expansion'))}."
    )

    return {
        "bias": bias,
        "regime": regime_out,
        "probability_bull": int(prob_bull),
        "probability_bear": int(prob_bear),
        "confidence": int(confidence),
        "explanation": explanation,
    }
