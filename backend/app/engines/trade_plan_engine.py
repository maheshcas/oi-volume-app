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
    _ = _to_float(probability_bull)  # kept for interface compatibility

    strategy_type = "Range"
    entry_zone = "Wait for clearer setup around key levels."
    stop_hint = "Keep stop beyond nearby structure."
    target_primary = t1
    target_extended = t2
    caution_note = "Low clarity session. Prefer range trades."

    if conf < 45:
        strategy_type = "Low Clarity Range"
        entry_zone = "Prefer range trades near support/resistance."
        stop_hint = "Keep stop outside range boundary."
        target_primary = t1 if t1 is not None else res
        target_extended = t2 if t2 is not None else sup
        caution_note = "Low clarity session. Prefer range trades."
    elif bias == "Bullish" and conf > 55:
        strategy_type = "Directional Bullish"
        entry_zone = (
            f"Near resistance breakout ({res:.0f}) or pullback to support ({sup:.0f})."
            if sup is not None and res is not None
            else "Near resistance breakout or pullback to support."
        )
        stop_hint = f"Below support ({sup:.0f})." if sup is not None else "Below support."
        caution_note = "Keep execution selective and size controlled."
    elif bias == "Bearish" and conf > 55:
        strategy_type = "Directional Bearish"
        entry_zone = (
            f"Near support breakdown ({sup:.0f}) or pullback to resistance ({res:.0f})."
            if sup is not None and res is not None
            else "Near support breakdown or pullback to resistance."
        )
        stop_hint = f"Above resistance ({res:.0f})." if res is not None else "Above resistance."
        caution_note = "Keep execution selective and size controlled."
    else:
        strategy_type = "Balanced"
        entry_zone = "Wait for cleaner move around support/resistance."
        stop_hint = "Use tighter stop until clarity improves."
        caution_note = "Mixed structure; avoid aggressive entries."

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
