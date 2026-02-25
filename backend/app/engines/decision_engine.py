from typing import Any


def master_arbitration_layer(
    oi: dict[str, Any],
    volume: dict[str, Any],
    breakout: dict[str, Any],
    trap: dict[str, Any],
    regime: dict[str, Any],
) -> dict[str, Any]:
    bias = "Neutral"
    regime_out = "Range"
    prob_bull = 50
    prob_bear = 50
    confidence = 50
    explanation = "Default range arbitration."

    breakout_up = bool(breakout.get("breakout_up"))
    breakout_down = bool(breakout.get("breakout_down"))
    volume_exp = bool(volume.get("volume_expansion"))
    oi_align = oi.get("alignment", "mixed")

    # LEVEL 1
    if breakout_up and volume_exp:
        bias = "Bullish"
        regime_out = "Trend"
        prob_bull, prob_bear, confidence = 70, 30, 80
        explanation = "Confirmed upside breakout with volume confirmation."
    elif breakout_down and volume_exp:
        bias = "Bearish"
        regime_out = "Trend"
        prob_bull, prob_bear, confidence = 30, 70, 80
        explanation = "Confirmed downside breakout with volume confirmation."
    # LEVEL 2
    elif oi_align in ("bullish", "bearish") and volume_exp:
        regime_out = "Trend"
        confidence = 62
        if oi_align == "bullish":
            bias = "Bullish"
            prob_bull, prob_bear = 60, 40
            explanation = "OI and volume aligned for bullish developing trend."
        else:
            bias = "Bearish"
            prob_bull, prob_bear = 40, 60
            explanation = "OI and volume aligned for bearish developing trend."
    # LEVEL 3
    else:
        bias = "Neutral"
        regime_out = "Range"
        prob_bull, prob_bear, confidence = 50, 50, 48
        explanation = "No directional confirmation; range structure dominates."

    # LEVEL 4 override
    if trap.get("is_trap"):
        regime_out = "Trap Risk"
        confidence = max(0, confidence - 20)
        explanation += " Trap override active due to weak breakout quality."

    # respect regime classification if trap not active and level logic didn't classify uniquely
    if regime_out != "Trap Risk":
        mapped = regime.get("regime")
        if mapped in ("Trend Day", "Breakdown"):
            regime_out = "Trend"
        elif mapped == "Range Day":
            regime_out = "Range"

    return {
        "bias": bias,
        "regime": regime_out,
        "probability_bull": int(prob_bull),
        "probability_bear": int(prob_bear),
        "confidence": int(confidence),
        "explanation": explanation,
    }
