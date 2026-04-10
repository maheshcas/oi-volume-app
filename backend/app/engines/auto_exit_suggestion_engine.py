from __future__ import annotations

from typing import Any


def generate_auto_exit_suggestion(
    *,
    bias: str,
    momentum_exhaustion: bool,
    reversal_probability: float | int,
    regime_shift_alert: bool,
    confidence: float | int,
    trap_risk: float | int = 0,
) -> dict[str, Any]:
    rev = float(reversal_probability)
    conf = float(confidence)
    trap = float(trap_risk)

    exit_signal = False
    exit_reason: str | None = None
    exit_trigger: str | None = None   # which condition(s) fired
    exit_urgency: str = "Low"         # Low | Moderate | High

    is_bullish = bias == "Bullish"
    is_bearish = bias == "Bearish"

    if not (is_bullish or is_bearish):
        return {"exit_signal": False, "exit_reason": None, "exit_trigger": None, "exit_urgency": "Low"}

    triggers_fired: list[str] = []
    if bool(momentum_exhaustion):
        triggers_fired.append("momentum_exhaustion")
    if rev > 60:
        triggers_fired.append("reversal_probability")
    if bool(regime_shift_alert):
        triggers_fired.append("regime_shift")
    if trap > 65:
        triggers_fired.append("trap_risk")

    if not triggers_fired:
        return {"exit_signal": False, "exit_reason": None, "exit_trigger": None, "exit_urgency": "Low"}

    exit_signal = True
    exit_trigger = "|".join(triggers_fired)

    # Urgency: high if 2+ triggers fired or trap is dominant; moderate if only one.
    if len(triggers_fired) >= 2 or "trap_risk" in triggers_fired:
        exit_urgency = "High"
    elif conf < 40:
        exit_urgency = "High"
    else:
        exit_urgency = "Moderate"

    # Specific reason based on primary trigger.
    if "trap_risk" in triggers_fired and "momentum_exhaustion" in triggers_fired:
        exit_reason = "Trap + Exhaustion Combo — high reversal risk" if is_bullish else "Trap + Exhaustion Combo — breakdown risk"
    elif "trap_risk" in triggers_fired:
        exit_reason = "Trap risk elevated — likely false breakout" if is_bullish else "Trap risk elevated — likely false breakdown"
    elif "regime_shift" in triggers_fired and "momentum_exhaustion" in triggers_fired:
        exit_reason = "Regime shift with momentum fade — trend may be ending" if is_bullish else "Regime shift with exhaustion — recovery may be failing"
    elif "regime_shift" in triggers_fired:
        exit_reason = "Regime transition detected — directional edge reduced"
    elif "momentum_exhaustion" in triggers_fired:
        exit_reason = "Momentum fading — volume/OI no longer supporting move" if is_bullish else "Downside exhaustion — sellers losing follow-through"
    elif "reversal_probability" in triggers_fired:
        exit_reason = f"Reversal probability elevated ({int(rev)}%) — caution on longs" if is_bullish else f"Reversal probability elevated ({int(rev)}%) — caution on shorts"
    else:
        exit_reason = "Exit conditions met"

    return {
        "exit_signal": exit_signal,
        "exit_reason": exit_reason,
        "exit_trigger": exit_trigger,
        "exit_urgency": exit_urgency,
    }

