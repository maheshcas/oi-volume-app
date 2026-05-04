from datetime import datetime, timezone
from typing import Any

NO_BREAKOUT_VALIDITY_FLOOR = 0.55

# Module-level rolling state for absorption signal (keyed by rounded support/resistance level).
# Persists across cycles within a process lifetime; resets automatically when the level shifts.
_ABS_ROLLING: dict[str, Any] = {}


def estimate_iv_realized_ratio(
    *,
    atm_ce_ltp: float,
    atm_pe_ltp: float,
    band_width: float,
    atr: float,
) -> dict[str, Any]:
    """
    Estimate an implied vs realized volatility ratio from market-observable inputs.

    IV proxy  = ATM straddle price (CE_LTP + PE_LTP) expressed as % of midpoint.
    RV proxy  = Current ATR expressed as % of midpoint (band_width / 2 ≈ midpoint offset).

    ratio > 1.15 → IV elevated vs realized (options expensive, crush risk high).
    ratio < 0.85 → IV depressed vs realized (options cheap, expansion risk).
    0.85–1.15   → balanced.
    """
    straddle = max(0.0, float(atm_ce_ltp) + float(atm_pe_ltp))
    bw = max(1.0, float(band_width))
    rv_proxy = max(1e-9, float(atr))
    # Express both as fractions of band_width to make them comparable.
    iv_proxy = straddle / bw
    rv_frac = rv_proxy / bw
    ratio = iv_proxy / max(1e-9, rv_frac)

    if ratio > 1.15:
        iv_state = "IV_elevated"        # premium decay risk; traps more likely to resolve fast
    elif ratio < 0.85:
        iv_state = "IV_depressed"       # expansion risk; breakouts may carry further
    else:
        iv_state = "IV_balanced"

    return {
        "iv_realized_ratio": round(ratio, 4),
        "iv_state": iv_state,
        "iv_proxy": round(iv_proxy, 6),
        "rv_proxy_frac": round(rv_frac, 6),
        "straddle_price": round(straddle, 2),
    }


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _validate_01(name: str, value: float) -> None:
    if not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    if value < 0.0 or value > 1.0:
        raise ValueError(f"{name} must be in range [0, 1]")


def adjust_trap_probability_for_volatility(
    *, base_trap_probability: float, current_atr: float, rolling_atr_mean: float
) -> dict[str, float]:
    """
    Volatility adjustment for trap probability.
    Inputs are in percentage space for base_trap_probability (0-100),
    ATR inputs are absolute positive values.
    """
    if not isinstance(base_trap_probability, (int, float)):
        raise ValueError("base_trap_probability must be numeric")
    if not isinstance(current_atr, (int, float)):
        raise ValueError("current_atr must be numeric")
    if not isinstance(rolling_atr_mean, (int, float)):
        raise ValueError("rolling_atr_mean must be numeric")

    base = float(base_trap_probability)
    atr_now = float(current_atr)
    atr_avg = float(rolling_atr_mean)

    if atr_avg <= 0:
        vol_ratio = 1.0
    else:
        vol_ratio = atr_now / atr_avg

    if vol_ratio < 0.8:
        multiplier = 1.2
    elif vol_ratio > 1.2:
        multiplier = 0.8
    else:
        multiplier = 1.0

    adjusted_trap = base * multiplier
    adjusted_trap = max(5.0, min(95.0, adjusted_trap))

    return {
        "trap_probability": int(round(adjusted_trap)),
        "volatility_factor": round(multiplier, 4),
    }


def adjust_trap_by_confidence(
    *, base_trap: float, smoothed_score: float, confidence_percent: float
) -> dict[str, float]:
    """
    Confidence-aware trap adjustment.
    smoothed_score is accepted for future extension; current rule uses confidence only.
    """
    if not isinstance(base_trap, (int, float)):
        raise ValueError("base_trap must be numeric")
    if not isinstance(smoothed_score, (int, float)):
        raise ValueError("smoothed_score must be numeric")
    if not isinstance(confidence_percent, (int, float)):
        raise ValueError("confidence_percent must be numeric")

    conf = max(0.0, min(100.0, float(confidence_percent)))
    confidence_factor = 1.0 - ((conf / 100.0) * 0.5)
    adjusted_trap = float(base_trap) * confidence_factor
    adjusted_trap = max(5.0, min(95.0, adjusted_trap))

    return {
        "trap_probability": int(round(adjusted_trap)),
        "confidence_factor": round(confidence_factor, 4),
    }


def trap_engine_v2(
    *,
    breakout_strength: float,
    atm_participation_score: float,
    oi_shift_score: float,
    volume_expansion_score: float,
    rejection_wick_score: float,
    time_above_level_ratio: float,
    volatility_factor: float,
    current_price: float | None = None,
    breakout_level: float | None = None,
    atr: float | None = None,
    volume_after_break: float | None = None,
    breakout_volume: float | None = None,
    warmup_active: bool = False,
) -> dict[str, Any]:
    """
    Institutional-grade Trap Engine v2.

    All inputs are normalized in range [0, 1].
    """
    _validate_01("breakout_strength", breakout_strength)
    _validate_01("atm_participation_score", atm_participation_score)
    _validate_01("oi_shift_score", oi_shift_score)
    _validate_01("volume_expansion_score", volume_expansion_score)
    _validate_01("rejection_wick_score", rejection_wick_score)
    _validate_01("time_above_level_ratio", time_above_level_ratio)
    _validate_01("volatility_factor", volatility_factor)

    # STEP 1 — Breakout validity
    validity_score = (
        (0.40 * breakout_strength)
        + (0.25 * atm_participation_score)
        + (0.20 * oi_shift_score)
        + (0.15 * volume_expansion_score)
    )
    no_breakout_validity_floor_applied = False
    if float(breakout_strength) <= 1e-6:
        # Quiet sessions can otherwise inherit an artificial trap baseline from
        # structural-failure weighting despite no real breakout attempt.
        if validity_score < NO_BREAKOUT_VALIDITY_FLOOR:
            validity_score = NO_BREAKOUT_VALIDITY_FLOOR
            no_breakout_validity_floor_applied = True

    # Liquidity absorption detection.
    absorption_score = 0.0
    if (
        isinstance(current_price, (int, float))
        and isinstance(breakout_level, (int, float))
        and isinstance(atr, (int, float))
        and isinstance(volume_after_break, (int, float))
        and isinstance(breakout_volume, (int, float))
    ):
        expected_move = max(1e-9, float(atr) * max(0.0, float(breakout_strength)))
        price_progress = abs(float(current_price) - float(breakout_level))
        absorption_ratio = 1.0 - min(1.0, price_progress / expected_move)
        volume_follow_through = float(volume_after_break) / max(1e-9, float(breakout_volume))
        absorption_score = (0.6 * absorption_ratio) + (0.4 * (1.0 - min(1.0, max(0.0, volume_follow_through))))
        absorption_score = _clamp01(absorption_score)

    # STEP 2 — Trap raw score
    structural_failure = 1.0 - validity_score
    hold_time_failure = (1.0 - time_above_level_ratio)
    volume_continuation_failure = (1.0 - volume_expansion_score)
    weights = {
        "structural": 0.45,
        "wick": 0.30,
        "hold_time": 0.12,
        "volume_cont": 0.08,
        "volatility": 0.05,
        "absorption": 0.10,
    }
    if warmup_active:
        # During warm-up, down-weight wick/hold-time contribution.
        weights["wick"] = 0.10
        weights["hold_time"] = 0.10

    weight_total = sum(weights.values())
    if weight_total <= 0:
        weight_total = 1.0
    norm = {k: (v / weight_total) for k, v in weights.items()}

    trap_raw = (
        (norm["structural"] * structural_failure)
        + (norm["wick"] * rejection_wick_score)
        + (norm["hold_time"] * hold_time_failure)
        + (norm["volume_cont"] * volume_continuation_failure)
        + (norm["volatility"] * volatility_factor)
        + (norm["absorption"] * absorption_score)
    )

    # Proportional boost for classic fake breakout instead of fixed jump.
    if breakout_strength > 0.7 and rejection_wick_score > 0.7 and time_above_level_ratio < 0.3:
        trap_raw += 0.15 * breakout_strength

    trap_raw = _clamp01(trap_raw)
    trap_probability = int(round(trap_raw * 100))

    # STEP 3 — Classification
    if trap_raw > 0.65:
        trap_level = "High"
    elif trap_raw > 0.45:
        trap_level = "Moderate"
    else:
        trap_level = "Low"

    if trap_raw > 0.45:
        if rejection_wick_score > 0.7 and time_above_level_ratio < 0.3:
            trap_type = "Liquidity Sweep"
        elif validity_score < 0.45 and time_above_level_ratio < 0.5:
            trap_type = "Breakout Failure"
        elif volume_expansion_score > 0.7 and time_above_level_ratio < 0.4:
            trap_type = "Exhaustion"
        else:
            trap_type = None
    else:
        trap_type = None

    return {
        "trap_probability": trap_probability,
        "trap_level": trap_level,
        "trap_type": trap_type,
        "validity_score": round(validity_score, 4),
        "no_breakout_validity_floor_applied": bool(no_breakout_validity_floor_applied),
        "absorption_score": round(absorption_score, 4),
        "trap_raw": round(trap_raw, 4),
        "warmup_active": bool(warmup_active),
        "weight_distribution": {k: round(v, 4) for k, v in norm.items()},
    }


def detect_fake_breakout(
    breakout: dict[str, Any], oi_alignment: str, atm_participation: float, volume_expansion: bool
) -> tuple[bool, float]:
    breakout_attempt = breakout.get("breakout_up") or breakout.get("breakout_down")
    if not breakout_attempt:
        return False, 0.0

    score = 0.0
    if atm_participation < 0.4:
        score += 45
    if not volume_expansion:
        score += 30
    if breakout.get("breakout_up") and oi_alignment != "bullish":
        score += 25
    if breakout.get("breakout_down") and oi_alignment != "bearish":
        score += 25

    return score >= 60, min(100.0, score)


def _parse_epoch_seconds(timestamp_text: str | None) -> int:
    if not timestamp_text:
        return int(datetime.now(timezone.utc).timestamp())
    for fmt in ("%d-%b-%Y %H:%M:%S", "%d-%b-%Y %H:%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            return int(datetime.strptime(timestamp_text, fmt).replace(tzinfo=timezone.utc).timestamp())
        except ValueError:
            continue
    return int(datetime.now(timezone.utc).timestamp())


def _build_spot_observations(
    previous_state: dict[str, Any] | None,
    spot: float | None,
    timestamp_text: str | None,
    max_points: int = 40,
    window_seconds: int = 120,
) -> list[dict[str, float]]:
    observations_raw = (previous_state or {}).get("spot_observations", [])
    observations: list[dict[str, float]] = []
    for item in observations_raw if isinstance(observations_raw, list) else []:
        try:
            ts = int(item.get("ts"))  # type: ignore[arg-type]
            px = float(item.get("spot"))  # type: ignore[arg-type]
            observations.append({"ts": ts, "spot": px})
        except Exception:
            continue

    current_ts = _parse_epoch_seconds(timestamp_text)
    if spot is not None:
        observations.append({"ts": current_ts, "spot": float(spot)})

    observations = sorted(observations, key=lambda x: x["ts"])[-max_points:]

    # Keep a rolling observation window (60-120 seconds target).
    latest_ts = observations[-1]["ts"] if observations else current_ts
    min_ts = latest_ts - max(60, min(120, int(window_seconds)))
    observations = [x for x in observations if float(x["ts"]) >= float(min_ts)]

    # Deduplicate by timestamp (keep last value seen for a timestamp).
    dedup: dict[int, float] = {}
    for item in observations:
        dedup[int(item["ts"])] = float(item["spot"])
    return [{"ts": float(ts), "spot": float(px)} for ts, px in sorted(dedup.items(), key=lambda kv: kv[0])]


def _time_ratio(
    observations: list[dict[str, float]],
    level: float,
    *,
    mode: str = "above",
) -> float:
    if len(observations) < 2:
        if not observations:
            return 0.0
        spot = float(observations[-1]["spot"])
        return 1.0 if ((mode == "above" and spot > level) or (mode == "below" and spot < level)) else 0.0

    total = 0.0
    active = 0.0
    for i in range(1, len(observations)):
        prev = observations[i - 1]
        cur = observations[i]
        dt = max(0.0, float(cur["ts"] - prev["ts"]))
        total += dt
        spot_prev = float(prev["spot"])
        cond = spot_prev > level if mode == "above" else spot_prev < level
        if cond:
            active += dt
    if total <= 0:
        return 0.0
    return max(0.0, min(1.0, active / total))


def _rejection_wick_score(
    observations: list[dict[str, float]],
    level: float,
    *,
    direction: str,
) -> float:
    if len(observations) < 2:
        return 0.0
    prices = [float(x["spot"]) for x in observations]
    open_price = prices[0]
    high = max(prices)
    low = min(prices)
    close = prices[-1]
    candle_range = max(1e-9, high - low)
    _ = level  # level-aware filtering can be layered later if needed.

    upper_wick = max(0.0, high - max(open_price, close))
    lower_wick = max(0.0, min(open_price, close) - low)
    # Direction-aware rejection wick:
    # - upside breakout rejection should print upper wick.
    # - downside breakdown rejection should print lower wick.
    direction_text = str(direction or "").strip().lower()
    if direction_text == "up":
        wick_ratio = upper_wick / candle_range
    elif direction_text == "down":
        wick_ratio = lower_wick / candle_range
    else:
        wick_ratio = max(upper_wick, lower_wick) / candle_range
    return max(0.0, min(1.0, wick_ratio * 2.0))


def _multi_bar_wick_score(
    observations: list[dict[str, float]],
    level: float,
    *,
    direction: str,
    sub_window_size: int = 5,
) -> float:
    """
    Detect repeated rejection wicks across multiple sequential sub-windows.
    A 3-bar rejection sequence at the same level is a much stronger trap signal
    than a single-bar wick. Returns 0–1; 0.4+ = meaningful multi-bar pattern.

    Splits the observation window into sub-windows and counts how many consecutive
    sub-windows each show a rejection wick above the threshold.
    """
    if len(observations) < sub_window_size * 2:
        return 0.0

    n = len(observations)
    step = max(1, n // 4)  # divide into ~4 sub-windows
    wick_scores: list[float] = []
    for start in range(0, n - sub_window_size + 1, step):
        sub = observations[start: start + sub_window_size]
        if len(sub) < 2:
            continue
        wick_scores.append(_rejection_wick_score(sub, level, direction=direction))

    if not wick_scores:
        return 0.0

    # Count sub-windows with significant wick (> 0.4 threshold).
    significant = sum(1 for w in wick_scores if w > 0.4)
    ratio = significant / len(wick_scores)
    # Amplify: if ≥ 75% of sub-windows show rejection, this is a strong multi-bar pattern.
    return min(1.0, ratio * 1.3)


def _pullback_depth_ratio(
    observations: list[dict[str, float]],
    breakout_level: float,
    *,
    direction: str,
) -> float:
    """
    Measure how far price retracted back into the range after crossing the breakout level.
    A valid breakout should NOT retrace more than 50% of the breakout distance.
    A deep pullback (> 70%) strongly suggests the breakout was a fake.

    Returns a [0, 1] score where 1.0 = full pullback back through the level.
    """
    if len(observations) < 3 or breakout_level <= 0:
        return 0.0

    prices = [float(x["spot"]) for x in observations]
    direction_text = str(direction or "").strip().lower()

    if direction_text == "up":
        # Find the highest excursion above the breakout level, then measure retracement.
        max_above = max((p for p in prices if p > breakout_level), default=None)
        if max_above is None:
            return 0.0
        excursion = max_above - breakout_level
        if excursion < 1e-9:
            return 0.0
        # How far has price pulled back from the high?
        current = prices[-1]
        pullback = max(0.0, max_above - current)
        return min(1.0, pullback / excursion)
    elif direction_text == "down":
        min_below = min((p for p in prices if p < breakout_level), default=None)
        if min_below is None:
            return 0.0
        excursion = breakout_level - min_below
        if excursion < 1e-9:
            return 0.0
        current = prices[-1]
        pullback = max(0.0, current - min_below)
        return min(1.0, pullback / excursion)
    return 0.0


def _compute_oi_matrix_trap(
    price_direction: str,
    oi_direction: str,
    volume_category: str,
    spot: float,
    support: float,
    resistance: float,
    strike_gap: int,
    liquidity_map: list[dict[str, Any]],
    prev_spot: float | None,
    prev_oi_total: float | None,
    oi_velocity_score: float = 0.0,
) -> dict[str, Any]:
    """
    OI-price matrix classification layer.
    Returns:
      oi_trap_signal, oi_trap_confidence, oi_trap_reason, breach_level,
      breach_oi_confirming, oi_price_divergence
    """
    _ = prev_spot
    _ = prev_oi_total
    level_proximity = max(1, int(strike_gap)) * 2

    near_resistance = (resistance > 0) and (abs(float(spot) - float(resistance)) < level_proximity)
    near_support = (support > 0) and (abs(float(spot) - float(support)) < level_proximity)
    above_resistance = (resistance > 0) and (float(spot) > float(resistance))
    below_support = (support > 0) and (float(spot) < float(support))

    breach_level: float | None = None
    breach_side: str | None = None
    if above_resistance or near_resistance:
        breach_level = float(resistance)
        breach_side = "resistance"
    elif below_support or near_support:
        breach_level = float(support)
        breach_side = "support"

    level_oi_confirming: bool | None = None
    if breach_level is not None and isinstance(liquidity_map, list) and liquidity_map:
        level_row = min(
            liquidity_map,
            key=lambda r: abs(float((r or {}).get("strike", 0) or 0) - float(breach_level)),
        )
        ce_chg = float((level_row or {}).get("oi_ce_change", 0) or 0)
        pe_chg = float((level_row or {}).get("oi_pe_change", 0) or 0)

        if breach_side == "resistance":
            if price_direction == "up":
                level_oi_confirming = ce_chg < -0.05
            else:
                level_oi_confirming = ce_chg > 0.03
        elif breach_side == "support":
            if price_direction == "down":
                level_oi_confirming = pe_chg < -0.05
            else:
                level_oi_confirming = pe_chg > 0.03

    matrix_signal = "NEUTRAL"
    matrix_confidence = "Low"

    if price_direction == "up" and oi_direction == "falling":
        matrix_signal = "BULL_TRAP"
        if volume_category == "low" and (near_resistance or above_resistance):
            matrix_confidence = "High"
        elif volume_category == "low":
            matrix_confidence = "Moderate"
        elif volume_category == "high":
            # OI flush with high volume can be short-covering exhaustion:
            # still suspicious, but less clean than low-volume divergence.
            matrix_confidence = "Moderate"
        else:
            matrix_confidence = "Low"
    elif price_direction == "up" and oi_direction == "rising" and volume_category == "high":
        matrix_signal = "BULL_CONFIRM"
        matrix_confidence = "High" if oi_velocity_score >= 0.6 else "Moderate"
    elif price_direction == "down" and oi_direction == "falling":
        matrix_signal = "BEAR_TRAP"
        if volume_category == "low" and (near_support or below_support):
            matrix_confidence = "High"
        elif volume_category == "low":
            matrix_confidence = "Moderate"
        else:
            matrix_confidence = "Low"
    elif price_direction == "down" and oi_direction == "rising" and volume_category == "high":
        matrix_signal = "BEAR_CONFIRM"
        matrix_confidence = "High" if oi_velocity_score >= 0.6 else "Moderate"

    if level_oi_confirming is False and matrix_signal in ("BULL_TRAP", "BEAR_TRAP"):
        matrix_confidence = "High"
    elif level_oi_confirming is True and matrix_signal in ("BULL_TRAP", "BEAR_TRAP"):
        matrix_confidence = "Low"

    reason_map = {
        "BULL_TRAP": f"Price rising but OI falling; short covering likely near {int(resistance) if resistance else 'resistance'}.",
        "BEAR_TRAP": f"Price falling but OI falling; long unwinding likely near {int(support) if support else 'support'}.",
        "BULL_CONFIRM": "Rising price + rising OI + high volume; genuine long buildup.",
        "BEAR_CONFIRM": "Falling price + rising OI + high volume; genuine short buildup.",
        "NEUTRAL": "OI and price are not in a clear trap/confirm pattern.",
    }
    oi_price_divergence = matrix_signal in ("BULL_TRAP", "BEAR_TRAP")
    breach_oi_confirming = bool(level_oi_confirming) if level_oi_confirming is not None else True
    boost_pts = 0.0
    if matrix_signal in ("BULL_TRAP", "BEAR_TRAP"):
        boost_pts = 15.0 if matrix_confidence == "High" else 8.0 if matrix_confidence == "Moderate" else 3.0
    elif matrix_signal in ("BULL_CONFIRM", "BEAR_CONFIRM"):
        boost_pts = -15.0 if matrix_confidence == "High" else -8.0 if matrix_confidence == "Moderate" else -3.0

    return {
        "oi_trap_signal": matrix_signal,
        "oi_trap_confidence": matrix_confidence,
        "oi_trap_reason": reason_map.get(matrix_signal, "OI matrix neutral"),
        "breach_level": breach_level,
        "breach_oi_confirming": breach_oi_confirming,
        "oi_price_divergence": oi_price_divergence,
        # Telemetry-friendly aliases
        "signal": matrix_signal,
        "strength": matrix_confidence,
        "boost_pts": boost_pts,
    }


def _closest_liquidity_row(
    liquidity_map: list[dict[str, Any]] | None,
    level: float | None,
) -> dict[str, Any] | None:
    if not isinstance(liquidity_map, list) or not liquidity_map:
        return None
    if not isinstance(level, (int, float)) or float(level) <= 0:
        return None
    try:
        return min(
            liquidity_map,
            key=lambda r: abs(float((r or {}).get("strike", 0) or 0) - float(level)),
        )
    except Exception:
        return None


def _compute_absorption_signal(
    *,
    spot: float | None,
    support: float | None,
    resistance: float | None,
    strike_gap: int,
    liquidity_map: list[dict[str, Any]] | None,
    trap_probability: float,
    observations: list[dict[str, float]] | None,
) -> dict[str, Any]:
    spot_v = float(spot) if isinstance(spot, (int, float)) else None
    support_v = float(support) if isinstance(support, (int, float)) else None
    resistance_v = float(resistance) if isinstance(resistance, (int, float)) else None
    gap = max(1.0, float(strike_gap or 50))
    near_buffer = 2.0 * gap
    trap_v = float(trap_probability or 0.0)

    if spot_v is None or support_v is None or resistance_v is None:
        return {
            "absorption_signal": "NONE",
            "absorption_strength": 0.0,
            "absorption_reason": "Absorption inactive - missing structural levels.",
            "absorption_level": None,
            "absorption_confirmed": False,
            "support_absorption_strength": 0.0,
            "resistance_absorption_strength": 0.0,
        }

    prices = [float(x.get("spot", 0.0)) for x in (observations or []) if isinstance(x, dict)]
    last_price = prices[-1] if prices else spot_v

    support_row = _closest_liquidity_row(liquidity_map, support_v)
    resistance_row = _closest_liquidity_row(liquidity_map, resistance_v)
    pe_chg = float((support_row or {}).get("oi_pe_change", 0.0) or 0.0)
    ce_chg = float((resistance_row or {}).get("oi_ce_change", 0.0) or 0.0)

    near_support = spot_v <= (support_v + near_buffer)
    near_resistance = spot_v >= (resistance_v - near_buffer)

    attempted_breakdown = any(p < support_v for p in prices) if prices else (spot_v < support_v)
    attempted_breakout = any(p > resistance_v for p in prices) if prices else (spot_v > resistance_v)
    reclaimed_support = last_price >= support_v
    rejected_resistance = last_price <= resistance_v

    support_price_failure = (attempted_breakdown and reclaimed_support) or (near_support and last_price >= support_v)
    resistance_price_failure = (attempted_breakout and rejected_resistance) or (near_resistance and last_price <= resistance_v)

    support_prox = _clamp01(1.0 - max(0.0, (spot_v - support_v)) / max(1e-9, near_buffer))
    resistance_prox = _clamp01(1.0 - max(0.0, (resistance_v - spot_v)) / max(1e-9, near_buffer))
    support_failure_score = 1.0 if (attempted_breakdown and reclaimed_support) else (0.7 if support_price_failure else 0.0)
    resistance_failure_score = 1.0 if (attempted_breakout and rejected_resistance) else (0.7 if resistance_price_failure else 0.0)
    # ABS1-C3: normalization 0.12 → 0.04 so realistic OI changes (1.5–4%) produce
    # meaningful defender scores instead of near-zero values.
    support_defender_score = _clamp01((pe_chg - 0.0) / 0.04) if pe_chg > 0 else 0.0
    resistance_defender_score = _clamp01((ce_chg - 0.0) / 0.04) if ce_chg > 0 else 0.0
    trap_score = _clamp01((trap_v - 45.0) / 25.0)

    support_strength = 100.0 * (
        0.30 * support_prox
        + 0.30 * support_failure_score
        + 0.30 * support_defender_score
        + 0.10 * trap_score
    )
    resistance_strength = 100.0 * (
        0.30 * resistance_prox
        + 0.30 * resistance_failure_score
        + 0.30 * resistance_defender_score
        + 0.10 * trap_score
    )

    # ABS1-C1: Rolling 5-cycle OI accumulation gates.
    # Single-cycle 3% gate was too strict (needs 2,612 contracts/15s at 87K OI base).
    # Writers accumulate over 5-10 minutes; rolling avg over ~75s fires correctly.
    _sup_key = f"pe_{int(round(support_v / gap) * gap)}"
    _res_key = f"ce_{int(round(resistance_v / gap) * gap)}"

    # Support rolling state — reset if level shifted > 2 gaps
    _sup_state = _ABS_ROLLING.get(_sup_key) or {}
    if abs(float(_sup_state.get("level", support_v)) - support_v) > 2 * gap:
        _sup_state = {}
    _sup_state["level"] = support_v
    _sup_state["sum"] = float(_sup_state.get("sum", 0.0)) + max(pe_chg, 0.0)
    _sup_state["count"] = int(_sup_state.get("count", 0)) + 1
    _sup_window = min(_sup_state["count"], 5)
    _pe_rolling_avg = _sup_state["sum"] / _sup_window
    _ABS_ROLLING[_sup_key] = _sup_state

    # Resistance rolling state — reset if level shifted > 2 gaps
    _res_state = _ABS_ROLLING.get(_res_key) or {}
    if abs(float(_res_state.get("level", resistance_v)) - resistance_v) > 2 * gap:
        _res_state = {}
    _res_state["level"] = resistance_v
    _res_state["sum"] = float(_res_state.get("sum", 0.0)) + max(ce_chg, 0.0)
    _res_state["count"] = int(_res_state.get("count", 0)) + 1
    _res_window = min(_res_state["count"], 5)
    _ce_rolling_avg = _res_state["sum"] / _res_window
    _ABS_ROLLING[_res_key] = _res_state

    # Gate: rolling 5-cycle avg >= 1.5% OR single-cycle spike >= 3%
    _pe_oi_gate = _pe_rolling_avg > 0.015 or pe_chg > 0.03
    _ce_oi_gate = _ce_rolling_avg > 0.015 or ce_chg > 0.03

    # ABS1-C2: Absorption = writers defending a level = LOW trap condition.
    # Strength threshold lowered 55 → 50; 2-cycle hysteresis prevents single-cycle noise.
    _sup_pre = bool(
        near_support
        and support_price_failure
        and _pe_oi_gate
        and trap_v < 50.0
        and support_strength >= 50.0
    )
    _res_pre = bool(
        near_resistance
        and resistance_price_failure
        and _ce_oi_gate
        and trap_v < 50.0
        and resistance_strength >= 50.0
    )

    # 2-cycle hysteresis counters
    _sup_state["confirm"] = (int(_sup_state.get("confirm", 0)) + 1) if _sup_pre else 0
    _res_state["confirm"] = (int(_res_state.get("confirm", 0)) + 1) if _res_pre else 0

    support_confirmed = _sup_state["confirm"] >= 2
    resistance_confirmed = _res_state["confirm"] >= 2

    # Reset rolling sum when absorption fires to prevent stale accumulation
    if support_confirmed:
        _sup_state["sum"] = 0.0
        _sup_state["count"] = 0
    if resistance_confirmed:
        _res_state["sum"] = 0.0
        _res_state["count"] = 0

    if support_confirmed and (not resistance_confirmed or support_strength >= resistance_strength):
        return {
            "absorption_signal": "SUPPORT_ABSORPTION",
            "absorption_strength": round(support_strength, 1),
            "absorption_reason": (
                f"Support absorption: price failed to break {int(round(support_v))} while PE OI built "
                f"(rolling {_pe_rolling_avg:.3f}) with trap low at {int(round(trap_v))}%."
            ),
            "absorption_level": support_v,
            "absorption_confirmed": True,
            "support_absorption_strength": round(support_strength, 1),
            "resistance_absorption_strength": round(resistance_strength, 1),
        }
    if resistance_confirmed:
        return {
            "absorption_signal": "RESISTANCE_ABSORPTION",
            "absorption_strength": round(resistance_strength, 1),
            "absorption_reason": (
                f"Resistance absorption: price failed to hold above {int(round(resistance_v))} while CE OI built "
                f"(rolling {_ce_rolling_avg:.3f}) with trap low at {int(round(trap_v))}%."
            ),
            "absorption_level": resistance_v,
            "absorption_confirmed": True,
            "support_absorption_strength": round(support_strength, 1),
            "resistance_absorption_strength": round(resistance_strength, 1),
        }

    return {
        "absorption_signal": "NONE",
        "absorption_strength": round(max(support_strength, resistance_strength), 1),
        "absorption_reason": "No confirmed absorption setup at support/resistance.",
        "absorption_level": support_v if support_strength >= resistance_strength else resistance_v,
        "absorption_confirmed": False,
        "support_absorption_strength": round(support_strength, 1),
        "resistance_absorption_strength": round(resistance_strength, 1),
    }


def run_trap_engine(
    features: dict[str, Any],
    breakout: dict[str, Any],
    oi: dict[str, Any],
    volume: dict[str, Any],
    previous_state: dict[str, Any] | None = None,
    liquidity_map: list[dict[str, Any]] | None = None,
    prev_spot: float | None = None,
    prev_oi_total: float | None = None,
    strike_gap: int | None = None,
) -> dict[str, Any]:
    # Retail simplified trap logic:
    # trigger only when breakout + weak ATM OI + weak volume + not first 5 minutes.
    ts = str(features.get("meta", {}).get("timestamp") or "")
    hhmm = None
    for token in ts.replace("-", " ").replace(":", " ").split():
        if token.isdigit() and len(token) in (1, 2):
            continue
    try:
        import re

        m = re.search(r"(\d{1,2}):(\d{2})", ts)
        if m:
            hhmm = (int(m.group(1)), int(m.group(2)))
    except Exception:
        hhmm = None

    in_open_window = False
    if hhmm is not None:
        hh, mm = hhmm
        mins = hh * 60 + mm
        in_open_window = 555 <= mins < 560  # 09:15 to 09:19 IST

    rows = features.get("rows", []) or []
    atm_row = features.get("atm_row") or {}
    spot = features.get("meta", {}).get("spot")
    support = features.get("meta", {}).get("support")
    resistance = features.get("meta", {}).get("resistance")
    if support is None:
        support = min((float(r.get("strike", 0) or 0) for r in rows), default=None)
    if resistance is None:
        resistance = max((float(r.get("strike", 0) or 0) for r in rows), default=None)

    breakout_up = bool(breakout.get("breakout_up"))
    breakout_down = bool(breakout.get("breakout_down"))
    breakout_trigger = bool(breakout_up or breakout_down)
    weak_atm_oi = float(oi.get("oi_strength", 0.0) or 0.0) < 0.4
    weak_volume = (not bool(volume.get("volume_expansion"))) or (
        ((float(volume.get("rvr", {}).get("ce", 0.0) or 0.0) + float(volume.get("rvr", {}).get("pe", 0.0) or 0.0)) / 2.0)
        < 0.55
    )

    # Reuse normalized upstream engine scores when available.
    oi_change = abs(float(atm_row.get("CE_DeltaOI", 0.0) or 0.0)) + abs(float(atm_row.get("PE_DeltaOI", 0.0) or 0.0))
    oi_avg_change = (
        sum(abs(float(r.get("CE_DeltaOI", 0.0) or 0.0)) + abs(float(r.get("PE_DeltaOI", 0.0) or 0.0)) for r in rows)
        / max(1, len(rows))
    )
    oi_shift_fallback = min(1.0, oi_change / max(1.0, oi_avg_change))
    oi_shift_candidate = oi.get("oi_shift_score")
    oi_shift_score = _clamp01(float(oi_shift_candidate if isinstance(oi_shift_candidate, (int, float)) else oi_shift_fallback))

    atm_volume = float(atm_row.get("CE_Volume", 0.0) or 0.0) + float(atm_row.get("PE_Volume", 0.0) or 0.0)
    avg_volume = (
        sum(float(r.get("CE_Volume", 0.0) or 0.0) + float(r.get("PE_Volume", 0.0) or 0.0) for r in rows)
        / max(1, len(rows))
    )
    volume_ratio = atm_volume / max(1.0, avg_volume)
    current_total_chain_oi = sum(
        max(0.0, float(r.get("CE_OI", r.get("oi_ce", 0.0)) or 0.0))
        + max(0.0, float(r.get("PE_OI", r.get("oi_pe", 0.0)) or 0.0))
        for r in rows
    )
    volume_score_fallback = min(1.0, volume_ratio / 2.0)
    volume_score_candidate = volume.get("volume_expansion_score")
    volume_expansion_score = _clamp01(
        float(volume_score_candidate if isinstance(volume_score_candidate, (int, float)) else volume_score_fallback)
    )

    threshold_points = max(1.0, float(breakout.get("threshold_points", 0.0) or 0.0))
    if breakout_up and resistance is not None and spot is not None:
        breakout_strength = min(1.0, max(0.0, (float(spot) - float(resistance)) / threshold_points))
    elif breakout_down and support is not None and spot is not None:
        breakout_strength = min(1.0, max(0.0, (float(support) - float(spot)) / threshold_points))
    else:
        breakout_strength = 0.0

    observations = _build_spot_observations(
        previous_state,
        float(spot) if isinstance(spot, (int, float)) else None,
        ts,
        window_seconds=120,
    )
    if breakout_up and resistance is not None:
        reference_level = float(resistance)
        mode = "above"
        direction = "up"
    elif breakout_down and support is not None:
        reference_level = float(support)
        mode = "below"
        direction = "down"
    else:
        # No active breakout: use nearest structural level so hold-time/wick still has variance.
        ref_support = float(support) if isinstance(support, (int, float)) else None
        ref_resistance = float(resistance) if isinstance(resistance, (int, float)) else None
        if isinstance(spot, (int, float)) and ref_support is not None and ref_resistance is not None:
            dist_sup = abs(float(spot) - ref_support)
            dist_res = abs(float(spot) - ref_resistance)
            if dist_sup <= dist_res:
                reference_level = ref_support
                mode = "below"
                direction = "down"
            else:
                reference_level = ref_resistance
                mode = "above"
                direction = "up"
        elif ref_resistance is not None:
            reference_level = ref_resistance
            mode = "above"
            direction = "up"
        elif ref_support is not None:
            reference_level = ref_support
            mode = "below"
            direction = "down"
        else:
            reference_level = None
            mode = "above"
            direction = "up"

    if reference_level is not None:
        time_ratio = _time_ratio(observations, reference_level, mode=mode)
        wick_score = _rejection_wick_score(observations, reference_level, direction=direction)
        multi_bar_wick = _multi_bar_wick_score(observations, reference_level, direction=direction)
        pullback_depth = _pullback_depth_ratio(observations, reference_level, direction=direction)
    else:
        time_ratio = 0.0
        wick_score = 0.0
        multi_bar_wick = 0.0
        pullback_depth = 0.0

    # Blend multi-bar wick into single-bar wick score (takes higher of the two).
    effective_wick_score = max(wick_score, multi_bar_wick * 0.85)
    spot_sample_count = len(observations)
    if observations:
        observation_window_seconds = int(max(0.0, float(observations[-1]["ts"]) - float(observations[0]["ts"])))
    else:
        observation_window_seconds = 0
    warmup_active = not (observation_window_seconds >= 60 or spot_sample_count >= 8)
    volatility_factor = min(1.0, max(0.0, abs(float(breakout.get("atr_threshold", threshold_points)) - 1.0) / 10.0))

    is_trap = bool(breakout_trigger and weak_atm_oi and weak_volume and (not in_open_window))
    breakout_level = float(resistance) if breakout_up and resistance is not None else float(support) if breakout_down and support is not None else None
    trap_v2 = trap_engine_v2(
        breakout_strength=float(breakout_strength),
        atm_participation_score=float(volume.get("atm_participation", 0.0) or 0.0),
        oi_shift_score=float(oi_shift_score),
        volume_expansion_score=float(volume_expansion_score),
        rejection_wick_score=float(effective_wick_score),
        time_above_level_ratio=float(time_ratio),
        volatility_factor=float(volatility_factor),
        current_price=float(spot) if isinstance(spot, (int, float)) else None,
        breakout_level=breakout_level,
        atr=float(breakout.get("atr_threshold", threshold_points) or threshold_points),
        volume_after_break=float(atm_volume),
        breakout_volume=float(avg_volume),
        warmup_active=warmup_active,
    )
    trap_raw = float(trap_v2.get("trap_raw", 0.0) or 0.0)

    # Deep pullback (> 70%) after a breakout is strong evidence of a trap.
    pullback_boost = 0.0
    if pullback_depth > 0.70 and breakout_trigger:
        pullback_boost = (pullback_depth - 0.70) * 0.30  # max +0.09 at full pullback
        trap_raw = _clamp01(trap_raw + pullback_boost)

    # E2: OI-price matrix computed BEFORE smoothing so its boost is applied
    # to trap_raw rather than compounding on top of the is_trap multiplier.
    resolved_prev_spot = prev_spot
    if resolved_prev_spot is None and isinstance(previous_state, dict):
        resolved_prev_spot = float(previous_state.get("spot", 0.0) or 0.0) if previous_state.get("spot") is not None else None
    resolved_prev_oi_total = prev_oi_total
    if resolved_prev_oi_total is None and isinstance(previous_state, dict):
        prior_oi = previous_state.get("total_chain_oi")
        resolved_prev_oi_total = float(prior_oi) if isinstance(prior_oi, (int, float)) else None

    if resolved_prev_spot is None or resolved_prev_oi_total is None:
        oi_matrix_result = {
            "oi_trap_signal": "NEUTRAL",
            "oi_trap_confidence": "Low",
            "oi_trap_reason": "Insufficient prior cycle context for OI matrix.",
            "breach_level": None,
            "breach_oi_confirming": True,
            "oi_price_divergence": False,
            "signal": "NEUTRAL",
            "strength": "Low",
            "boost_pts": 0.0,
        }
        oi_boost_frac = 0.0
    else:
        if isinstance(spot, (int, float)) and float(spot) > float(resolved_prev_spot) + 10.0:
            price_direction = "up"
        elif isinstance(spot, (int, float)) and float(spot) < float(resolved_prev_spot) - 10.0:
            price_direction = "down"
        else:
            price_direction = "flat"

        if current_total_chain_oi > float(resolved_prev_oi_total) * 1.005:
            oi_direction = "rising"
        elif current_total_chain_oi < float(resolved_prev_oi_total) * 0.995:
            oi_direction = "falling"
        else:
            oi_direction = "flat"

        if volume_ratio > 1.3:
            volume_category = "high"
        elif volume_ratio < 0.7:
            volume_category = "low"
        else:
            volume_category = "normal"

        resolved_strike_gap = int(strike_gap or features.get("strike_gap") or 50)
        oi_matrix_result = _compute_oi_matrix_trap(
            price_direction=price_direction,
            oi_direction=oi_direction,
            volume_category=volume_category,
            spot=float(spot) if isinstance(spot, (int, float)) else 0.0,
            support=float(support) if isinstance(support, (int, float)) else 0.0,
            resistance=float(resistance) if isinstance(resistance, (int, float)) else 0.0,
            strike_gap=max(1, resolved_strike_gap),
            liquidity_map=liquidity_map if isinstance(liquidity_map, list) else [],
            prev_spot=resolved_prev_spot,
            prev_oi_total=resolved_prev_oi_total,
            oi_velocity_score=float(oi.get("oi_velocity_score", 0.0) or 0.0),
        )
        oi_boost_frac = float(oi_matrix_result.get("boost_pts", 0.0)) / 100.0

    # Apply OI boost to raw BEFORE smoothing — prevents compounding with multiplier.
    trap_raw_pre_oi = trap_raw
    trap_raw_boosted = _clamp01(trap_raw + oi_boost_frac)

    prev_trap_smoothed = trap_raw_boosted
    if isinstance(previous_state, dict):
        prev_trap_smoothed = float(
            previous_state.get(
                "trap_smoothed_prev",
                previous_state.get("trap_smoothed", previous_state.get("trap_raw_prev", trap_raw_boosted)),
            )
            or trap_raw_boosted
        )
    prev_trap_smoothed = _clamp01(prev_trap_smoothed)

    # E3: Asymmetric smoothing — react faster to rising trap, decay slower on falling.
    if trap_raw_boosted > prev_trap_smoothed:
        trap_smoothed = _clamp01(0.6 * prev_trap_smoothed + 0.4 * trap_raw_boosted)
    else:
        trap_smoothed = _clamp01(0.75 * prev_trap_smoothed + 0.25 * trap_raw_boosted)

    trap_risk_multiplier = 1.25 if is_trap else (1.10 if breakout_trigger and (weak_atm_oi or weak_volume) else 1.0)
    trap_trend_adjustment_applied = trap_risk_multiplier > 1.0
    trap_risk = int(round(min(95.0, trap_smoothed * 100.0 * trap_risk_multiplier)))
    trap_after_multiplier_pct = float(min(95.0, trap_smoothed * 100.0 * trap_risk_multiplier))

    # OI boost is now pre-smoothing; no additive adjustment to trap_risk here.
    trap_after_matrix_pct = trap_after_multiplier_pct
    trap_final_capped = bool(trap_after_matrix_pct > 95.0)

    atm_row_data = features.get("atm_row") or {}
    atm_ce_ltp = float(atm_row_data.get("CE_LastPrice") or 0.0)
    atm_pe_ltp = float(atm_row_data.get("PE_LastPrice") or 0.0)
    band_width_est = max(1.0, float(resistance or 0) - float(support or 0)) if resistance and support else max(1.0, threshold_points * 4)
    iv_rv = estimate_iv_realized_ratio(
        atm_ce_ltp=atm_ce_ltp,
        atm_pe_ltp=atm_pe_ltp,
        band_width=band_width_est,
        atr=float(breakout.get("atr_threshold", threshold_points) or threshold_points),
    )

    if in_open_window:
        trap_type = None
        trap_message = "Trap filter inactive during opening 5 minutes."
    elif is_trap:
        trap_type = "Breakout Failure"
        trap_message = "Breakout lacks OI/volume support; reversal risk elevated."
    elif breakout_trigger:
        trap_type = None
        trap_message = "Breakout conditions not fully weak; trap risk moderate."
    else:
        trap_type = None
        trap_message = "No active trap setup."

    trap_direction = "upside" if direction == "up" else "downside"
    resolved_trap_type = str(trap_type or trap_v2.get("trap_type") or "")
    # When smoothed trap_risk is elevated but no type was resolved (e.g. no active
    # breakout but prior high-trap state carried forward), supply a contextual label
    # so the UI doesn't render an empty badge at meaningful risk levels.
    if not resolved_trap_type and trap_risk >= 45:
        resolved_trap_type = "False-Break Risk" if trap_direction == "upside" else "Breakdown Risk"

    absorption_result = _compute_absorption_signal(
        spot=float(spot) if isinstance(spot, (int, float)) else None,
        support=float(support) if isinstance(support, (int, float)) else None,
        resistance=float(resistance) if isinstance(resistance, (int, float)) else None,
        strike_gap=int(strike_gap or features.get("strike_gap") or 50),
        liquidity_map=liquidity_map if isinstance(liquidity_map, list) else [],
        trap_probability=float(trap_smoothed * 100.0),
        observations=observations,
    )

    return {
        "is_trap": is_trap,
        "trap_probability_pct": int(trap_risk),
        "trap_risk": int(trap_risk),
        "trap_raw": round(trap_raw, 4),
        "trap_smoothed": round(trap_smoothed, 4),
        "trap_smoothed_prev": round(trap_smoothed, 4),
        "trap_type": resolved_trap_type,
        "trap_direction": trap_direction,
        "trap_message": trap_message,
        "show_affected_level": bool(resolved_trap_type),
        "trap_level": trap_v2.get("trap_level"),
        "trap_affected_level": reference_level,
        "breakout_strength": round(float(breakout_strength), 4),
        "rejection_wick_score": round(float(effective_wick_score), 4),
        "single_bar_wick_score": round(float(wick_score), 4),
        "multi_bar_wick_score": round(float(multi_bar_wick), 4),
        "pullback_depth_ratio": round(float(pullback_depth), 4),
        "rejection_wick_status": "provisional" if warmup_active else "final",
        "time_above_level_ratio": round(float(time_ratio), 4),
        "time_above_level_status": "provisional" if warmup_active else "final",
        "oi_shift_score": round(float(oi_shift_score), 4),
        "volume_expansion_score": round(float(volume_expansion_score), 4),
        "volatility_factor": round(float(volatility_factor), 4),
        "absorption_score": round(float(trap_v2.get("absorption_score", 0.0) or 0.0), 4),
        "spot_observations": observations,
        "warmup_active": bool(warmup_active),
        "spot_sample_count": int(spot_sample_count),
        "observation_window_seconds": int(observation_window_seconds),
        "no_breakout_validity_floor_applied": bool(trap_v2.get("no_breakout_validity_floor_applied", False)),
        "trap_trend_adjustment_applied": bool(trap_trend_adjustment_applied),
        "weight_distribution": trap_v2.get("weight_distribution", {}),
        "iv_realized_ratio": iv_rv.get("iv_realized_ratio"),
        "iv_state": iv_rv.get("iv_state"),
        "straddle_price": iv_rv.get("straddle_price"),
        "oi_trap_signal": oi_matrix_result.get("oi_trap_signal"),
        "oi_trap_confidence": oi_matrix_result.get("oi_trap_confidence"),
        "oi_trap_reason": oi_matrix_result.get("oi_trap_reason"),
        "breach_level": oi_matrix_result.get("breach_level"),
        "breach_oi_confirming": oi_matrix_result.get("breach_oi_confirming"),
        "oi_price_divergence": oi_matrix_result.get("oi_price_divergence"),
        "absorption_signal": absorption_result.get("absorption_signal"),
        "absorption_strength": absorption_result.get("absorption_strength"),
        "absorption_reason": absorption_result.get("absorption_reason"),
        "absorption_level": absorption_result.get("absorption_level"),
        "absorption_confirmed": bool(absorption_result.get("absorption_confirmed")),
        "support_absorption_strength": absorption_result.get("support_absorption_strength"),
        "resistance_absorption_strength": absorption_result.get("resistance_absorption_strength"),
        "total_chain_oi": round(float(current_total_chain_oi), 2),
        # Read-only telemetry decomposition (Patch 14, updated E2/E3)
        # Stage order: raw → oi_boost (pre-smooth) → smoothed → multiplier → final
        "trap_telemetry": {
            "trap_raw_pre_oi": round(float(trap_raw_pre_oi), 4),
            "trap_raw_post_oi": round(float(trap_raw_boosted), 4),
            "trap_smoothed": round(float(trap_smoothed), 4),
            "pullback_boost_applied": round(float(pullback_boost), 4),
            "pullback_depth": round(float(pullback_depth or 0.0), 4),
            "is_trap_flag": bool(is_trap),
            "multiplier_applied": float(trap_risk_multiplier),
            "trap_after_multiplier": round(float(trap_after_multiplier_pct) / 100.0, 4),
            "trap_after_multiplier_pct": round(float(trap_after_multiplier_pct), 2),
            "oi_matrix_signal": str(oi_matrix_result.get("signal") or oi_matrix_result.get("oi_trap_signal") or "NEUTRAL"),
            "oi_matrix_strength": str(oi_matrix_result.get("strength") or oi_matrix_result.get("oi_trap_confidence") or "Low"),
            "oi_matrix_boost_pts": round(float(oi_boost_frac) * 100.0, 2),
            "trap_after_matrix": round(float(trap_after_matrix_pct) / 100.0, 4),
            "trap_after_matrix_pct": round(float(trap_after_matrix_pct), 2),
            "trap_final_capped": bool(trap_final_capped),
        },
    }
