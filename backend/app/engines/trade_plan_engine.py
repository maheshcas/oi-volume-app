from __future__ import annotations

from typing import Any


def _to_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _fmt_level(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:,.0f}"


def _build_zone(label: str, low: float | None, high: float | None) -> dict[str, Any]:
    if low is None or high is None:
        return {
            "label": label,
            "low": None,
            "high": None,
            "text": "N/A",
        }
    zone_low = min(float(low), float(high))
    zone_high = max(float(low), float(high))
    return {
        "label": label,
        "low": round(zone_low, 2),
        "high": round(zone_high, 2),
        "text": f"{_fmt_level(zone_low)} - {_fmt_level(zone_high)}",
    }


def _build_execution_layer(
    *,
    support: float | None,
    resistance: float | None,
    spot: float | None,
    target1: float | None,
    target2: float | None,
    spc_state: str,
    spc_decision: str,
    trade_action: str,
    bias: str,
    trap_risk: float,
    range_locked: bool,
    no_edge: bool,
) -> dict[str, Any]:
    if support is None or resistance is None or resistance <= support:
        return {
            "entry_zone": "Wait for clean structure setup.",
            "stop_zone": "Use nearby structure invalidation.",
            "target_zone": "Set target only after confirmed direction.",
            "execution_mode": "Structure incomplete",
            "delta_band": "N/A",
            "delta_strike_guidance": "Avoid buying premium until structure normalizes.",
            "avoid_buying_premium": True,
            "entry_zone_bounds": _build_zone("Entry Zone", None, None),
            "stop_zone_bounds": _build_zone("Stop Zone", None, None),
            "target_zone_bounds": _build_zone("Target Zone", None, None),
        }

    band = max(50.0, abs(resistance - support))
    edge_width = max(20.0, min(120.0, band * 0.18))
    breakout_pad = max(15.0, min(150.0, band * 0.12))
    stop_pad = max(20.0, min(180.0, band * 0.15))
    midpoint = (support + resistance) / 2.0

    state = str(spc_state or "").upper()
    direction_bias = str(bias or "").strip().title()
    active_decision = str(spc_decision or "").upper() == "ACT" and str(trade_action or "").upper() != "WAIT"

    entry = _build_zone("Entry Zone", midpoint - edge_width * 0.5, midpoint + edge_width * 0.5)
    stop_zone = _build_zone("Stop Zone", support - stop_pad, support - 5.0)
    target_zone = _build_zone(
        "Target Zone",
        target1 if target1 is not None else resistance - edge_width * 0.5,
        target2 if target2 is not None else resistance,
    )
    execution_mode = "Range / no-edge execution"
    delta_band = "N/A"
    delta_note = "Avoid buying premium; wait for directional confirmation."
    avoid_buying = True

    if state == "SUPPORT_DEFENSE":
        entry = _build_zone("Entry Zone", support, support + edge_width)
        stop_zone = _build_zone("Stop Zone", support - stop_pad, support - 5.0)
        target_zone = _build_zone(
            "Target Zone",
            target1 if target1 is not None else support + edge_width * 1.6,
            target2 if target2 is not None else resistance - edge_width * 0.4,
        )
        execution_mode = "Support defense bounce"
        delta_band = "0.35 - 0.55"
        delta_note = "Use moderate-delta entries on support hold confirmation."
        avoid_buying = not active_decision
    elif state == "RESISTANCE_PRESSURE":
        entry = _build_zone("Entry Zone", resistance - edge_width, resistance)
        stop_zone = _build_zone("Stop Zone", resistance + 5.0, resistance + stop_pad)
        target_zone = _build_zone(
            "Target Zone",
            target1 if target1 is not None else support + edge_width * 0.4,
            target2 if target2 is not None else resistance - edge_width * 1.6,
        )
        execution_mode = "Resistance rejection setup"
        delta_band = "0.35 - 0.55"
        delta_note = "Use moderate-delta entries only after rejection confirmation."
        avoid_buying = not active_decision
    elif state in {"BREAKOUT_ATTEMPT", "CONFIRMED_EXPANSION"} and (direction_bias == "Bullish" or (spot is not None and spot >= resistance)):
        anchor = max(resistance, spot if spot is not None else resistance)
        entry = _build_zone("Entry Zone", anchor + 2.0, anchor + breakout_pad)
        stop_zone = _build_zone("Stop Zone", resistance - edge_width * 0.6, resistance + 5.0)
        target_zone = _build_zone(
            "Target Zone",
            target1 if target1 is not None else resistance + breakout_pad * 1.3,
            target2 if target2 is not None else resistance + band * 0.8,
        )
        execution_mode = "Breakout momentum execution"
        delta_band = "0.60 - 0.80"
        delta_note = "Use 0.60-0.80 delta calls after breakout acceptance."
        avoid_buying = False
    elif state in {"BREAKDOWN_ATTEMPT", "CONFIRMED_EXPANSION"} and (direction_bias == "Bearish" or (spot is not None and spot <= support)):
        anchor = min(support, spot if spot is not None else support)
        entry = _build_zone("Entry Zone", anchor - breakout_pad, anchor - 2.0)
        stop_zone = _build_zone("Stop Zone", support - 5.0, support + edge_width * 0.6)
        target_zone = _build_zone(
            "Target Zone",
            target1 if target1 is not None else support - breakout_pad * 1.3,
            target2 if target2 is not None else support - band * 0.8,
        )
        execution_mode = "Breakdown momentum execution"
        delta_band = "0.60 - 0.80"
        delta_note = "Use 0.60-0.80 delta puts after breakdown acceptance."
        avoid_buying = False

    if range_locked or no_edge or state == "WITHIN_STRUCTURE":
        execution_mode = "Range / no-edge execution"
        delta_band = "N/A"
        delta_note = "Range context detected: avoid buying premium and wait for expansion."
        avoid_buying = True
        entry = _build_zone("Entry Zone", midpoint - edge_width * 0.5, midpoint + edge_width * 0.5)
        stop_zone = _build_zone("Stop Zone", support - stop_pad, resistance + stop_pad)
        target_zone = _build_zone("Target Zone", support, resistance)

    if trap_risk >= 70.0 and state in {"BREAKOUT_ATTEMPT", "BREAKDOWN_ATTEMPT"}:
        delta_note = f"{delta_note} Trap risk elevated; wait for one extra confirmation."

    return {
        "entry_zone": entry["text"],
        "stop_zone": stop_zone["text"],
        "target_zone": target_zone["text"],
        "execution_mode": execution_mode,
        "delta_band": delta_band,
        "delta_strike_guidance": delta_note,
        "avoid_buying_premium": avoid_buying,
        "entry_zone_bounds": entry,
        "stop_zone_bounds": stop_zone,
        "target_zone_bounds": target_zone,
    }


def _position_size_fraction(
    confidence: float,
    trap_risk: float,
    volatility_state: str | None,
) -> tuple[float, str]:
    """
    Return a suggested position size fraction (0.0–1.0 of max allowed exposure).

    High confidence + low trap → larger size.
    High trap or low confidence → smaller size.
    Expanding volatility reduces size due to wider adverse excursions.
    """
    base = 0.5
    if confidence > 65:
        base += (confidence - 65) / 70.0 * 0.4    # max +0.4 at conf=95
    elif confidence < 40:
        base -= (40.0 - confidence) / 40.0 * 0.25  # max -0.25 at conf=0

    if trap_risk > 60:
        base -= (trap_risk - 60.0) / 40.0 * 0.3   # max -0.3 at trap=100
    elif trap_risk > 40:
        base -= 0.10

    if str(volatility_state or "") == "Expanding":
        base -= 0.10   # expanding vol → widen stops needed, reduce exposure

    fraction = max(0.1, min(1.0, base))

    if fraction >= 0.75:
        label = "Full size"
    elif fraction >= 0.5:
        label = "Standard size"
    elif fraction >= 0.3:
        label = "Half size"
    else:
        label = "Minimal size"

    return round(fraction, 2), label


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
    spot: float | int | None = None,
    spc_state: str | None = None,
    spc_decision: str | None = None,
    trade_action: str | None = None,
    range_locked: bool = False,
    no_edge: bool = False,
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
    spot_value = _to_float(spot)
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

    pos_fraction, pos_label = _position_size_fraction(conf, trap, volatility_state)

    execution = _build_execution_layer(
        support=sup,
        resistance=res,
        spot=spot_value,
        target1=t1,
        target2=t2,
        spc_state=str(spc_state or ""),
        spc_decision=str(spc_decision or ""),
        trade_action=str(trade_action or ""),
        bias=str(bias or ""),
        trap_risk=trap,
        range_locked=bool(range_locked),
        no_edge=bool(no_edge),
    )

    return {
        "trade_plan": {
            "strategy_type": strategy_type,
            "entry_zone": execution.get("entry_zone", entry_zone),
            "stop_hint": stop_hint,
            "stop_zone": execution.get("stop_zone"),
            "target_primary": target_primary,
            "target_extended": target_extended,
            "target_zone": execution.get("target_zone"),
            "execution_mode": execution.get("execution_mode"),
            "delta_band": execution.get("delta_band"),
            "delta_strike_guidance": execution.get("delta_strike_guidance"),
            "avoid_buying_premium": execution.get("avoid_buying_premium"),
            "entry_zone_bounds": execution.get("entry_zone_bounds"),
            "stop_zone_bounds": execution.get("stop_zone_bounds"),
            "target_zone_bounds": execution.get("target_zone_bounds"),
            "caution_note": caution_note,
            "position_size_fraction": pos_fraction,
            "position_size_label": pos_label,
        }
    }
