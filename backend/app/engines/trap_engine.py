from datetime import datetime, timezone
from typing import Any


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
    _ = level, direction  # level-aware filtering can be layered later if needed.

    upper_wick = max(0.0, high - max(open_price, close))
    lower_wick = max(0.0, min(open_price, close) - low)
    wick_ratio = max(upper_wick, lower_wick) / candle_range
    return max(0.0, min(1.0, wick_ratio * 2.0))


def run_trap_engine(
    features: dict[str, Any],
    breakout: dict[str, Any],
    oi: dict[str, Any],
    volume: dict[str, Any],
    previous_state: dict[str, Any] | None = None,
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
    else:
        time_ratio = 0.0
        wick_score = 0.0
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
        rejection_wick_score=float(wick_score),
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
    prev_trap_raw = trap_raw
    if isinstance(previous_state, dict):
        prev_trap_raw = float(previous_state.get("trap_raw_prev", trap_raw) or trap_raw)
    trap_smoothed = _clamp01((0.7 * prev_trap_raw) + (0.3 * trap_raw))

    trap_risk_multiplier = 1.25 if is_trap else (1.10 if breakout_trigger and (weak_atm_oi or weak_volume) else 1.0)
    trap_risk = int(round(min(95.0, trap_smoothed * 100.0 * trap_risk_multiplier)))

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

    resolved_trap_type = str(trap_type or trap_v2.get("trap_type") or "")
    # When smoothed trap_risk is elevated but no type was resolved (e.g. no active
    # breakout but prior high-trap state carried forward), supply a contextual label
    # so the UI doesn't render an empty badge at meaningful risk levels.
    if not resolved_trap_type and trap_risk >= 45:
        resolved_trap_type = "False-Break Risk" if trap_direction == "upside" else "Breakdown Risk"
    trap_direction = "upside" if direction == "up" else "downside"

    return {
        "is_trap": is_trap,
        "trap_probability_pct": int(trap_risk),
        "trap_risk": int(trap_risk),
        "trap_raw": round(trap_raw, 4),
        "trap_smoothed": round(trap_smoothed, 4),
        "trap_type": resolved_trap_type,
        "trap_direction": trap_direction,
        "trap_message": trap_message,
        "show_affected_level": bool(resolved_trap_type),
        "trap_level": trap_v2.get("trap_level"),
        "trap_affected_level": reference_level,
        "breakout_strength": round(float(breakout_strength), 4),
        "rejection_wick_score": round(float(wick_score), 4),
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
        "weight_distribution": trap_v2.get("weight_distribution", {}),
    }
