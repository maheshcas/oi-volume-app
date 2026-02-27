from __future__ import annotations

from typing import Any


def _to_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def generate_trade_plan(
    *,
    bias: str,
    probability_bull: float | int | None,
    confidence: float | int | None,
    support: float | int | None,
    resistance: float | int | None,
    target1: float | int | None,
    target2: float | int | None,
    trap_risk: float | int | None,
    volatility_state: str | None,
) -> dict[str, dict[str, Any]]:
    """
    Build a concise retail-friendly trade plan.

    Rules:
    - Bullish + confidence > 55:
      entry near resistance breakout OR pullback to support.
    - Bearish + confidence > 55:
      entry near support breakdown OR pullback to resistance.
    - confidence < 45:
      low-clarity range preference.
    """
    conf = _to_float(confidence) or 0.0
    trap = _to_float(trap_risk) or 0.0
    sup = _to_float(support)
    res = _to_float(resistance)
    t1 = _to_float(target1)
    t2 = _to_float(target2)
    bull_prob = _to_float(probability_bull) or 50.0

    strategy_type = "Range / Wait"
    entry_zone = "Wait for clearer setup around support/resistance."
    stop_hint = "Keep stops outside the nearby range."
    target_primary = t1
    target_extended = t2
    caution_note = "Low clarity session. Prefer range trades."

    if conf < 45:
        strategy_type = "Low Clarity Range"
        entry_zone = (
            f"Fade edges near {sup:.0f}-{res:.0f} when rejection appears."
            if sup is not None and res is not None
            else "Fade range edges after rejection confirmation."
        )
        stop_hint = (
            f"Stop beyond range edge ({sup:.0f}/{res:.0f})."
            if sup is not None and res is not None
            else "Stop beyond range edge."
        )
        target_primary = res if bull_prob >= 50 else sup
        target_extended = sup if bull_prob >= 50 else res
    elif bias == "Bullish" and conf > 55:
        strategy_type = "Directional Bullish"
        entry_zone = (
            f"Breakout above {res:.0f} or pullback near {sup:.0f}."
            if sup is not None and res is not None
            else "Breakout continuation or pullback setup."
        )
        stop_hint = f"Below support {sup:.0f}." if sup is not None else "Below nearest support."
        caution_note = "Follow only if participation stays strong."
    elif bias == "Bearish" and conf > 55:
        strategy_type = "Directional Bearish"
        entry_zone = (
            f"Breakdown below {sup:.0f} or pullback near {res:.0f}."
            if sup is not None and res is not None
            else "Breakdown continuation or pullback setup."
        )
        stop_hint = f"Above resistance {res:.0f}." if res is not None else "Above nearest resistance."
        caution_note = "Follow only if downside participation stays strong."
    else:
        strategy_type = "Balanced / Selective"
        entry_zone = "Take only high-quality setups near key levels."
        stop_hint = "Use tighter risk controls until structure improves."
        caution_note = "Mixed structure; avoid aggressive entries."

    # Keep risk phrasing simple and concise.
    if trap >= 65:
        caution_note = f"{caution_note} Trap risk is elevated."
    elif volatility_state == "Expanding":
        caution_note = f"{caution_note} Volatility is expanding."

    return {
        "trade_plan": {
            "strategy_type": strategy_type,
            "entry_zone": entry_zone,
            "stop_hint": stop_hint,
            "target_primary": target_primary,
            "target_extended": target_extended,
            "caution_note": caution_note,
        }
    }

