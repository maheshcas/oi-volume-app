from __future__ import annotations

import math
import statistics
from typing import Any


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(round(float(value)))
    except (TypeError, ValueError):
        return default


def _non_empty_text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text if text else default


def _closest_row_by_strike(rows: list[dict[str, Any]], target: float) -> dict[str, Any] | None:
    if not rows:
        return None
    return min(rows, key=lambda r: abs(_safe_float(r.get("strike")) - target))


def _closest_chain_row(chain_greeks: list[dict[str, Any]], spot: float) -> dict[str, Any] | None:
    if not chain_greeks:
        return None
    return min(chain_greeks, key=lambda r: abs(_safe_float(r.get("strike")) - spot))


def _get_option_leg(row: dict[str, Any] | None, option_type: str) -> dict[str, Any]:
    if not isinstance(row, dict):
        return {}
    key = "ce" if option_type.upper() == "CE" else "pe"
    leg = row.get(key)
    return leg if isinstance(leg, dict) else {}


def _get_leg_ltp(row: dict[str, Any] | None, option_type: str) -> float:
    leg = _get_option_leg(row, option_type)
    ltp = _safe_float(leg.get("ltp"), 0.0)
    if ltp > 0:
        return ltp
    alt_key = f"ltp_{option_type.lower()}"
    return _safe_float((row or {}).get(alt_key), 0.0)


def _compute_straddle_trend(current: float | None, previous: float | None) -> str:
    cur = _safe_float(current, 0.0)
    prev = _safe_float(previous, 0.0)
    if prev <= 0 or cur <= 0:
        return "unknown"
    if cur < prev * 0.97:
        return "compressing"
    if cur > prev * 1.03:
        return "expanding"
    return "stable"


def _compute_iv_skew(atm_pe_iv: float, atm_ce_iv: float) -> tuple[str, float]:
    diff = _safe_float(atm_pe_iv, 0.0) - _safe_float(atm_ce_iv, 0.0)
    if diff > 0.015:
        return "bearish", diff
    if diff < -0.015:
        return "bullish", diff
    return "neutral", diff


def _compute_max_pain_strike(liquidity_map: list[dict[str, Any]], spot: float) -> int | None:
    if not liquidity_map:
        return None
    strikes = sorted({_safe_int(row.get("strike"), 0) for row in liquidity_map if _safe_int(row.get("strike"), 0) > 0})
    if not strikes:
        return None

    best_strike: int | None = None
    best_pain: float | None = None
    for strike in strikes:
        total_loss = 0.0
        for row in liquidity_map:
            row_strike = _safe_int(row.get("strike"), 0)
            if row_strike <= 0:
                continue
            oi_ce = _safe_float(row.get("oi_ce"), 0.0)
            oi_pe = _safe_float(row.get("oi_pe"), 0.0)
            # CE writers lose when expiry settles above their strike.
            if row_strike < strike:
                total_loss += max(0.0, oi_ce) * (strike - row_strike)
            # PE writers lose when expiry settles below their strike.
            if row_strike > strike:
                total_loss += max(0.0, oi_pe) * (row_strike - strike)
        pain = total_loss
        if best_pain is None or pain < best_pain:
            best_pain = pain
            best_strike = strike
        elif best_pain is not None and math.isclose(pain, best_pain, rel_tol=1e-9):
            if best_strike is None or abs(strike - spot) < abs(best_strike - spot):
                best_strike = strike
    return best_strike


def _compute_max_pain_pull(spot: float, max_pain_strike: int | None, strike_gap: int) -> tuple[float | None, str]:
    if max_pain_strike is None:
        return None, "unknown"
    distance = abs(_safe_float(spot, 0.0) - float(max_pain_strike))
    if spot < max_pain_strike - strike_gap:
        return distance, "upward"
    if spot > max_pain_strike + strike_gap:
        return distance, "downward"
    return distance, "at"


def _compute_price_magnet(
    liquidity_map: list[dict[str, Any]],
    spot: float,
    strike_gap: int,
) -> dict[str, Any]:
    """
    Price Magnet Effect: the underlying price tends to move toward
    the strike with the highest COMBINED open interest (CE + PE).
    This is the intraday gravitational pull level — different from
    max pain which is the expiry settlement target.
    """
    if not liquidity_map:
        return {
            "price_magnet_strike": None,
            "price_magnet_combined": 0.0,
            "magnet_pull_direction": "unknown",
            "magnet_distance_pts": None,
            "secondary_magnet": None,
            "between_magnets": False,
            "magnet_ce_pct": 0.0,
            "magnet_pe_pct": 0.0,
            "magnet_character": "unknown",
            "compression_zone": False,
        }

    scored: list[dict[str, Any]] = []
    for row in liquidity_map:
        s = _safe_int(row.get("strike"), 0)
        if s <= 0:
            continue
        ce_oi = max(0.0, _safe_float(row.get("oi_ce"), 0.0))
        pe_oi = max(0.0, _safe_float(row.get("oi_pe"), 0.0))
        combined = ce_oi + pe_oi
        if combined > 0:
            scored.append(
                {
                    "strike": s,
                    "combined": combined,
                    "ce_oi": ce_oi,
                    "pe_oi": pe_oi,
                }
            )

    if not scored:
        return {
            "price_magnet_strike": None,
            "price_magnet_combined": 0.0,
            "magnet_pull_direction": "unknown",
            "magnet_distance_pts": None,
            "secondary_magnet": None,
            "between_magnets": False,
            "magnet_ce_pct": 0.0,
            "magnet_pe_pct": 0.0,
            "magnet_character": "unknown",
            "compression_zone": False,
        }

    scored.sort(key=lambda x: x["combined"], reverse=True)
    primary = scored[0]
    secondary = scored[1] if len(scored) > 1 else None

    magnet_strike = int(primary["strike"])
    magnet_combined = float(primary["combined"])
    ce_oi = float(primary["ce_oi"])
    pe_oi = float(primary["pe_oi"])

    if spot < magnet_strike - strike_gap:
        pull = "up"
    elif spot > magnet_strike + strike_gap:
        pull = "down"
    else:
        pull = "at"

    distance = abs(float(spot) - float(magnet_strike)) if magnet_strike else None
    ce_pct = (ce_oi / magnet_combined * 100.0) if magnet_combined > 0 else 0.0
    pe_pct = (pe_oi / magnet_combined * 100.0) if magnet_combined > 0 else 0.0

    if ce_pct >= 60:
        character = "resistance"
    elif pe_pct >= 60:
        character = "support"
    else:
        character = "balanced"

    between = False
    compression = False
    sec_strike: int | None = None
    if secondary:
        sec_strike = int(secondary["strike"])
        lo = min(magnet_strike, sec_strike)
        hi = max(magnet_strike, sec_strike)
        between = lo <= spot <= hi
        dist_primary = abs(spot - magnet_strike)
        dist_secondary = abs(spot - sec_strike)
        compression = dist_primary <= 3 * strike_gap and dist_secondary <= 3 * strike_gap

    return {
        "price_magnet_strike": magnet_strike,
        "price_magnet_combined": round(magnet_combined, 0),
        "magnet_pull_direction": pull,
        "magnet_distance_pts": round(distance, 1) if distance is not None else None,
        "secondary_magnet": sec_strike,
        "between_magnets": between,
        "magnet_ce_pct": round(ce_pct, 1),
        "magnet_pe_pct": round(pe_pct, 1),
        "magnet_character": character,
        "compression_zone": compression,
    }


def _compute_level_pcr(level_row: dict[str, Any] | None) -> float | None:
    if not level_row:
        return None
    oi_ce = _safe_float(level_row.get("oi_ce"), 0.0)
    oi_pe = _safe_float(level_row.get("oi_pe"), 0.0)
    if oi_ce <= 0:
        return 0.0
    return oi_pe / oi_ce


def _compute_wall_holding(level_row: dict[str, Any] | None, side: str) -> bool:
    if not level_row:
        return False
    if side == "resistance":
        chg = _safe_float(level_row.get("oi_ce_change"), 1e9)
        return -0.03 <= chg < 0.05
    chg = _safe_float(level_row.get("oi_pe_change"), 1e9)
    return -0.03 <= chg < 0.05


def _compute_volume_spike_strikes(liquidity_map: list[dict[str, Any]]) -> list[int]:
    if not liquidity_map:
        return []
    avg_vols: list[float] = []
    for row in liquidity_map:
        vol_ce = _safe_float(row.get("vol_ce"), 0.0)
        vol_pe = _safe_float(row.get("vol_pe"), 0.0)
        avg_vols.append((vol_ce + vol_pe) / 2.0)
    if not avg_vols:
        return []
    median_vol = statistics.median(avg_vols)
    if median_vol <= 0:
        return []
    spikes: list[int] = []
    for row, avg in zip(liquidity_map, avg_vols):
        if avg > 2.0 * median_vol:
            strike = _safe_int(row.get("strike"), 0)
            if strike > 0:
                spikes.append(strike)
    return sorted(set(spikes))


def _compute_trade_side_routing(
    iv_rank: float,
    straddle_trend: str,
    trap_probability: float,
    bias: str,
) -> str:
    if iv_rank < 35:
        if straddle_trend == "compressing" and trap_probability < 45:
            return "SELLER_PREFERRED"
        return "BUYER_PREFERRED"
    if iv_rank > 65:
        if bias in {"Bullish", "Bearish"} and trap_probability < 35 and straddle_trend == "expanding":
            return "BUYER_ALLOWED"
        return "SELLER_PREFERRED"
    if bias in {"Bullish", "Bearish"} and trap_probability < 50:
        return "DIRECTION_TRADE"
    return "RANGE_TRADE"


def _routing_to_side(routing: str) -> tuple[str, str]:
    if routing in {"BUYER_PREFERRED", "BUYER_ALLOWED", "DIRECTION_TRADE"}:
        return "BUYER", "Directional context favours buying options"
    if routing in {"SELLER_PREFERRED", "RANGE_TRADE"}:
        return "SELLER", "IV/range context favours selling options"
    return "NEUTRAL", "No clear side routing"


def _is_near_level(spot: float, level: float, strike_gap: int, multiple: float) -> bool:
    if level <= 0 or strike_gap <= 0:
        return False
    return abs(spot - level) < multiple * strike_gap


def _mid_band(support: float, resistance: float) -> float | None:
    if support <= 0 or resistance <= 0:
        return None
    return (support + resistance) / 2.0


def _pick_recommended_strike(
    *,
    chain_greeks: list[dict[str, Any]],
    spot: float,
    option_type: str | None,
    action: str | None,
    delta_target_min: float | None,
    delta_target_max: float | None,
) -> int | None:
    if not chain_greeks:
        return None
    atm = _closest_chain_row(chain_greeks, spot)
    atm_strike = _safe_int((atm or {}).get("strike"), 0)
    if option_type in {None, "STRADDLE"} or action is None:
        return atm_strike if atm_strike > 0 else None
    if action == "BUY":
        return atm_strike if atm_strike > 0 else None

    d_min = _safe_float(delta_target_min, 0.0)
    d_max = _safe_float(delta_target_max, 1.0)
    candidates: list[tuple[float, int]] = []
    for row in chain_greeks:
        strike = _safe_int(row.get("strike"), 0)
        if strike <= 0:
            continue
        leg = _get_option_leg(row, option_type)
        delta = abs(_safe_float(leg.get("delta"), 0.0))
        if option_type == "CE" and strike < spot:
            continue
        if option_type == "PE" and strike > spot:
            continue
        if delta <= d_max:
            if d_min > 0 and delta < d_min:
                continue
            center = (d_min + d_max) / 2.0 if d_min > 0 else d_max
            candidates.append((abs(delta - center), strike))
    if candidates:
        candidates.sort(key=lambda x: (x[0], x[1]))
        return int(candidates[0][1])
    return atm_strike if atm_strike > 0 else None


def _count_true(values: list[bool]) -> int:
    return sum(1 for v in values if bool(v))


def _strength_from_borderlines(borderline_count: int) -> str:
    if borderline_count <= 0:
        return "Strong"
    if borderline_count == 1:
        return "Moderate"
    return "Weak"


def _is_borderline_upper(value: float, threshold: float) -> bool:
    if threshold <= 0:
        return False
    return value >= threshold * 0.9


def _is_borderline_lower(value: float, threshold: float) -> bool:
    if threshold <= 0:
        return False
    return value <= threshold * 1.1


def _is_borderline_abs(dist: float, limit: float) -> bool:
    if limit <= 0:
        return False
    return dist >= limit * 0.9


def _build_signal_output(
    *,
    signal: str,
    reason: str,
    strength: str,
    option: str | None,
    action: str | None,
    delta_min: float | None,
    delta_max: float | None,
    size: float,
    stop: str,
    target: str,
    recommended_strike: int | None,
) -> dict[str, Any]:
    return {
        "entry_signal": signal,
        "entry_signal_reason": reason,
        "entry_signal_strength": strength,
        "recommended_strike": recommended_strike,
        "recommended_option": option,
        "recommended_action": action,
        "delta_target_min": delta_min,
        "delta_target_max": delta_max,
        "position_size_fraction": float(max(0.0, min(1.0, size))),
        "stop_description": stop,
        "target_description": target,
    }


def compute_strike_intelligence(context: dict) -> dict:
    """
    Compute intraday strike intelligence from cycle context.

    Input keys:
      spot, support, resistance, strike_gap, chain_greeks, liquidity_map, iv_rank,
      iv_percentile, atm_ce_iv, atm_pe_iv, prev_straddle_premium, trap_probability,
      trap_direction, bias, session_phase, days_to_expiry, oi_scenario, defense_ratio_ce,
      defense_ratio_pe.

    Output keys:
      trade_side, trade_side_reason, entry_signal, entry_signal_reason,
      entry_signal_strength, recommended_strike, recommended_option,
      recommended_action, delta_target_min, delta_target_max,
      position_size_fraction, stop_description, target_description,
      max_pain_strike, max_pain_distance, max_pain_pull, iv_skew,
      iv_skew_magnitude, atm_straddle_premium, straddle_trend,
      ce_wall_holding, pe_wall_holding, resistance_pcr, support_pcr,
      volume_spike_strikes, trade_side_routing.

    Example scenarios:
      A) Expiry-day compression with max-pain pin -> SELL_STRADDLE_EXPIRY / SELL_CE_RESISTANCE
      B) Upside trap near resistance -> BUY_PE_TRAP_FADE
      C) Genuine breakdown below support with low trap -> BUY_PE_BREAKDOWN
      D) Rich IV + compression + strong walls -> SELL_CE_RESISTANCE / SELL_PE_SUPPORT
      E) High trap and no clean wall/break -> WAIT_NO_SETUP
    """
    try:
        spot = _safe_float(context.get("spot"), 0.0)
        support = _safe_float(context.get("support"), 0.0)
        resistance = _safe_float(context.get("resistance"), 0.0)
        strike_gap = max(1, _safe_int(context.get("strike_gap"), 50))

        chain_greeks = context.get("chain_greeks")
        chain_greeks = chain_greeks if isinstance(chain_greeks, list) else []
        liquidity_map = context.get("liquidity_map")
        liquidity_map = liquidity_map if isinstance(liquidity_map, list) else []

        iv_rank = _safe_float(context.get("iv_rank"), 50.0)
        iv_percentile = _safe_float(context.get("iv_percentile"), 50.0)
        atm_ce_iv = _safe_float(context.get("atm_ce_iv"), 0.0)
        atm_pe_iv = _safe_float(context.get("atm_pe_iv"), 0.0)
        prev_straddle_premium = context.get("prev_straddle_premium")
        trap_probability = _safe_float(context.get("trap_probability"), 0.0)
        trap_direction = _non_empty_text(context.get("trap_direction"), "unknown")
        bias = _non_empty_text(context.get("bias"), "Neutral")
        session_phase = _non_empty_text(context.get("session_phase"), "Transition")
        days_to_expiry = max(0, _safe_int(context.get("days_to_expiry"), 0))
        oi_scenario = _non_empty_text(context.get("oi_scenario"), "NEUTRAL")
        session_range_pct = _safe_float(context.get("session_range_pct"), 0.0)
        defense_ratio_ce = _safe_float(context.get("defense_ratio_ce"), 0.0)
        defense_ratio_pe = _safe_float(context.get("defense_ratio_pe"), 0.0)

        # Intermediates
        atm_row = _closest_chain_row(chain_greeks, spot)
        atm_strike = _safe_int((atm_row or {}).get("strike"), 0)
        atm_ce_ltp = _get_leg_ltp(atm_row, "CE")
        atm_pe_ltp = _get_leg_ltp(atm_row, "PE")
        atm_straddle_premium = (atm_ce_ltp + atm_pe_ltp) if (atm_ce_ltp > 0 and atm_pe_ltp > 0) else None
        straddle_trend = _compute_straddle_trend(atm_straddle_premium, _safe_float(prev_straddle_premium, 0.0))
        iv_skew, iv_skew_magnitude = _compute_iv_skew(atm_pe_iv, atm_ce_iv)

        max_pain_strike = _compute_max_pain_strike(liquidity_map, spot)
        max_pain_distance, max_pain_pull = _compute_max_pain_pull(spot, max_pain_strike, strike_gap)
        magnet_result = _compute_price_magnet(
            liquidity_map=liquidity_map,
            spot=spot,
            strike_gap=strike_gap,
        )

        resistance_row = _closest_row_by_strike(liquidity_map, resistance)
        support_row = _closest_row_by_strike(liquidity_map, support)
        resistance_row_strike = _safe_int((resistance_row or {}).get("strike"), 0)
        support_row_strike = _safe_int((support_row or {}).get("strike"), 0)

        resistance_pcr = _compute_level_pcr(resistance_row)
        support_pcr = _compute_level_pcr(support_row)
        ce_wall_holding = _compute_wall_holding(resistance_row, "resistance")
        pe_wall_holding = _compute_wall_holding(support_row, "support")
        volume_spike_strikes = _compute_volume_spike_strikes(liquidity_map)

        trade_side_routing = _compute_trade_side_routing(
            iv_rank=iv_rank,
            straddle_trend=straddle_trend,
            trap_probability=trap_probability,
            bias=bias,
        )
        route_side, route_reason = _routing_to_side(trade_side_routing)
        mid = _mid_band(support, resistance)
        mid_text = f"{mid:.0f}" if mid is not None else "mid-band"

        # Signals
        b1 = (
            trap_probability > 65
            and trap_direction == "upside"
            and spot > resistance - 2 * strike_gap
            and ce_wall_holding
            and iv_rank < 55
        )
        b2 = (
            trap_probability < 50
            and spot < support + 2 * strike_gap
            and pe_wall_holding
            and iv_rank < 45
            and bias in {"Bullish", "Neutral"}
            and oi_scenario in {"LONG_BUILDUP", "NEUTRAL"}
        )
        b3 = (
            trap_probability < 35
            and bias == "Bearish"
            and spot < support - strike_gap
            and not pe_wall_holding
            and iv_rank < 50
            and straddle_trend in {"expanding", "stable"}
        )
        b4 = (
            (
                trap_probability < 35
                or (
                    trap_probability < 55
                    and oi_scenario == "PINNING"
                    and session_range_pct > 1.0
                )
            )
            and bias == "Bullish"
            and spot > resistance + strike_gap
            and not ce_wall_holding
            and iv_rank < 50
            and straddle_trend in {"expanding", "stable"}
        )
        b5 = (
            iv_rank < 30
            and straddle_trend == "expanding"
            and session_phase in {"Opening Drive", "Structure Formation"}
            and trap_probability < 50
        )

        s1 = (
            ce_wall_holding
            and _is_near_level(spot, resistance, strike_gap, 3.0)
            and trap_probability < 55
            and session_phase in {"Compression Phase", "Structure Formation", "Position Build Phase"}
            and straddle_trend in {"compressing", "stable"}
            and iv_rank > 40
        )
        s2 = (
            pe_wall_holding
            and _is_near_level(spot, support, strike_gap, 3.0)
            and trap_probability < 55
            and session_phase in {"Compression Phase", "Structure Formation", "Position Build Phase"}
            and iv_rank > 40
        )
        s3 = (
            days_to_expiry == 0
            and max_pain_distance is not None
            and max_pain_distance < 200
            and straddle_trend in {"compressing", "stable"}
            and (atm_straddle_premium is not None and atm_straddle_premium < 80)
            and session_phase in {"Compression Phase", "Position Build Phase"}
        )
        s4 = (
            defense_ratio_ce > 10.0
            and ce_wall_holding
            and resistance_row_strike in volume_spike_strikes
            and trap_probability < 50
        )
        s5 = (
            defense_ratio_pe > 10.0
            and pe_wall_holding
            and support_row_strike in volume_spike_strikes
            and trap_probability < 50
        )

        buyer_outputs: list[tuple[bool, dict[str, Any], int]] = []
        seller_outputs: list[tuple[bool, dict[str, Any], int]] = []

        if b1:
            b_count = _count_true(
                [
                    _is_borderline_lower(trap_probability, 65),
                    _is_borderline_lower(iv_rank, 55),
                    _is_borderline_lower(spot - resistance, 2 * strike_gap),
                ]
            )
            buyer_outputs.append(
                (
                    True,
                    _build_signal_output(
                        signal="BUY_PE_TRAP_FADE",
                        reason="Upside trap near resistance with CE wall intact; fade move via PE buy.",
                        strength=_strength_from_borderlines(b_count),
                        option="PE",
                        action="BUY",
                        delta_min=0.45,
                        delta_max=0.55,
                        size=0.25,
                        stop="40% of premium paid",
                        target=f"Spot returns to mid-band ({mid_text})",
                        recommended_strike=None,
                    ),
                    1,
                )
            )
        if b2:
            b_count = _count_true(
                [
                    _is_borderline_upper(trap_probability, 50),
                    _is_borderline_lower(iv_rank, 45),
                    _is_borderline_lower(support + 2 * strike_gap - spot, 2 * strike_gap),
                ]
            )
            buyer_outputs.append(
                (
                    True,
                    _build_signal_output(
                        signal="BUY_CE_REVERSAL",
                        reason="Support defended with low trap and acceptable IV; bounce setup via CE buy.",
                        strength=_strength_from_borderlines(b_count),
                        option="CE",
                        action="BUY",
                        delta_min=0.40,
                        delta_max=0.50,
                        size=0.30,
                        stop=f"Spot closes below {support:.0f}",
                        target=f"Mid-band {mid_text}",
                        recommended_strike=None,
                    ),
                    2,
                )
            )
        if b3:
            b_count = _count_true(
                [
                    _is_borderline_lower(trap_probability, 35),
                    _is_borderline_lower(iv_rank, 50),
                    _is_borderline_lower(support - spot, strike_gap),
                ]
            )
            buyer_outputs.append(
                (
                    True,
                    _build_signal_output(
                        signal="BUY_PE_BREAKDOWN",
                        reason="Support break with low trap and floor unwinding; continuation PE buy setup.",
                        strength=_strength_from_borderlines(b_count),
                        option="PE",
                        action="BUY",
                        delta_min=0.45,
                        delta_max=0.55,
                        size=0.35,
                        stop=f"Spot reclaims {support:.0f}",
                        target=f"{support - 150:.0f}pts",
                        recommended_strike=None,
                    ),
                    3,
                )
            )
        if b4:
            b_count = _count_true(
                [
                    _is_borderline_lower(trap_probability, 35),
                    _is_borderline_lower(iv_rank, 50),
                    _is_borderline_lower(spot - resistance, strike_gap),
                ]
            )
            buyer_outputs.append(
                (
                    True,
                    _build_signal_output(
                        signal="BUY_CE_BREAKOUT",
                        reason="Resistance break with low trap and ceiling unwind; continuation CE buy setup.",
                        strength=_strength_from_borderlines(b_count),
                        option="CE",
                        action="BUY",
                        delta_min=0.45,
                        delta_max=0.55,
                        size=0.35,
                        stop=f"Spot falls back below {resistance:.0f}",
                        target=f"{resistance + 150:.0f}pts",
                        recommended_strike=None,
                    ),
                    4,
                )
            )
        if b5:
            b_count = _count_true(
                [
                    _is_borderline_lower(iv_rank, 30),
                    _is_borderline_upper(trap_probability, 50),
                ]
            )
            buyer_outputs.append(
                (
                    True,
                    _build_signal_output(
                        signal="BUY_STRADDLE_EXPANSION",
                        reason="Cheap IV with early-session expansion; long straddle volatility play.",
                        strength=_strength_from_borderlines(b_count),
                        option="STRADDLE",
                        action="BUY",
                        delta_min=None,
                        delta_max=None,
                        size=0.20,
                        stop="Time-based: exit by 14:00 IST if no 80pt move",
                        target="1.5x combined premium",
                        recommended_strike=None,
                    ),
                    5,
                )
            )

        if s1:
            b_count = _count_true(
                [
                    _is_borderline_lower(trap_probability, 55),
                    _is_borderline_upper(iv_rank, 40),
                    _is_borderline_abs(abs(spot - resistance), 3 * strike_gap),
                ]
            )
            s1_reason = "Resistance wall holding in range/structure phase; OTM CE decay sell setup."
            if magnet_result.get("magnet_pull_direction") == "down" and magnet_result.get("price_magnet_strike"):
                s1_reason = (
                    f"CE wall holding at resistance; magnet {int(magnet_result['price_magnet_strike'])} "
                    f"pulling price down {float(magnet_result.get('magnet_distance_pts') or 0):.0f}pts — sell CE."
                )
            seller_outputs.append(
                (
                    True,
                    _build_signal_output(
                        signal="SELL_CE_RESISTANCE",
                        reason=s1_reason,
                        strength=_strength_from_borderlines(b_count),
                        option="CE",
                        action="SELL",
                        delta_min=0.15,
                        delta_max=0.25,
                        size=0.55,
                        stop="CE OI drops >10% + spot holds above resistance for 3 candles",
                        target="80% premium decay",
                        recommended_strike=None,
                    ),
                    1,
                )
            )
        if s2:
            b_count = _count_true(
                [
                    _is_borderline_lower(trap_probability, 55),
                    _is_borderline_upper(iv_rank, 40),
                    _is_borderline_abs(abs(spot - support), 3 * strike_gap),
                ]
            )
            s2_reason = "Support wall holding in range/structure phase; OTM PE decay sell setup."
            if magnet_result.get("magnet_pull_direction") == "up" and magnet_result.get("price_magnet_strike"):
                s2_reason = (
                    f"PE wall holding at support; magnet {int(magnet_result['price_magnet_strike'])} "
                    f"pulling price up {float(magnet_result.get('magnet_distance_pts') or 0):.0f}pts — sell PE."
                )
            seller_outputs.append(
                (
                    True,
                    _build_signal_output(
                        signal="SELL_PE_SUPPORT",
                        reason=s2_reason,
                        strength=_strength_from_borderlines(b_count),
                        option="PE",
                        action="SELL",
                        delta_min=0.15,
                        delta_max=0.25,
                        size=0.55,
                        stop="PE OI drops >10% + spot closes below support",
                        target="80% premium decay",
                        recommended_strike=None,
                    ),
                    2,
                )
            )
        if s3:
            b_count = _count_true(
                [
                    _is_borderline_upper(max_pain_distance or 0.0, 100),
                    _is_borderline_upper(atm_straddle_premium or 0.0, 80),
                ]
            )
            s3_anchor = (
                magnet_result.get("price_magnet_strike")
                if magnet_result.get("between_magnets")
                else (max_pain_strike or magnet_result.get("price_magnet_strike"))
            )
            s3_reason = (
                f"Expiry-day pin near {int(s3_anchor)} with compression; theta-focused short straddle setup."
                if s3_anchor
                else "Expiry-day pin near max pain with compression; theta-focused short straddle setup."
            )
            seller_outputs.append(
                (
                    True,
                    _build_signal_output(
                        signal="SELL_STRADDLE_EXPIRY",
                        reason=s3_reason,
                        strength=_strength_from_borderlines(b_count),
                        option="STRADDLE",
                        action="SELL",
                        delta_min=None,
                        delta_max=None,
                        size=0.30,
                        stop="Spot moves >80pts from entry strike",
                        target="80% straddle premium decay",
                        recommended_strike=None,
                    ),
                    0,
                )
            )
        if s4:
            b_count = _count_true(
                [
                    _is_borderline_lower(defense_ratio_ce, 10.0),
                    _is_borderline_lower(trap_probability, 50),
                ]
            )
            seller_outputs.append(
                (
                    True,
                    _build_signal_output(
                        signal="SELL_CE_WALL_CONFIRMED",
                        reason="Strong CE defense wall with fresh volume confirmation; high-conviction CE sell.",
                        strength=_strength_from_borderlines(b_count),
                        option="CE",
                        action="SELL",
                        delta_min=0.15,
                        delta_max=0.20,
                        size=0.65,
                        stop="CE OI drops >15%",
                        target="80% premium decay",
                        recommended_strike=None,
                    ),
                    4,
                )
            )
        if s5:
            b_count = _count_true(
                [
                    _is_borderline_lower(defense_ratio_pe, 10.0),
                    _is_borderline_lower(trap_probability, 50),
                ]
            )
            seller_outputs.append(
                (
                    True,
                    _build_signal_output(
                        signal="SELL_PE_WALL_CONFIRMED",
                        reason="Strong PE defense wall with fresh volume confirmation; high-conviction PE sell.",
                        strength=_strength_from_borderlines(b_count),
                        option="PE",
                        action="SELL",
                        delta_min=0.15,
                        delta_max=0.20,
                        size=0.65,
                        stop="PE OI drops >15%",
                        target="80% premium decay",
                        recommended_strike=None,
                    ),
                    5,
                )
            )

        buyer_outputs.sort(key=lambda x: x[2])
        seller_outputs.sort(key=lambda x: x[2])

        if trade_side_routing in {"BUYER_PREFERRED", "BUYER_ALLOWED", "DIRECTION_TRADE"}:
            ordered_signals = [x[1] for x in buyer_outputs] + [x[1] for x in seller_outputs]
        elif trade_side_routing in {"SELLER_PREFERRED", "RANGE_TRADE"}:
            ordered_signals = [x[1] for x in seller_outputs] + [x[1] for x in buyer_outputs]
        else:
            ordered_signals = [x[1] for x in buyer_outputs] + [x[1] for x in seller_outputs]

        chosen = ordered_signals[0] if ordered_signals else _build_signal_output(
            signal="WAIT_NO_SETUP",
            reason="No clean setup: trap/IV/phase/wall conditions are not aligned.",
            strength="Weak",
            option=None,
            action=None,
            delta_min=None,
            delta_max=None,
            size=0.0,
            stop="Wait for cleaner setup",
            target="No target while waiting",
            recommended_strike=None,
        )

        recommended_strike = _pick_recommended_strike(
            chain_greeks=chain_greeks,
            spot=spot,
            option_type=chosen["recommended_option"],
            action=chosen["recommended_action"],
            delta_target_min=chosen["delta_target_min"],
            delta_target_max=chosen["delta_target_max"],
        )
        chosen["recommended_strike"] = recommended_strike

        if chosen["entry_signal"] == "WAIT_NO_SETUP":
            trade_side = "NEUTRAL"
            side_reason = "No actionable buyer/seller setup from current conditions"
            if trap_probability >= 65:
                chosen["entry_signal_reason"] = "Trap too high for clean entry; wait."
            elif iv_rank > 65 and straddle_trend != "expanding":
                chosen["entry_signal_reason"] = "IV rich without clean expansion; avoid fresh buys."
            elif iv_rank < 35 and straddle_trend != "compressing":
                chosen["entry_signal_reason"] = "IV low but no directional conviction yet."
            elif not ce_wall_holding and not pe_wall_holding:
                chosen["entry_signal_reason"] = "Neither support nor resistance wall is confirmed."
            elif session_phase == "Transition":
                chosen["entry_signal_reason"] = "Transition phase with mixed confirmation; wait."
        else:
            trade_side = "BUYER" if chosen["recommended_action"] == "BUY" else "SELLER"
            if trade_side == route_side:
                side_reason = route_reason
            else:
                side_reason = f"Signal override: {chosen['entry_signal']} has higher priority than routing"

        return {
            "trade_side": trade_side,
            "trade_side_reason": side_reason,
            "entry_signal": chosen["entry_signal"],
            "entry_signal_reason": chosen["entry_signal_reason"],
            "entry_signal_strength": chosen["entry_signal_strength"],
            "recommended_strike": chosen["recommended_strike"],
            "recommended_option": chosen["recommended_option"],
            "recommended_action": chosen["recommended_action"],
            "delta_target_min": chosen["delta_target_min"],
            "delta_target_max": chosen["delta_target_max"],
            "position_size_fraction": chosen["position_size_fraction"],
            "stop_description": chosen["stop_description"],
            "target_description": chosen["target_description"],
            "max_pain_strike": max_pain_strike,
            "max_pain_distance": max_pain_distance,
            "max_pain_pull": max_pain_pull,
            "price_magnet_strike": magnet_result.get("price_magnet_strike"),
            "price_magnet_combined": magnet_result.get("price_magnet_combined"),
            "magnet_pull_direction": magnet_result.get("magnet_pull_direction"),
            "magnet_distance_pts": magnet_result.get("magnet_distance_pts"),
            "secondary_magnet": magnet_result.get("secondary_magnet"),
            "between_magnets": bool(magnet_result.get("between_magnets", False)),
            "magnet_ce_pct": magnet_result.get("magnet_ce_pct"),
            "magnet_pe_pct": magnet_result.get("magnet_pe_pct"),
            "magnet_character": magnet_result.get("magnet_character"),
            "compression_zone": bool(magnet_result.get("compression_zone", False)),
            "iv_skew": iv_skew,
            "iv_skew_magnitude": iv_skew_magnitude,
            "atm_straddle_premium": atm_straddle_premium,
            "straddle_trend": straddle_trend,
            "ce_wall_holding": bool(ce_wall_holding),
            "pe_wall_holding": bool(pe_wall_holding),
            "resistance_pcr": resistance_pcr,
            "support_pcr": support_pcr,
            "volume_spike_strikes": volume_spike_strikes,
            "trade_side_routing": trade_side_routing,
            "iv_percentile": iv_percentile,
            "atm_strike": atm_strike if atm_strike > 0 else None,
        }
    except Exception:
        return {
            "trade_side": "NEUTRAL",
            "trade_side_reason": "Engine fallback: invalid or incomplete context",
            "entry_signal": "WAIT_NO_SETUP",
            "entry_signal_reason": "Fallback mode due to invalid inputs.",
            "entry_signal_strength": "Weak",
            "recommended_strike": None,
            "recommended_option": None,
            "recommended_action": None,
            "delta_target_min": None,
            "delta_target_max": None,
            "position_size_fraction": 0.0,
            "stop_description": "Wait for valid data",
            "target_description": "No target while waiting",
            "max_pain_strike": None,
            "max_pain_distance": None,
            "max_pain_pull": "unknown",
            "price_magnet_strike": None,
            "price_magnet_combined": 0.0,
            "magnet_pull_direction": "unknown",
            "magnet_distance_pts": None,
            "secondary_magnet": None,
            "between_magnets": False,
            "magnet_ce_pct": 0.0,
            "magnet_pe_pct": 0.0,
            "magnet_character": "unknown",
            "compression_zone": False,
            "iv_skew": "neutral",
            "iv_skew_magnitude": 0.0,
            "atm_straddle_premium": None,
            "straddle_trend": "unknown",
            "ce_wall_holding": False,
            "pe_wall_holding": False,
            "resistance_pcr": None,
            "support_pcr": None,
            "volume_spike_strikes": [],
            "trade_side_routing": "UNKNOWN",
        }
