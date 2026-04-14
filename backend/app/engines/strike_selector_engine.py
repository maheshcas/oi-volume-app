from __future__ import annotations

from typing import Any


def _format_zone(low: float, high: float) -> str:
    lo = int(round(min(low, high)))
    hi = int(round(max(low, high)))
    return f"{lo:,} - {hi:,}"


def _find_strikes_by_delta(
    chain_greeks: list[dict[str, Any]],
    target_delta_min: float,
    target_delta_max: float,
    option_type: str,
) -> list[dict[str, Any]]:
    target_mid = (target_delta_min + target_delta_max) / 2.0
    candidates: list[dict[str, Any]] = []
    for row in chain_greeks:
        g = row.get("ce" if option_type == "CE" else "pe", {})
        delta = abs(float(g.get("delta", 0) or 0))
        if delta <= 0:
            continue
        candidate = {
            "strike": row["strike"],
            "delta": round(delta, 3),
            "gamma": g.get("gamma", 0),
            "theta": g.get("theta", 0),
            "iv": g.get("iv", 0),
            "ltp": row.get(f"ltp_{option_type.lower()}", 0),
            "moneyness": g.get("moneyness", ""),
            "distance_from_spot": row.get("distance_from_spot", 0),
            "_delta_gap": abs(delta - target_mid),
            "_in_range": target_delta_min <= delta <= target_delta_max,
        }
        if float(candidate.get("ltp") or 0) > 0:
            candidates.append(candidate)

    in_range = sorted(
        [candidate for candidate in candidates if candidate["_in_range"]],
        key=lambda item: item["_delta_gap"],
    )
    selected = in_range[:3]

    # Keep the table useful even on sparse/flat IV chains.
    if len(selected) < 2:
        seen = {float(item["strike"]) for item in selected}
        nearest = sorted(
            [candidate for candidate in candidates if float(candidate["strike"]) not in seen],
            key=lambda item: item["_delta_gap"],
        )
        for candidate in nearest:
            selected.append(candidate)
            if len(selected) >= 3:
                break

    return [
        {
            "strike": item["strike"],
            "delta": item["delta"],
            "gamma": item["gamma"],
            "theta": item["theta"],
            "iv": item["iv"],
            "ltp": item["ltp"],
            "moneyness": item["moneyness"],
            "distance_from_spot": item["distance_from_spot"],
        }
        for item in sorted(selected, key=lambda item: item["_delta_gap"])[:3]
    ]


def generate_strike_guidance(
    *,
    trade_action: str,
    readiness_active: bool,
    trap_probability: float,
    session_phase: str,
    days_to_expiry: int,
    iv_rank: float | None,
    chain_greeks: list[dict[str, Any]],
    bias: str,
    support: float | None,
    resistance: float | None,
    spc_state: str | None = None,
    execution_mode: str | None = None,
    delta_guidance: str | None = None,
    avoid_buying_premium: bool | None = None,
    entry_zone: str | None = None,
    stop_zone: str | None = None,
    target_zone: str | None = None,
    position_size_fraction: float | None = None,
    position_size_label: str | None = None,
) -> dict[str, Any]:

    warnings: list[str] = []
    theta_warning = False
    recommended_action = "Wait"
    delta_range = [0.0, 0.0]
    option_type = "CE"

    if days_to_expiry <= 1:
        warnings.append("Expiry today - theta decay severe for buyers")
        theta_warning = True
    elif days_to_expiry <= 3:
        warnings.append(f"Expiry in {days_to_expiry} days - theta working against buyers")
        theta_warning = True

    if iv_rank is not None:
        if iv_rank >= 70:
            warnings.append("IV elevated - consider selling OTM instead of buying")
        elif iv_rank <= 30:
            if trap_probability >= 60:
                warnings.append("IV low but trap risk overrides - selling still preferred")
            else:
                warnings.append("IV depressed - option buying relatively cheap")

    if trap_probability >= 60:
        warnings.append(f"Trap risk {int(trap_probability)}% - avoid chasing breakouts")

    if session_phase in ("Compression Phase", "Structure Formation Phase"):
        warnings.append(f"{session_phase} - range-bound, premium selling favoured")

    action_upper = str(trade_action or "").upper().strip()

    if action_upper == "LONG BIAS":
        if readiness_active:
            option_type = "CE"
            if trap_probability < 45 and not theta_warning:
                recommended_action = "Buy CE - confirmed setup"
                delta_range = [0.45, 0.65]
            else:
                recommended_action = "Buy CE - wait for cleaner entry"
                delta_range = [0.35, 0.50]
        else:
            recommended_action = "Wait - no clean setup"
            delta_range = [0.0, 0.0]

    elif action_upper == "SHORT BIAS":
        if readiness_active:
            option_type = "PE"
            if trap_probability < 45 and not theta_warning:
                recommended_action = "Buy PE - confirmed setup"
                delta_range = [0.45, 0.65]
            else:
                recommended_action = "Buy PE - wait for cleaner entry"
                delta_range = [0.35, 0.50]
        else:
            recommended_action = "Wait - no clean setup"
            delta_range = [0.0, 0.0]

    elif action_upper in {"WAIT", "CAUTION", ""}:
        # Decision layer is source-of-truth for trade eligibility.
        recommended_action = "Wait - no clean setup"
        delta_range = [0.0, 0.0]

    elif trap_probability >= 60 or (iv_rank is not None and iv_rank >= 70):
        if bias == "Bullish":
            option_type = "PE"
            recommended_action = "Sell OTM PE (support)"
            delta_range = [0.15, 0.35]
        else:
            option_type = "CE"
            recommended_action = "Sell OTM CE (resistance)"
            delta_range = [0.15, 0.35]

    else:
        recommended_action = "Wait - no clean setup"
        delta_range = [0.0, 0.0]

    # Safety: keep option side consistent with action text.
    action_text = str(recommended_action or "").upper()
    if " PE" in action_text:
        option_type = "PE"
    elif " CE" in action_text:
        option_type = "CE"

    suggested_strikes = []
    if delta_range[1] > 0 and chain_greeks:
        suggested_strikes = _find_strikes_by_delta(
            chain_greeks, delta_range[0], delta_range[1], option_type
        )

    rr_note = None
    if suggested_strikes and support and resistance:
        band_width = abs(resistance - support)
        mid_idx = len(suggested_strikes) // 2
        ref_strike = suggested_strikes[mid_idx]
        if band_width > 0 and ref_strike.get("ltp", 0) > 0:
            rr = band_width / ref_strike["ltp"]
            rr_note = (
                f"Band width {int(band_width)}pts vs "
                f"{int(ref_strike['strike'])} {option_type} \u20b9{ref_strike['ltp']:.1f} "
                f"= {rr:.1f}x RR"
            )

    execution_layer_map = {
        "CONFIRMED_EXPANSION": "Momentum execution",
        "BREAKOUT_ATTEMPT": "Breakout watch execution",
        "BREAKDOWN_ATTEMPT": "Breakout watch execution",
        "SUPPORT_DEFENSE": "Defense execution",
        "RESISTANCE_PRESSURE": "Defense execution",
        "WITHIN_STRUCTURE": "Range execution",
    }
    execution_layer = execution_layer_map.get(str(spc_state or "").strip().upper(), execution_mode or "Selective execution")

    # Keep displayed execution zones aligned with option-side recommendation.
    resolved_entry_zone = entry_zone
    resolved_stop_zone = stop_zone
    resolved_target_zone = target_zone
    support_value = float(support) if support is not None else None
    resistance_value = float(resistance) if resistance is not None else None
    side_pad = 45.0
    stop_pad = 65.0
    target_pad = 120.0

    if option_type == "PE" and recommended_action.upper().startswith("SELL OTM PE") and support_value is not None:
        resolved_entry_zone = _format_zone(support_value + 20.0, support_value + side_pad)
        resolved_stop_zone = _format_zone(support_value - stop_pad, support_value - 20.0)
        resolved_target_zone = (
            _format_zone(support_value + target_pad, support_value + target_pad + 80.0)
            if resistance_value is None
            else _format_zone(min(support_value + target_pad, resistance_value - 40.0), resistance_value)
        )
    elif option_type == "CE" and recommended_action.upper().startswith("SELL OTM CE") and resistance_value is not None:
        resolved_entry_zone = _format_zone(resistance_value - side_pad, resistance_value - 20.0)
        resolved_stop_zone = _format_zone(resistance_value + 20.0, resistance_value + stop_pad)
        resolved_target_zone = (
            _format_zone(resistance_value - target_pad - 80.0, resistance_value - target_pad)
            if support_value is None
            else _format_zone(support_value, max(resistance_value - target_pad, support_value + 40.0))
        )

    return {
        "recommended_action": recommended_action,
        "option_type": option_type,
        "delta_range": delta_range,
        "suggested_strikes": suggested_strikes,
        "warnings": warnings,
        "theta_warning": theta_warning,
        "days_to_expiry": days_to_expiry,
        "iv_rank": iv_rank,
        "risk_reward_note": rr_note,
        "position_size_fraction": position_size_fraction,
        "position_size_label": position_size_label,
        "execution_layer": execution_layer,
        "delta_guidance": delta_guidance,
        "avoid_buying_premium": bool(avoid_buying_premium),
        "entry_zone": resolved_entry_zone,
        "stop_zone": resolved_stop_zone,
        "target_zone": resolved_target_zone,
    }
