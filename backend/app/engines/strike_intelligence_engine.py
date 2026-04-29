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


def _compute_max_pain_strike(
    liquidity_map: list[dict[str, Any]],
    spot: float,
    strike_gap: int,
) -> int | None:
    metrics = _compute_max_pain_metrics(
        liquidity_map=liquidity_map,
        spot=spot,
        strike_gap=strike_gap,
    )
    return _safe_int(metrics.get("max_pain_strike"), 0) or None


def _compute_max_pain_metrics(
    *,
    liquidity_map: list[dict[str, Any]],
    spot: float,
    strike_gap: int,
    symbol: str = "",
) -> dict[str, Any]:
    if not liquidity_map:
        return {
            "max_pain_strike": None,
            "max_pain_confidence": 0.0,
            "max_pain_strength": "Weak",
        }

    window = max(1, int(strike_gap)) * 8
    candidates: list[dict[str, Any]] = []
    for row in liquidity_map:
        strike = _safe_int(row.get("strike"), 0)
        if strike <= 0:
            continue
        if spot > 0 and abs(strike - spot) > window:
            continue
        ce_oi = max(0.0, _safe_float(row.get("oi_ce"), 0.0))
        pe_oi = max(0.0, _safe_float(row.get("oi_pe"), 0.0))
        candidates.append(
            {
                "strike": strike,
                "ce_oi": ce_oi,
                "pe_oi": pe_oi,
                "combined_oi": ce_oi + pe_oi,
            }
        )
    if not candidates:
        return {
            "max_pain_strike": None,
            "max_pain_confidence": 0.0,
            "max_pain_strength": "Weak",
        }

    max_oi = max(float(r["combined_oi"]) for r in candidates)
    noise_threshold = 0.15 if str(symbol).upper() == "SENSEX" else 0.10
    oi_cutoff = max_oi * noise_threshold
    filtered = [r for r in candidates if float(r["combined_oi"]) >= oi_cutoff]
    rows = filtered if filtered else candidates
    strikes = sorted({_safe_int(r.get("strike"), 0) for r in rows if _safe_int(r.get("strike"), 0) > 0})
    if not strikes:
        return {
            "max_pain_strike": None,
            "max_pain_confidence": 0.0,
            "max_pain_strength": "Weak",
        }

    best_strike: int | None = None
    best_loss: float | None = None
    loss_values: list[float] = []
    for k in strikes:
        total_loss = 0.0
        for row in rows:
            strike = _safe_int(row.get("strike"), 0)
            ce_oi = _safe_float(row.get("ce_oi"), 0.0)
            pe_oi = _safe_float(row.get("pe_oi"), 0.0)
            call_loss = max(0.0, float(k - strike)) * ce_oi
            put_loss = max(0.0, float(strike - k)) * pe_oi
            total_loss += call_loss + put_loss
        loss_values.append(total_loss)
        if best_loss is None or total_loss < best_loss:
            best_loss = total_loss
            best_strike = k
        elif best_loss is not None and math.isclose(total_loss, best_loss, rel_tol=1e-9):
            if best_strike is None or abs(k - spot) < abs(best_strike - spot):
                best_strike = k

    if not loss_values or len(loss_values) < 2:
        return {
            "max_pain_strike": None,
            "max_pain_confidence": 0.0,
            "max_pain_strength": "Weak",
        }

    avg_loss = statistics.mean(loss_values)
    min_loss = float(best_loss or 0.0)
    confidence = 0.0
    if avg_loss > 0:
        confidence = max(0.0, min(100.0, (1.0 - (min_loss / avg_loss)) * 100.0))
    # Cap confidence when very few strikes survived the noise filter.
    if len(loss_values) < 4:
        confidence = min(confidence, 40.0)
    if confidence >= 70:
        strength = "Strong"
    elif confidence >= 45:
        strength = "Moderate"
    else:
        strength = "Weak"
    return {
        "max_pain_strike": best_strike,
        "max_pain_confidence": round(confidence, 2),
        "max_pain_strength": strength,
    }


def _compute_max_pain_pull(spot: float, max_pain_strike: int | None, strike_gap: int) -> tuple[float | None, str]:
    if max_pain_strike is None:
        return None, "unknown"
    distance = abs(_safe_float(spot, 0.0) - float(max_pain_strike))
    if spot < max_pain_strike - strike_gap:
        return distance, "upward"
    if spot > max_pain_strike + strike_gap:
        return distance, "downward"
    return distance, "at"


def _resolve_magnet_interpretation(pull: str, character: str) -> str:
    if pull == "at":
        return "at_magnet"
    if pull == "up" and character in {"support", "strong_support"}:
        return "ascending_toward_floor"
    if pull == "up" and character in {"resistance", "strong_resistance"}:
        return "approaching_ceiling"
    if pull == "down" and character in {"resistance", "strong_resistance"}:
        return "descending_from_ceiling"
    if pull == "down" and character in {"support", "strong_support"}:
        return "approaching_floor"
    if pull == "up":
        return "drifting_up_to_neutral_magnet"
    if pull == "down":
        return "drifting_down_to_neutral_magnet"
    return "unknown"


def _compute_price_magnet(
    liquidity_map: list[dict[str, Any]],
    spot: float,
    strike_gap: int,
    previous_direction: str | None = None,
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
            "magnet_interpretation": "unknown",
            "magnet_distance_pts": None,
            "secondary_magnet": None,
            "secondary_magnet_distance_pts": None,
            "between_magnets": False,
            "magnet_ce_pct": 0.0,
            "magnet_pe_pct": 0.0,
            "magnet_character": "unknown",
            "magnet_strength": 0.0,
            "magnet_dominance_ratio": 0.0,
            "compression_zone": False,
        }

    scored: list[dict[str, Any]] = []
    for row in liquidity_map:
        s = _safe_int(row.get("strike"), 0)
        if s <= 0:
            continue
        # Exclude far-OTM strikes; they are usually expiry hedges rather than
        # meaningful intraday magnet levels.
        intraday_window = 10 * strike_gap
        if spot > 0 and abs(s - spot) > intraday_window:
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
            "magnet_interpretation": "unknown",
            "magnet_distance_pts": None,
            "secondary_magnet": None,
            "secondary_magnet_distance_pts": None,
            "between_magnets": False,
            "magnet_ce_pct": 0.0,
            "magnet_pe_pct": 0.0,
            "magnet_character": "unknown",
            "magnet_strength": 0.0,
            "magnet_dominance_ratio": 0.0,
            "compression_zone": False,
        }

    scored.sort(key=lambda x: x["combined"], reverse=True)
    primary = scored[0]
    secondary = scored[1] if len(scored) > 1 else None

    magnet_strike = int(primary["strike"])
    magnet_combined = float(primary["combined"])
    ce_oi = float(primary["ce_oi"])
    pe_oi = float(primary["pe_oi"])

    enter_threshold = float(strike_gap) * 1.5
    exit_threshold = float(strike_gap) * 0.8
    diff = float(magnet_strike) - float(spot)
    abs_diff = abs(diff)
    prev = str(previous_direction or "").strip().lower()
    if prev not in {"up", "down", "at"}:
        prev = "at"
    if prev == "up" and diff > exit_threshold:
        pull = "up"
    elif prev == "down" and (-diff) > exit_threshold:
        pull = "down"
    elif abs_diff <= exit_threshold:
        pull = "at"
    elif diff >= enter_threshold:
        pull = "up"
    elif (-diff) >= enter_threshold:
        pull = "down"
    else:
        pull = prev

    distance = abs(float(spot) - float(magnet_strike)) if magnet_strike else None
    ce_pct = (ce_oi / magnet_combined * 100.0) if magnet_combined > 0 else 0.0
    pe_pct = (pe_oi / magnet_combined * 100.0) if magnet_combined > 0 else 0.0

    ce_frac = (ce_oi / magnet_combined) if magnet_combined > 0 else 0.0
    pe_frac = (pe_oi / magnet_combined) if magnet_combined > 0 else 0.0
    if pe_frac >= 0.65:
        character = "strong_support"
    elif pe_frac >= 0.55:
        character = "support"
    elif ce_frac >= 0.65:
        character = "strong_resistance"
    elif ce_frac >= 0.55:
        character = "resistance"
    else:
        character = "balanced"
    magnet_strength = abs(ce_frac - pe_frac)
    magnet_dominance_ratio = (
        max(ce_oi, pe_oi) / max(1.0, min(ce_oi, pe_oi))
        if magnet_combined > 0
        else 0.0
    )
    interpretation = _resolve_magnet_interpretation(pull, character)

    between = False
    compression = False
    sec_strike: int | None = None
    secondary_distance_pts: float | None = None
    min_secondary_distance = max(1, int(strike_gap)) * 3
    secondary = next(
        (
            row
            for row in scored[1:]
            if abs(int(row["strike"]) - magnet_strike) >= min_secondary_distance
        ),
        None,
    )
    show_secondary_magnet = (
        character not in {"balanced", "unknown"}
        and magnet_strength >= 0.15
        and magnet_dominance_ratio >= 1.15
    )
    if secondary and show_secondary_magnet:
        sec_strike = int(secondary["strike"])
        lo = min(magnet_strike, sec_strike)
        hi = max(magnet_strike, sec_strike)
        between = lo <= spot <= hi
        secondary_distance_pts = float(abs(sec_strike - magnet_strike))
        compression = bool(
            secondary_distance_pts <= (6 * max(1, int(strike_gap)))
            and between
        )

    return {
        "price_magnet_strike": magnet_strike,
        "price_magnet_combined": round(magnet_combined, 0),
        "magnet_pull_direction": pull,
        "magnet_interpretation": interpretation,
        "magnet_distance_pts": round(distance, 1) if distance is not None else None,
        "secondary_magnet": sec_strike,
        "secondary_magnet_distance_pts": secondary_distance_pts,
        "between_magnets": between,
        "magnet_ce_pct": round(ce_pct, 1),
        "magnet_pe_pct": round(pe_pct, 1),
        "magnet_character": character,
        "magnet_strength": round(float(magnet_strength), 4),
        "magnet_dominance_ratio": round(float(magnet_dominance_ratio), 4),
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
    """
    Returns True when the wall is holding (writers steady — not adding or exiting).
    Strengthening (>+2%) and weakening (<-1%) are separate states not captured here;
    callers that need the full 3-state picture should call _compute_wall_state().
    """
    if not level_row:
        return False
    if side == "resistance":
        chg = _safe_float(level_row.get("oi_ce_change"), 1e9)
    else:
        chg = _safe_float(level_row.get("oi_pe_change"), 1e9)
    return -0.01 <= chg < 0.02


def _compute_wall_state(level_row: dict[str, Any] | None, side: str) -> str:
    """3-state wall status: 'strengthening' | 'holding' | 'weakening'."""
    if not level_row:
        return "weakening"
    if side == "resistance":
        chg = _safe_float(level_row.get("oi_ce_change"), 1e9)
    else:
        chg = _safe_float(level_row.get("oi_pe_change"), 1e9)
    if chg >= 0.02:
        return "strengthening"
    if chg <= -0.01:
        return "weakening"
    return "holding"


def _compute_defense_ratio(level_row: dict[str, Any] | None, side: str) -> float:
    if not level_row:
        return 0.0
    oi_ce = _safe_float(level_row.get("oi_ce"), 0.0)
    oi_pe = _safe_float(level_row.get("oi_pe"), 0.0)
    if side == "resistance":
        return oi_ce / max(oi_pe, 1.0)
    return oi_pe / max(oi_ce, 1.0)


def _find_wall_strike(
    liquidity_map: list[dict[str, Any]],
    side: str,
    spot: float = 0.0,
    strike_gap: int = 50,
) -> int | None:
    if not liquidity_map:
        return None
    # Search window: 10 strike gaps in the relevant direction.
    search_window = 10 * strike_gap
    best_row: dict[str, Any] | None = None
    best_oi = -1.0
    for row in liquidity_map:
        strike = _safe_int(row.get("strike"), 0)
        if strike <= 0:
            continue
        if spot > 0:
            if side == "PE":
                # PE wall = put writer floor = must be at or below spot.
                if strike > spot:
                    continue
                if strike < spot - search_window:
                    continue
            elif side == "CE":
                # CE wall = call writer ceiling = must be at or above spot.
                if strike < spot:
                    continue
                if strike > spot + search_window:
                    continue
        oi_key = "oi_pe" if side == "PE" else "oi_ce"
        oi_value = _safe_float(row.get(oi_key), 0.0)
        if oi_value > best_oi:
            best_oi = oi_value
            best_row = row
    return _safe_int((best_row or {}).get("strike"), 0) or None


def _get_oi_change(
    liquidity_map: list[dict[str, Any]] | None,
    level: float,
    side: str,
) -> float:
    """
    Get the OI change at the strike closest to `level`.
    Returns 0.0 if liquidity_map is None or empty.
    """
    if not liquidity_map or level <= 0:
        return 0.0
    row = min(
        liquidity_map,
        key=lambda r: abs(_safe_float((r or {}).get("strike"), 0.0) - level),
    )
    key = f"oi_{side}_change"
    return _safe_float((row or {}).get(key), 0.0)


def _compute_directional_signal(
    spot: float,
    support: float,
    resistance: float,
    magnet: float,
    magnet_pull_direction: str,
    max_pain_strike: float | None,
    pe_wall: float,
    ce_wall: float,
    defense_ratio_pe: float,
    defense_ratio_ce: float,
    pe_wall_defense: float,
    ce_wall_defense: float,
    trap_probability: float,
    strike_gap: int,
    chain_greeks: list[dict[str, Any]],
    liquidity_map: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    defended_threshold = 1.2
    exposed_threshold = 1.0
    min_rr = 0.5
    level_proximity = 4 * strike_gap

    dist_to_r = resistance - spot
    dist_to_s = spot - support
    if dist_to_r > level_proximity and dist_to_s > level_proximity:
        return {
            "signal": "WAIT",
            "bias": "NEUTRAL",
            "wall_status": "NEUTRAL",
            "stop_valid": False,
            "rr": 0.0,
            "size": None,
            "entry_strike": None,
            "entry_premium": None,
            "entry_option": None,
            "stop_anchor": (support + resistance) / 2.0 if resistance > support else None,
            "target_1": magnet if magnet > 0 else None,
            "reason": "Spot not near any level",
        }

    if magnet_pull_direction == "up":
        bias = "BULLISH"
    elif magnet_pull_direction == "down":
        bias = "BEARISH"
    else:
        bias = "NEUTRAL"

    wall_ratio = 0.0
    if bias == "BULLISH":
        wall_ratio = defense_ratio_ce
        if wall_ratio >= defended_threshold:
            wall_status = "BLOCKED"
        elif wall_ratio < exposed_threshold:
            wall_status = "CONFIRMED"
        else:
            wall_status = "WEAK"
        stop_anchor = pe_wall if pe_wall > 0 else support
        effective_pe_defense = max(pe_wall_defense, defense_ratio_pe)
        stop_valid = effective_pe_defense >= defended_threshold
        risk = abs(spot - (stop_anchor - strike_gap))
    elif bias == "BEARISH":
        wall_ratio = defense_ratio_pe
        if wall_ratio >= defended_threshold:
            wall_status = "BLOCKED"
        elif wall_ratio < exposed_threshold:
            wall_status = "CONFIRMED"
        else:
            wall_status = "WEAK"
        stop_anchor = ce_wall if ce_wall > 0 else resistance
        effective_ce_defense = max(ce_wall_defense, defense_ratio_ce)
        stop_valid = effective_ce_defense >= defended_threshold
        risk = abs(spot - (stop_anchor + strike_gap))
    else:
        wall_status = "NEUTRAL"
        stop_anchor = (support + resistance) / 2.0 if resistance > support else spot
        stop_valid = True
        risk = abs(spot - stop_anchor)

    reward = abs(spot - magnet) if magnet > 0 else 0.0
    rr = round(reward / risk, 2) if risk > 0 else 0.0
    trap_ok = trap_probability < 55
    ce_oi_chg = _get_oi_change(liquidity_map, resistance, "ce")
    pe_oi_chg = _get_oi_change(liquidity_map, support, "pe")
    ce_clusters = sorted(
        [
            _safe_int(row.get("strike"), 0)
            for row in (liquidity_map or [])
            if _safe_int(row.get("strike"), 0) > spot
        ]
    )
    pe_clusters = sorted(
        [
            _safe_int(row.get("strike"), 0)
            for row in (liquidity_map or [])
            if 0 < _safe_int(row.get("strike"), 0) < spot
        ],
        reverse=True,
    )

    signal = "WAIT"
    size: str | None = None
    reason = "Conditions not fully aligned"
    entry_option: str | None = None
    entry_strike: int | None = None
    entry_premium: float | None = None
    target_1: float | None = magnet if magnet > 0 else None

    breakout_above_resistance = (
        spot > resistance
        and defense_ratio_ce < exposed_threshold
        and not (magnet < spot - strike_gap)
        and trap_probability < 55
        and ce_oi_chg < -0.05
    )
    breakdown_below_support = (
        spot < support
        and defense_ratio_pe < exposed_threshold
        and not (magnet > spot + strike_gap)
        and trap_probability < 50
        and pe_oi_chg < -0.05
    )
    rejection_at_resistance = (
        spot >= resistance - strike_gap
        and magnet_pull_direction == "down"
        and magnet < spot
        and abs(magnet - spot) <= 5 * strike_gap
        and (max_pain_strike is None or max_pain_strike <= spot)
        and trap_probability < 60
    )
    bounce_at_support = (
        spot <= support + strike_gap
        and magnet_pull_direction == "up"
        and magnet > spot
        and abs(magnet - spot) <= 5 * strike_gap
        and (max_pain_strike is None or max_pain_strike >= spot)
        and trap_probability < 60
    )

    if breakout_above_resistance:
        signal = "BREAKOUT_ABOVE_RESISTANCE"
        size = "standard"
        entry_option = "CE"
        stop_anchor = resistance - strike_gap
        risk = abs(spot - stop_anchor)
        target_1 = float(ce_clusters[0]) if ce_clusters else (magnet if magnet > 0 else None)
        rr = round(abs((target_1 or spot) - spot) / risk, 2) if risk > 0 and target_1 is not None else 0.0
        reason = (
            f"Spot above resistance {resistance:.0f} + CE OI dropping ({ce_oi_chg:.2f}) + "
            f"resistance exposed ({defense_ratio_ce:.2f}x) - breakout continuation CE buy."
        )
    elif breakdown_below_support:
        signal = "BREAKDOWN_BELOW_SUPPORT"
        size = "standard"
        entry_option = "PE"
        stop_anchor = support + strike_gap
        risk = abs(spot - stop_anchor)
        target_1 = float(pe_clusters[0]) if pe_clusters else (magnet if magnet > 0 else None)
        rr = round(abs((target_1 or spot) - spot) / risk, 2) if risk > 0 and target_1 is not None else 0.0
        reason = (
            f"Spot below support {support:.0f} + PE OI dropping ({pe_oi_chg:.2f}) + "
            f"support exposed ({defense_ratio_pe:.2f}x) - breakdown continuation PE buy."
        )
    elif rejection_at_resistance:
        if trap_probability >= 55:
            reason = (
                f"Trap too high ({trap_probability:.0f}%) - wait below 60 for REJECTION_AT_RESISTANCE"
            )
        else:
            signal = "REJECTION_AT_RESISTANCE"
            size = "standard" if trap_probability < 45 else "reduced"
            entry_option = "PE"
            stop_anchor = resistance + strike_gap
            risk = abs(stop_anchor - spot)
            target_1 = magnet if magnet > 0 else max_pain_strike
            rr = round(abs((target_1 or spot) - spot) / risk, 2) if risk > 0 and target_1 is not None else 0.0
            reason = (
                f"Spot {spot:.0f} testing resistance {resistance:.0f} with magnet {magnet:.0f} pulling "
                f"down {abs(magnet - spot):.0f}pts - rejection fade PE buy."
            )
    elif bounce_at_support:
        if trap_probability >= 55:
            reason = f"Trap too high ({trap_probability:.0f}%) - wait below 60 for BOUNCE_AT_SUPPORT"
        else:
            signal = "BOUNCE_AT_SUPPORT"
            size = "standard" if trap_probability < 45 else "reduced"
            entry_option = "CE"
            stop_anchor = support - strike_gap
            risk = abs(spot - stop_anchor)
            target_1 = magnet if magnet > 0 else max_pain_strike
            rr = round(abs((target_1 or spot) - spot) / risk, 2) if risk > 0 and target_1 is not None else 0.0
            reason = (
                f"Spot {spot:.0f} testing support {support:.0f} with magnet {magnet:.0f} pulling "
                f"up {abs(magnet - spot):.0f}pts - bounce CE buy."
            )
    elif bias == "BULLISH" and wall_status == "CONFIRMED" and stop_valid and rr >= min_rr and trap_ok:
        signal = "BUY_CE"
        size = "standard"
    elif bias == "BEARISH" and wall_status == "CONFIRMED" and stop_valid and rr >= min_rr and trap_ok:
        signal = "BUY_PE"
        size = "standard"
    elif bias == "NEUTRAL" and defense_ratio_ce >= defended_threshold and defense_ratio_pe >= defended_threshold:
        signal = "SELL_STRADDLE"
        size = "standard"
        reason = "Both walls defended with neutral magnet; premium-selling pin setup."
    elif bias == "BULLISH" and wall_status == "BLOCKED":
        reason = f"Magnet pulling up but resistance defended ({wall_ratio:.2f}x) - ceiling will block"
    elif bias == "BULLISH" and wall_status == "WEAK":
        reason = f"Magnet pulling up but resistance is only weakly exposed ({wall_ratio:.2f}x) - wait for clean breakout"
    elif bias == "BEARISH" and wall_status == "BLOCKED":
        reason = f"Magnet pulling down but support defended ({wall_ratio:.2f}x) - floor will hold"
    elif bias == "BEARISH" and wall_status == "WEAK":
        reason = f"Magnet pulling down but support is only weakly exposed ({wall_ratio:.2f}x) - wait for clean breakdown"
    elif bias == "BULLISH" and not stop_valid:
        reason = f"Magnet up and resistance exposed, but PE floor is not defended enough ({pe_wall_defense:.2f}x)"
    elif bias == "BEARISH" and not stop_valid:
        reason = f"Magnet down and support exposed, but CE ceiling is not defended enough ({ce_wall_defense:.2f}x)"
    elif bias in {"BULLISH", "BEARISH"} and rr < min_rr:
        reason = f"Directional setup found but RR too low ({rr:.2f}x) - need at least {min_rr:.2f}x"
    elif not trap_ok:
        reason = f"Trap risk too high ({trap_probability:.0f}%) - wait for it to ease below 55"

    max_pain_ref = _safe_float(max_pain_strike, spot)
    if signal in {"BUY_CE", "BREAKOUT_ABOVE_RESISTANCE", "BOUNCE_AT_SUPPORT"}:
        entry_option = "CE"
        for row in chain_greeks:
            ce_leg = row.get("ce") or {}
            delta = _safe_float(ce_leg.get("delta"), 0.0)
            ltp = _safe_float(ce_leg.get("ltp"), 0.0)
            strike = _safe_int(row.get("strike"), 0)
            if signal == "BREAKOUT_ABOVE_RESISTANCE":
                strike_ok = strike >= spot
                delta_ok = 0.35 <= delta <= 0.55
            elif signal == "BOUNCE_AT_SUPPORT":
                strike_ok = abs(strike - spot) <= 2 * strike_gap
                delta_ok = 0.35 <= delta <= 0.55
            else:
                strike_ok = strike >= max_pain_ref
                delta_ok = 0.30 <= delta <= 0.50
            if strike_ok and delta_ok and ltp >= 5.0:
                entry_strike = strike
                entry_premium = ltp
                break
    elif signal in {"BUY_PE", "BREAKDOWN_BELOW_SUPPORT", "REJECTION_AT_RESISTANCE"}:
        entry_option = "PE"
        for row in sorted(chain_greeks, key=lambda r: -_safe_int(r.get("strike"), 0)):
            pe_leg = row.get("pe") or {}
            delta = abs(_safe_float(pe_leg.get("delta"), 0.0))
            ltp = _safe_float(pe_leg.get("ltp"), 0.0)
            strike = _safe_int(row.get("strike"), 0)
            if signal == "BREAKDOWN_BELOW_SUPPORT":
                strike_ok = strike <= spot
                delta_ok = 0.35 <= delta <= 0.55
            elif signal == "REJECTION_AT_RESISTANCE":
                strike_ok = abs(strike - spot) <= 2 * strike_gap
                delta_ok = 0.35 <= delta <= 0.55
            else:
                strike_ok = strike <= max_pain_ref
                delta_ok = 0.30 <= delta <= 0.50
            if strike_ok and delta_ok and ltp >= 5.0:
                entry_strike = strike
                entry_premium = ltp
                break

    if signal in {"BUY_CE", "BUY_PE", "SELL_STRADDLE"}:
        defended_text = "exposed" if wall_status == "CONFIRMED" else wall_status.lower()
        reason = (
            f"Magnet {magnet_pull_direction} + "
            f"{'resistance' if bias == 'BULLISH' else 'support' if bias == 'BEARISH' else 'walls'} "
            f"{defended_text} ({wall_ratio:.2f}x) + PE floor {pe_wall_defense:.2f}x"
        )

    return {
        "signal": signal,
        "bias": bias,
        "wall_status": wall_status,
        "stop_valid": stop_valid,
        "rr": rr,
        "size": size,
        "entry_strike": entry_strike,
        "entry_premium": entry_premium,
        "entry_option": entry_option,
        "stop_anchor": stop_anchor,
        "target_1": target_1,
        "reason": reason,
    }


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
        symbol = str(context.get("symbol") or "")
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
        previous_magnet_pull_direction = _non_empty_text(
            context.get("previous_magnet_pull_direction"),
            "at",
        ).lower()

        # Intermediates
        atm_row = _closest_chain_row(chain_greeks, spot)
        atm_strike = _safe_int((atm_row or {}).get("strike"), 0)
        atm_ce_ltp = _get_leg_ltp(atm_row, "CE")
        atm_pe_ltp = _get_leg_ltp(atm_row, "PE")
        atm_straddle_premium = (atm_ce_ltp + atm_pe_ltp) if (atm_ce_ltp > 0 and atm_pe_ltp > 0) else None
        straddle_trend = _compute_straddle_trend(atm_straddle_premium, _safe_float(prev_straddle_premium, 0.0))
        iv_skew, iv_skew_magnitude = _compute_iv_skew(atm_pe_iv, atm_ce_iv)

        max_pain_metrics = _compute_max_pain_metrics(
            liquidity_map=liquidity_map,
            spot=spot,
            strike_gap=strike_gap,
            symbol=symbol,
        )
        max_pain_strike = _safe_int(max_pain_metrics.get("max_pain_strike"), 0) or None
        max_pain_confidence = _safe_float(max_pain_metrics.get("max_pain_confidence"), 0.0)
        max_pain_strength = _non_empty_text(max_pain_metrics.get("max_pain_strength"), "Weak")
        max_pain_distance, max_pain_pull = _compute_max_pain_pull(spot, max_pain_strike, strike_gap)
        magnet_result = _compute_price_magnet(
            liquidity_map=liquidity_map,
            spot=spot,
            strike_gap=strike_gap,
            previous_direction=previous_magnet_pull_direction,
        )
        pe_wall = _find_wall_strike(liquidity_map, "PE", spot=spot, strike_gap=strike_gap)
        ce_wall = _find_wall_strike(liquidity_map, "CE", spot=spot, strike_gap=strike_gap)

        resistance_row = _closest_row_by_strike(liquidity_map, resistance)
        support_row = _closest_row_by_strike(liquidity_map, support)
        pe_wall_row = _closest_row_by_strike(liquidity_map, float(pe_wall)) if pe_wall else None
        ce_wall_row = _closest_row_by_strike(liquidity_map, float(ce_wall)) if ce_wall else None
        resistance_row_strike = _safe_int((resistance_row or {}).get("strike"), 0)
        support_row_strike = _safe_int((support_row or {}).get("strike"), 0)

        resistance_pcr = _compute_level_pcr(resistance_row)
        support_pcr = _compute_level_pcr(support_row)
        ce_wall_holding = _compute_wall_holding(resistance_row, "resistance")
        pe_wall_holding = _compute_wall_holding(support_row, "support")
        pe_wall_defense = _compute_defense_ratio(pe_wall_row, "support")
        ce_wall_defense = _compute_defense_ratio(ce_wall_row, "resistance")
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

        directional = _compute_directional_signal(
            spot=spot,
            support=support,
            resistance=resistance,
            magnet=_safe_float(magnet_result.get("price_magnet_strike"), 0.0),
            magnet_pull_direction=_non_empty_text(magnet_result.get("magnet_pull_direction"), "unknown"),
            max_pain_strike=float(max_pain_strike) if max_pain_strike is not None else None,
            pe_wall=float(pe_wall or 0.0),
            ce_wall=float(ce_wall or 0.0),
            defense_ratio_pe=defense_ratio_pe,
            defense_ratio_ce=defense_ratio_ce,
            pe_wall_defense=pe_wall_defense,
            ce_wall_defense=ce_wall_defense,
            trap_probability=trap_probability,
            strike_gap=strike_gap,
            chain_greeks=chain_greeks,
            liquidity_map=liquidity_map,
        )

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
            "max_pain_confidence": max_pain_confidence,
            "max_pain_strength": max_pain_strength,
            "max_pain_distance": max_pain_distance,
            "max_pain_pull": max_pain_pull,
            "price_magnet_strike": magnet_result.get("price_magnet_strike"),
            "price_magnet_combined": magnet_result.get("price_magnet_combined"),
            "magnet_pull_direction": magnet_result.get("magnet_pull_direction"),
            "magnet_interpretation": magnet_result.get("magnet_interpretation"),
            "magnet_distance_pts": magnet_result.get("magnet_distance_pts"),
            "secondary_magnet": magnet_result.get("secondary_magnet"),
            "secondary_magnet_distance_pts": magnet_result.get("secondary_magnet_distance_pts"),
            "between_magnets": bool(magnet_result.get("between_magnets", False)),
            "magnet_ce_pct": magnet_result.get("magnet_ce_pct"),
            "magnet_pe_pct": magnet_result.get("magnet_pe_pct"),
            "magnet_character": magnet_result.get("magnet_character"),
            "magnet_strength": magnet_result.get("magnet_strength"),
            "magnet_dominance_ratio": magnet_result.get("magnet_dominance_ratio"),
            "compression_zone": bool(magnet_result.get("compression_zone", False)),
            "iv_skew": iv_skew,
            "iv_skew_magnitude": iv_skew_magnitude,
            "atm_straddle_premium": atm_straddle_premium,
            "straddle_trend": straddle_trend,
            "pe_wall_strike": pe_wall,
            "ce_wall_strike": ce_wall,
            "ce_wall_holding": bool(ce_wall_holding),
            "pe_wall_holding": bool(pe_wall_holding),
            "resistance_pcr": resistance_pcr,
            "support_pcr": support_pcr,
            "volume_spike_strikes": volume_spike_strikes,
            "trade_side_routing": trade_side_routing,
            "iv_percentile": iv_percentile,
            "atm_strike": atm_strike if atm_strike > 0 else None,
            "directional_signal": directional.get("signal"),
            "directional_reason": directional.get("reason"),
            "directional_bias": directional.get("bias"),
            "directional_size": directional.get("size"),
            "directional_strike": directional.get("entry_strike"),
            "directional_rr": directional.get("rr"),
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
            "max_pain_confidence": 0.0,
            "max_pain_strength": "Weak",
            "max_pain_distance": None,
            "max_pain_pull": "unknown",
            "price_magnet_strike": None,
            "price_magnet_combined": 0.0,
            "magnet_pull_direction": "unknown",
            "magnet_interpretation": "unknown",
            "magnet_distance_pts": None,
            "secondary_magnet": None,
            "secondary_magnet_distance_pts": None,
            "between_magnets": False,
            "magnet_ce_pct": 0.0,
            "magnet_pe_pct": 0.0,
            "magnet_character": "unknown",
            "magnet_strength": 0.0,
            "magnet_dominance_ratio": 0.0,
            "compression_zone": False,
            "iv_skew": "neutral",
            "iv_skew_magnitude": 0.0,
            "atm_straddle_premium": None,
            "straddle_trend": "unknown",
            "pe_wall_strike": None,
            "ce_wall_strike": None,
            "ce_wall_holding": False,
            "pe_wall_holding": False,
            "resistance_pcr": None,
            "support_pcr": None,
            "volume_spike_strikes": [],
            "trade_side_routing": "UNKNOWN",
            "directional_signal": "WAIT",
            "directional_reason": "Engine fallback: invalid or incomplete context",
            "directional_bias": "NEUTRAL",
            "directional_size": None,
            "directional_strike": None,
            "directional_rr": 0.0,
        }
