from __future__ import annotations

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


def _round_to_gap(price: float | None, strike_gap: int) -> float | None:
    if price is None:
        return None
    gap = max(1, strike_gap)
    return float(int(round(float(price) / gap) * gap))


def _empty_result() -> dict[str, Any]:
    return {
        "trade_type": "NONE",
        "entry_underlying": None,
        "entry_option_strike": None,
        "entry_option_type": None,
        "entry_option_action": None,
        "entry_premium": None,
        "entry_brief": "No trade setup currently.",
        "stop_underlying": None,
        "stop_premium_value": None,
        "stop_brief": "Wait for a clean setup.",
        "target_1": None,
        "target_2": None,
        "target_brief": "No targets while waiting.",
        "rr_t1": None,
        "rr_t2": None,
        "rr_brief": "RR unavailable",
        "ce_clusters": [],
        "pe_clusters": [],
        "call_wall_used": None,
        "put_wall_used": None,
        "straddle_entry_premium": None,
        "straddle_target_premium": None,
        "price_magnet_strike": None,
        "magnet_pull_direction": "unknown",
        "magnet_distance_pts": None,
        "secondary_magnet": None,
        "magnet_character": "unknown",
        "compression_zone": False,
    }


def _to_liq_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "strike": _safe_int(row.get("strike"), 0),
        "oi_ce": _safe_float(row.get("oi_ce"), 0.0),
        "oi_pe": _safe_float(row.get("oi_pe"), 0.0),
        "vol_ce": _safe_float(row.get("vol_ce"), 0.0),
        "vol_pe": _safe_float(row.get("vol_pe"), 0.0),
        "oi_ce_change": _safe_float(row.get("oi_ce_change"), 0.0),
        "oi_pe_change": _safe_float(row.get("oi_pe_change"), 0.0),
        "liquidity_score": _safe_float(row.get("liquidity_score"), 0.0),
    }


def _find_oi_clusters(
    liquidity_map: list[dict[str, Any]], spot: float
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows = [_to_liq_row(r) for r in liquidity_map if isinstance(r, dict)]
    ce_candidates = [r for r in rows if r["strike"] > 0 and r["strike"] >= spot]
    pe_candidates = [r for r in rows if r["strike"] > 0 and r["strike"] <= spot]
    ce_sorted = sorted(ce_candidates, key=lambda r: (r["oi_ce"], r["strike"]), reverse=True)[:3]
    pe_sorted = sorted(pe_candidates, key=lambda r: (r["oi_pe"], r["strike"]), reverse=True)[:3]
    return ce_sorted, pe_sorted


def _trade_type_from_signal(entry_signal: str) -> str:
    signal = str(entry_signal or "").strip().upper()
    if signal == "REJECTION_AT_RESISTANCE":
        return "REJECTION_AT_RESISTANCE"
    if signal == "BREAKOUT_ABOVE_RESISTANCE":
        return "BREAKOUT_ABOVE_RESISTANCE"
    if signal == "BOUNCE_AT_SUPPORT":
        return "BOUNCE_AT_SUPPORT"
    if signal == "BREAKDOWN_BELOW_SUPPORT":
        return "BREAKDOWN_BELOW_SUPPORT"
    if signal in {"SELL_CE_RESISTANCE", "SELL_CE_WALL_CONFIRMED"}:
        return "RANGE_SELL_CE"
    if signal in {"SELL_PE_SUPPORT", "SELL_PE_WALL_CONFIRMED"}:
        return "RANGE_SELL_PE"
    if signal == "SELL_STRADDLE_EXPIRY":
        return "EXPIRY_PIN"
    if signal == "BUY_PE_TRAP_FADE":
        return "TRAP_FADE_PE"
    if signal == "BUY_CE_REVERSAL":
        return "BOUNCE_CE"
    if signal == "BUY_PE_BREAKDOWN":
        return "BREAKDOWN_PE"
    if signal == "BUY_CE_BREAKOUT":
        return "BREAKOUT_CE"
    return "NONE"


def _closest_chain_row(chain_greeks: list[dict[str, Any]], spot: float) -> dict[str, Any] | None:
    rows = [r for r in chain_greeks if isinstance(r, dict)]
    if not rows:
        return None
    return min(rows, key=lambda r: abs(_safe_float(r.get("strike"), 0.0) - spot))


def _find_chain_row(chain_greeks: list[dict[str, Any]], strike: float) -> dict[str, Any] | None:
    rows = [r for r in chain_greeks if isinstance(r, dict)]
    if not rows:
        return None
    return min(rows, key=lambda r: abs(_safe_float(r.get("strike"), 0.0) - strike))


def _find_sell_strike(
    chain_greeks: list[dict[str, Any]],
    *,
    option_type: str,
    anchor: float,
    spot: float,
    delta_min: float,
    delta_max: float,
    min_ltp: float = 0.0,
) -> int | None:
    best: tuple[float, int] | None = None
    for row in chain_greeks:
        if not isinstance(row, dict):
            continue
        strike = _safe_int(row.get("strike"), 0)
        if strike <= 0:
            continue
        if option_type == "CE" and strike < spot:
            continue
        if option_type == "PE" and strike > spot:
            continue
        leg = row.get("ce" if option_type == "CE" else "pe") or {}
        delta = abs(_safe_float((leg if isinstance(leg, dict) else {}).get("delta"), 0.0))
        if delta < delta_min or delta > delta_max:
            continue
        ltp = _safe_float((leg if isinstance(leg, dict) else {}).get("ltp"), 0.0)
        if ltp < min_ltp:
            continue
        dist = abs(strike - anchor)
        if best is None or dist < best[0]:
            best = (dist, strike)
    return best[1] if best else None


def _get_leg_ltp(chain_greeks: list[dict[str, Any]], strike: float | None, option_type: str) -> float | None:
    if strike is None:
        return None
    row = _find_chain_row(chain_greeks, strike)
    if not row:
        return None
    leg = row.get("ce" if option_type == "CE" else "pe")
    if not isinstance(leg, dict):
        return None
    ltp = _safe_float(leg.get("ltp"), 0.0)
    return ltp if ltp > 0 else None


def _compute_rr(entry: float | None, stop: float | None, target: float | None) -> float | None:
    if entry is None or stop is None or target is None:
        return None
    risk = abs(entry - stop)
    reward = abs(entry - target)
    if risk <= 0:
        return None
    rr = reward / risk
    return rr if rr > 0 else None


def compute_entry_target(context: dict) -> dict:
    """
    Compute OI-led entry/stop/target plan.

    Input keys:
      spot, support, resistance, strike_gap, put_wall, call_wall, max_pain_strike,
      defense_ratio_ce, defense_ratio_pe, liquidity_map, chain_greeks, trap_probability,
      bias, oi_scenario, session_phase, days_to_expiry, iv_rank, atm_straddle_premium,
      entry_signal, price_magnet_strike, magnet_pull_direction, magnet_distance_pts,
      secondary_magnet, magnet_character, compression_zone.

    Output keys:
      trade_type, entry_underlying, entry_option_strike, entry_option_type,
      entry_option_action, entry_premium, entry_brief, stop_underlying,
      stop_premium_value, stop_brief, target_1, target_2, target_brief, rr_t1,
      rr_t2, rr_brief, ce_clusters, pe_clusters, call_wall_used, put_wall_used,
      straddle_entry_premium, straddle_target_premium.
    """
    try:
        out = _empty_result()
        spot = _safe_float(context.get("spot"), 0.0)
        support = _safe_float(context.get("support"), 0.0)
        resistance = _safe_float(context.get("resistance"), 0.0)
        strike_gap = max(1, _safe_int(context.get("strike_gap"), 50))
        put_wall = _safe_float(context.get("put_wall"), 0.0) or support
        call_wall = _safe_float(context.get("call_wall"), 0.0) or resistance
        max_pain_strike = context.get("max_pain_strike")
        max_pain = _safe_float(max_pain_strike, 0.0) if max_pain_strike is not None else None
        price_magnet_strike_ctx = context.get("price_magnet_strike")
        price_magnet_strike = (
            _safe_float(price_magnet_strike_ctx, 0.0) if price_magnet_strike_ctx is not None else None
        )
        magnet_pull_direction = str(context.get("magnet_pull_direction") or "unknown")
        magnet_distance_pts = _safe_float(context.get("magnet_distance_pts"), 0.0)
        secondary_magnet_ctx = context.get("secondary_magnet")
        secondary_magnet = _safe_float(secondary_magnet_ctx, 0.0) if secondary_magnet_ctx is not None else None
        magnet_character = str(context.get("magnet_character") or "unknown")
        compression_zone = bool(context.get("compression_zone", False))
        entry_signal = str(context.get("entry_signal") or "")
        chain_greeks = context.get("chain_greeks")
        chain_greeks = chain_greeks if isinstance(chain_greeks, list) else []
        liquidity_map = context.get("liquidity_map")
        liquidity_map = liquidity_map if isinstance(liquidity_map, list) else []
        atm_straddle_premium = context.get("atm_straddle_premium")
        atm_straddle_premium_f = _safe_float(atm_straddle_premium, 0.0) if atm_straddle_premium is not None else None

        ce_clusters, pe_clusters = _find_oi_clusters(liquidity_map, spot)
        out["ce_clusters"] = ce_clusters
        out["pe_clusters"] = pe_clusters
        out["call_wall_used"] = _round_to_gap(call_wall, strike_gap)
        out["put_wall_used"] = _round_to_gap(put_wall, strike_gap)
        out["price_magnet_strike"] = _round_to_gap(price_magnet_strike, strike_gap)
        out["magnet_pull_direction"] = magnet_pull_direction
        out["magnet_distance_pts"] = round(float(magnet_distance_pts), 1) if magnet_distance_pts is not None else None
        out["secondary_magnet"] = _round_to_gap(secondary_magnet, strike_gap)
        out["magnet_character"] = magnet_character
        out["compression_zone"] = compression_zone

        trade_type = _trade_type_from_signal(entry_signal)
        out["trade_type"] = trade_type
        if trade_type == "NONE":
            return out

        atm_row = _closest_chain_row(chain_greeks, spot)
        atm_strike = _safe_int((atm_row or {}).get("strike"), 0) or None

        entry_underlying: float | None = None
        entry_option_strike: int | None = None
        entry_option_type: str | None = None
        entry_option_action: str | None = None
        stop_underlying: float | None = None
        stop_pct_premium: float | None = None
        target_1: float | None = None
        target_2: float | None = None
        rr_t1: float | None = None
        rr_t2: float | None = None

        if trade_type == "RANGE_SELL_CE":
            entry_underlying = call_wall - strike_gap
            entry_option_type, entry_option_action = "CE", "SELL"
            entry_option_strike = _find_sell_strike(
                chain_greeks,
                option_type="CE",
                anchor=entry_underlying + strike_gap,
                spot=spot,
                delta_min=0.15,
                delta_max=0.35,
                min_ltp=5.0,
            ) or atm_strike
            stop_underlying = entry_underlying + (2 * strike_gap)
            stop_pct_premium = 0.50

            magnet_target = price_magnet_strike if price_magnet_strike is not None and price_magnet_strike > 0 else None
            put_wall_target = put_wall if put_wall > 0 else None
            mid_band_target = (support + resistance) / 2.0 if support > 0 and resistance > 0 else None
            max_pain_target = max_pain if max_pain is not None and max_pain > 0 else None

            valid_t1_candidates = [
                value for value in (magnet_target, put_wall_target, mid_band_target)
                if value is not None and value < entry_underlying
            ]
            target_1 = max(valid_t1_candidates) if valid_t1_candidates else (
                put_wall_target if put_wall_target is not None and put_wall_target < entry_underlying else support
            )

            risk_pts = abs((entry_underlying or 0.0) - (stop_underlying or 0.0))
            if risk_pts > 0 and target_1 is not None:
                min_t1 = (entry_underlying or 0.0) - (1.5 * risk_pts)
                target_1 = min(target_1, min_t1)
                if support > 0:
                    target_1 = max(target_1, support)

            valid_t2_candidates = [
                value for value in (max_pain_target, put_wall_target, support)
                if value is not None and value < (target_1 if target_1 is not None else entry_underlying)
            ]
            target_2 = min(valid_t2_candidates) if valid_t2_candidates else (
                max_pain_target if max_pain_target is not None and max_pain_target < entry_underlying else support
            )
            if risk_pts > 0 and target_1 is not None and (target_2 is None or target_2 >= target_1):
                target_2 = max(support, target_1 - risk_pts) if support > 0 else (target_1 - risk_pts)

        elif trade_type == "RANGE_SELL_PE":
            entry_underlying = put_wall + strike_gap
            entry_option_type, entry_option_action = "PE", "SELL"
            entry_option_strike = _find_sell_strike(
                chain_greeks,
                option_type="PE",
                anchor=entry_underlying - strike_gap,
                spot=spot,
                delta_min=0.15,
                delta_max=0.35,
                min_ltp=5.0,
            ) or atm_strike
            stop_underlying = entry_underlying - (2 * strike_gap)
            stop_pct_premium = 0.50

            magnet_target = price_magnet_strike if price_magnet_strike is not None and price_magnet_strike > 0 else None
            call_wall_target = call_wall if call_wall > 0 else None
            max_pain_target = max_pain if max_pain is not None and max_pain > 0 else None
            mid_band_target = (support + resistance) / 2.0 if support > 0 and resistance > 0 else None

            valid_t1_candidates = [
                value for value in (magnet_target, call_wall_target, mid_band_target)
                if value is not None and value > entry_underlying
            ]
            target_1 = min(valid_t1_candidates) if valid_t1_candidates else (
                call_wall_target if call_wall_target is not None and call_wall_target > entry_underlying else resistance
            )

            risk_pts = abs((entry_underlying or 0.0) - (stop_underlying or 0.0))
            if risk_pts > 0 and target_1 is not None:
                min_t1 = (entry_underlying or 0.0) + (1.5 * risk_pts)
                target_1 = max(target_1, min_t1)
                if resistance > 0:
                    target_1 = min(target_1, resistance)

            valid_t2_candidates = [
                value for value in (max_pain_target, call_wall_target, resistance)
                if value is not None and value > (target_1 if target_1 is not None else entry_underlying)
            ]
            target_2 = max(valid_t2_candidates) if valid_t2_candidates else resistance

        elif trade_type == "EXPIRY_PIN":
            entry_underlying = max_pain if max_pain is not None and max_pain > 0 else ((put_wall + call_wall) / 2.0)
            entry_option_type, entry_option_action = "STRADDLE", "SELL"
            entry_option_strike = atm_strike
            stop_underlying = entry_underlying + 2 * strike_gap
            stop_pct_premium = None
            out["straddle_entry_premium"] = atm_straddle_premium_f
            out["straddle_target_premium"] = (
                round((atm_straddle_premium_f or 0.0) * 0.2, 1) if atm_straddle_premium_f is not None else None
            )

        elif trade_type == "TRAP_FADE_PE":
            entry_underlying = spot
            entry_option_type, entry_option_action = "PE", "BUY"
            entry_option_strike = atm_strike
            stop_underlying = spot + 2 * strike_gap
            stop_pct_premium = 0.40
            target_1 = resistance
            target_2 = (resistance + support) / 2.0 if support > 0 and resistance > 0 else None

        elif trade_type == "BOUNCE_CE":
            entry_underlying = spot
            entry_option_type, entry_option_action = "CE", "BUY"
            entry_option_strike = atm_strike
            stop_underlying = put_wall - strike_gap
            stop_pct_premium = 0.40
            target_1 = (support + resistance) / 2.0 if support > 0 and resistance > 0 else None
            target_2 = call_wall

        elif trade_type == "REJECTION_AT_RESISTANCE":
            entry_underlying = spot
            entry_option_type, entry_option_action = "PE", "BUY"
            entry_option_strike = _find_sell_strike(
                chain_greeks,
                option_type="PE",
                anchor=spot,
                spot=spot,
                delta_min=0.35,
                delta_max=0.55,
                min_ltp=5.0,
            ) or atm_strike
            stop_underlying = resistance + strike_gap
            stop_pct_premium = 0.40
            target_1 = price_magnet_strike if price_magnet_strike is not None and price_magnet_strike > 0 else None
            if target_1 is not None:
                target_2 = target_1 - (2 * strike_gap)
                if support > 0:
                    target_2 = max(target_2, support + strike_gap)

        elif trade_type == "BREAKOUT_ABOVE_RESISTANCE":
            entry_underlying = spot
            entry_option_type, entry_option_action = "CE", "BUY"
            entry_option_strike = _find_sell_strike(
                chain_greeks,
                option_type="CE",
                anchor=spot,
                spot=spot,
                delta_min=0.35,
                delta_max=0.55,
                min_ltp=5.0,
            ) or atm_strike
            stop_underlying = resistance - strike_gap
            stop_pct_premium = 0.40
            target_1 = _safe_float(ce_clusters[0]["strike"], 0.0) if ce_clusters else (
                price_magnet_strike if price_magnet_strike is not None and price_magnet_strike > 0 else None
            )
            target_2 = _safe_float(ce_clusters[1]["strike"], 0.0) if len(ce_clusters) > 1 else (
                (target_1 + (2 * strike_gap)) if target_1 is not None else resistance + (2 * strike_gap)
            )

        elif trade_type == "BOUNCE_AT_SUPPORT":
            entry_underlying = spot
            entry_option_type, entry_option_action = "CE", "BUY"
            entry_option_strike = _find_sell_strike(
                chain_greeks,
                option_type="CE",
                anchor=spot,
                spot=spot,
                delta_min=0.35,
                delta_max=0.55,
                min_ltp=5.0,
            ) or atm_strike
            stop_underlying = support - strike_gap
            stop_pct_premium = 0.40
            target_1 = price_magnet_strike if price_magnet_strike is not None and price_magnet_strike > 0 else None
            if max_pain is not None and target_1 is not None and max_pain > target_1:
                target_2 = max_pain
            elif target_1 is not None:
                target_2 = min(resistance - strike_gap, target_1 + (2 * strike_gap)) if resistance > 0 else target_1 + (2 * strike_gap)

        elif trade_type == "BREAKDOWN_PE":
            entry_underlying = spot
            entry_option_type, entry_option_action = "PE", "BUY"
            entry_option_strike = atm_strike
            stop_underlying = support
            stop_pct_premium = 0.40
            target_1 = _safe_float(pe_clusters[0]["strike"], 0.0) if pe_clusters else support - 2 * strike_gap
            target_2 = _safe_float(pe_clusters[1]["strike"], 0.0) if len(pe_clusters) > 1 else support - 4 * strike_gap

        elif trade_type == "BREAKOUT_CE":
            entry_underlying = spot
            entry_option_type, entry_option_action = "CE", "BUY"
            entry_option_strike = atm_strike
            stop_underlying = resistance
            stop_pct_premium = 0.40
            target_1 = _safe_float(ce_clusters[0]["strike"], 0.0) if ce_clusters else resistance + 2 * strike_gap
            target_2 = _safe_float(ce_clusters[1]["strike"], 0.0) if len(ce_clusters) > 1 else resistance + 4 * strike_gap

        elif trade_type == "BREAKDOWN_BELOW_SUPPORT":
            entry_underlying = spot
            entry_option_type, entry_option_action = "PE", "BUY"
            entry_option_strike = _find_sell_strike(
                chain_greeks,
                option_type="PE",
                anchor=spot,
                spot=spot,
                delta_min=0.35,
                delta_max=0.55,
                min_ltp=5.0,
            ) or atm_strike
            stop_underlying = support + strike_gap
            stop_pct_premium = 0.40
            target_1 = _safe_float(pe_clusters[0]["strike"], 0.0) if pe_clusters else (
                price_magnet_strike if price_magnet_strike is not None and price_magnet_strike > 0 else None
            )
            target_2 = _safe_float(pe_clusters[1]["strike"], 0.0) if len(pe_clusters) > 1 else (
                (target_1 - (2 * strike_gap)) if target_1 is not None else support - (2 * strike_gap)
            )

        entry_underlying = _round_to_gap(entry_underlying, strike_gap)
        stop_underlying = _round_to_gap(stop_underlying, strike_gap)
        target_1 = _round_to_gap(target_1, strike_gap)
        target_2 = _round_to_gap(target_2, strike_gap)

        entry_premium: float | None = None
        stop_premium_value: float | None = None
        if entry_option_type in {"CE", "PE"} and entry_option_strike is not None:
            entry_premium = _get_leg_ltp(chain_greeks, entry_option_strike, entry_option_type)
            if entry_premium is not None and stop_pct_premium is not None:
                if entry_option_action == "BUY":
                    stop_premium_value = round(entry_premium * stop_pct_premium, 1)
                elif entry_option_action == "SELL":
                    stop_premium_value = round(entry_premium * (1.0 + stop_pct_premium), 1)

        rr_t1 = _compute_rr(entry_underlying, stop_underlying, target_1)
        rr_t2 = _compute_rr(entry_underlying, stop_underlying, target_2)

        rupee = "\u20b9"
        if trade_type == "EXPIRY_PIN":
            entry_brief = (
                f"Sell ATM straddle near {format(_safe_float(entry_underlying), '.0f')}."
                f" Collect {rupee}{(atm_straddle_premium_f or 0.0):.1f} combined premium."
            )
            stop_brief = (
                f"Stop if spot crosses {format(_safe_float(entry_underlying + 2 * strike_gap), '.0f')}"
                f" or {format(_safe_float(entry_underlying - 2 * strike_gap), '.0f')}."
            )
            residual = out["straddle_target_premium"]
            target_brief = (
                f"Target 80% decay; hold residual near {rupee}{residual:.1f}."
                if isinstance(residual, float)
                else "Target 80% straddle premium decay."
            )
        else:
            action = entry_option_action or "TRADE"
            option = entry_option_type or "OPT"
            strike_txt = f"{entry_option_strike}" if entry_option_strike is not None else "ATM"
            premium_txt = f"{rupee}{entry_premium:.1f}" if entry_premium is not None else f"{rupee}-"
            if action == "SELL":
                entry_brief = (
                    f"Sell {strike_txt} {option} near {format(_safe_float(entry_underlying), '.0f')}. "
                    f"Collect {premium_txt} premium."
                )
            else:
                entry_brief = (
                    f"Buy {strike_txt} {option} near {format(_safe_float(entry_underlying), '.0f')}. "
                    f"Pay {premium_txt}."
                )

            stop_prem_txt = f"{rupee}{stop_premium_value:.1f}" if stop_premium_value is not None else f"{rupee}-"
            stop_brief = (
                f"Stop if spot crosses {format(_safe_float(stop_underlying), '.0f')}"
                f" or premium hits {stop_prem_txt}."
                if stop_underlying is not None
                else "Stop: premium or structure invalidation."
            )

            if trade_type == "RANGE_SELL_CE":
                t1_val = _safe_float(target_1) if target_1 is not None else None
                t2_val = _safe_float(target_2) if target_2 is not None else None
                e_val = _safe_float(entry_underlying) if entry_underlying is not None else None
                t1_pts = abs(e_val - t1_val) if e_val is not None and t1_val is not None else None
                t2_pts = abs(e_val - t2_val) if e_val is not None and t2_val is not None else None
                target_brief = (
                    f"T1: {format(t1_val, '.0f') if t1_val is not None else '-'} "
                    f"(price magnet - {t1_pts:.0f}pts) · "
                    f"T2: {format(t2_val, '.0f') if t2_val is not None else '-'} "
                    f"(max pain - {t2_pts:.0f}pts)"
                    if t1_pts is not None and t2_pts is not None
                    else "Targets mapped to magnet and max pain."
                )
            elif trade_type == "RANGE_SELL_PE":
                stop_brief = (
                    f"Stop if spot falls below {format(_safe_float(stop_underlying), '.0f')}"
                    f" or premium hits {stop_prem_txt}."
                    if stop_underlying is not None
                    else "Stop: premium or structure invalidation."
                )
                t1_txt = f"{format(_safe_float(target_1), '.0f')}" if target_1 is not None else "-"
                t2_txt = f"{format(_safe_float(target_2), '.0f')}" if target_2 is not None else "-"
                t1_pts = (
                    f"{abs(_safe_float(target_1) - _safe_float(entry_underlying)):.0f}pts above entry"
                    if target_1 is not None and entry_underlying is not None
                    else "-"
                )
                target_brief = f"T1: {t1_txt} ({t1_pts}) · T2: {t2_txt}"
            elif trade_type == "REJECTION_AT_RESISTANCE":
                entry_brief = (
                    f"Buy PE near {format(_safe_float(spot), '.0f')} as spot tests resistance "
                    f"{format(_safe_float(resistance), '.0f')}."
                )
                stop_brief = (
                    f"Stop if spot breaks above {format(_safe_float(stop_underlying), '.0f')}."
                    if stop_underlying is not None
                    else "Stop: premium or structure invalidation."
                )
                target_brief = (
                    f"T1: {format(_safe_float(target_1), '.0f')} "
                    f"({abs(_safe_float(target_1) - _safe_float(entry_underlying)):.0f}pts) · "
                    f"T2: {format(_safe_float(target_2), '.0f')}"
                    if target_1 is not None and entry_underlying is not None
                    else "Targets mapped to magnet fade."
                )
                if target_1 is not None and target_2 is not None:
                    target_brief = (
                        f"T1: {format(_safe_float(target_1), '.0f')} (magnet) · "
                        f"T2: {format(_safe_float(target_2), '.0f')}"
                    )
            elif trade_type == "BREAKOUT_ABOVE_RESISTANCE":
                stop_brief = (
                    f"Stop if spot slips back below {format(_safe_float(stop_underlying), '.0f')}"
                    f" or premium hits {stop_prem_txt}."
                    if stop_underlying is not None
                    else "Stop: premium or structure invalidation."
                )
                target_brief = (
                    f"T1: {format(_safe_float(target_1), '.0f')} "
                    f"({abs(_safe_float(target_1) - _safe_float(entry_underlying)):.0f}pts) · "
                    f"T2: {format(_safe_float(target_2), '.0f')}"
                    if target_1 is not None and entry_underlying is not None
                    else "Targets mapped to upside CE clusters."
                )
            elif trade_type == "BOUNCE_AT_SUPPORT":
                target_brief = (
                    f"T1: {format(_safe_float(target_1), '.0f')} "
                    f"({abs(_safe_float(target_1) - _safe_float(entry_underlying)):.0f}pts) · "
                    f"T2: {format(_safe_float(target_2), '.0f')}"
                    if target_1 is not None and entry_underlying is not None
                    else "Targets mapped to bounce recovery."
                )
            elif trade_type == "BREAKDOWN_BELOW_SUPPORT":
                stop_brief = (
                    f"Stop if spot reclaims {format(_safe_float(stop_underlying), '.0f')}"
                    f" or premium hits {stop_prem_txt}."
                    if stop_underlying is not None
                    else "Stop: premium or structure invalidation."
                )
                target_brief = (
                    f"T1: {format(_safe_float(target_1), '.0f')} "
                    f"({abs(_safe_float(target_1) - _safe_float(entry_underlying)):.0f}pts) · "
                    f"T2: {format(_safe_float(target_2), '.0f')}"
                    if target_1 is not None and entry_underlying is not None
                    else "Targets mapped to downside PE clusters."
                )
            else:
                t1_txt = f"{format(_safe_float(target_1), '.0f')}" if target_1 is not None else "-"
                t2_txt = f"{format(_safe_float(target_2), '.0f')}" if target_2 is not None else "-"
                t1_pts = (
                    f"{abs(_safe_float(target_1) - _safe_float(entry_underlying)):.0f}pts"
                    if target_1 is not None and entry_underlying is not None
                    else "-"
                )
                target_brief = f"T1: {t1_txt} ({t1_pts}) - T2: {t2_txt}"

        rr_brief = (
            f"RR T1: {rr_t1:.1f}x - T2: {rr_t2:.1f}x"
            if rr_t1 is not None or rr_t2 is not None
            else "RR unavailable"
        )

        out.update(
            {
                "entry_underlying": entry_underlying,
                "entry_option_strike": entry_option_strike,
                "entry_option_type": entry_option_type,
                "entry_option_action": entry_option_action,
                "entry_premium": entry_premium,
                "entry_brief": entry_brief,
                "stop_underlying": stop_underlying,
                "stop_premium_value": stop_premium_value,
                "stop_brief": stop_brief,
                "target_1": target_1,
                "target_2": target_2,
                "target_brief": target_brief,
                "rr_t1": rr_t1,
                "rr_t2": rr_t2,
                "rr_brief": rr_brief,
            }
        )
        return out
    except Exception:
        return _empty_result()
