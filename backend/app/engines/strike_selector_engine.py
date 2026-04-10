from __future__ import annotations
from typing import Any


def _find_strikes_by_delta(
    chain_greeks: list[dict[str, Any]],
    target_delta_min: float,
    target_delta_max: float,
    option_type: str,
) -> list[dict[str, Any]]:
    matches = []
    for row in chain_greeks:
        g = row.get("ce" if option_type == "CE" else "pe", {})
        delta = abs(float(g.get("delta", 0) or 0))
        if target_delta_min <= delta <= target_delta_max:
            matches.append({
                "strike": row["strike"],
                "delta": round(delta, 3),
                "theta": g.get("theta", 0),
                "iv": g.get("iv", 0),
                "ltp": row.get(f"ltp_{option_type.lower()}", 0),
                "moneyness": g.get("moneyness", ""),
            })
    return sorted(matches, key=lambda x: abs(x["delta"] - 0.50))[:3]


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
) -> dict[str, Any]:

    warnings: list[str] = []
    theta_warning = False
    recommended_action = "Wait"
    delta_range = [0.0, 0.0]
    option_type = "CE"

    # Theta warning
    if days_to_expiry <= 1:
        warnings.append("Expiry today — theta decay severe for buyers")
        theta_warning = True
    elif days_to_expiry <= 3:
        warnings.append(f"Expiry in {days_to_expiry} days — theta working against buyers")
        theta_warning = True

    # IV context
    if iv_rank is not None:
        if iv_rank >= 70:
            warnings.append("IV elevated — consider selling OTM instead of buying")
        elif iv_rank <= 30:
            warnings.append("IV depressed — option buying relatively cheap")

    # Trap warning
    if trap_probability >= 60:
        warnings.append(f"Trap risk {int(trap_probability)}% — avoid chasing breakouts")

    # Phase warning
    if session_phase in ("Compression Phase", "Structure Formation Phase"):
        warnings.append(f"{session_phase} — range-bound, premium selling favoured")

    # Strike guidance logic
    action_upper = str(trade_action or "").upper().strip()

    if action_upper == "LONG BIAS" and readiness_active:
        option_type = "CE"
        if trap_probability < 45 and not theta_warning:
            recommended_action = "Buy CE — confirmed setup"
            delta_range = [0.45, 0.65]
        else:
            recommended_action = "Buy CE — wait for cleaner entry"
            delta_range = [0.35, 0.50]

    elif action_upper == "SHORT BIAS" and readiness_active:
        option_type = "PE"
        if trap_probability < 45 and not theta_warning:
            recommended_action = "Buy PE — confirmed setup"
            delta_range = [0.45, 0.65]
        else:
            recommended_action = "Buy PE — wait for cleaner entry"
            delta_range = [0.35, 0.50]

    elif trap_probability >= 60 or (iv_rank is not None and iv_rank >= 70):
        # Selling conditions
        if bias == "Bullish":
            option_type = "PE"
            recommended_action = "Sell OTM PE — sell support put"
            delta_range = [0.20, 0.30]
        else:
            option_type = "CE"
            recommended_action = "Sell OTM CE — sell resistance call"
            delta_range = [0.20, 0.30]

    else:
        recommended_action = "Wait — no clean setup"
        delta_range = [0.0, 0.0]

    # Find matching strikes
    suggested_strikes = []
    if delta_range[1] > 0 and chain_greeks:
        suggested_strikes = _find_strikes_by_delta(
            chain_greeks, delta_range[0], delta_range[1], option_type
        )

    # Risk/reward context
    rr_note = None
    if suggested_strikes and support and resistance:
        band_width = abs(resistance - support)
        if band_width > 0 and suggested_strikes[0].get("ltp", 0) > 0:
            rr = band_width / suggested_strikes[0]["ltp"]
            rr_note = f"Band width {int(band_width)}pts vs premium ₹{suggested_strikes[0]['ltp']:.1f} = {rr:.1f}x RR"

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
    }
