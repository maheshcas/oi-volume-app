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
        (0.35 * breakout_strength)
        + (0.25 * atm_participation_score)
        + (0.20 * oi_shift_score)
        + (0.20 * volume_expansion_score)
    )

    # STEP 2 — Trap raw score
    trap_raw = (
        (0.30 * (1 - validity_score))
        + (0.25 * rejection_wick_score)
        + (0.20 * (1 - time_above_level_ratio))
        + (0.15 * (1 - oi_shift_score))
        + (0.10 * volatility_factor)
    )

    if breakout_strength > 0.7 and rejection_wick_score > 0.7 and time_above_level_ratio < 0.3:
        trap_raw += 0.15

    trap_raw = _clamp01(trap_raw)
    trap_probability = int(round(trap_raw * 100))

    # STEP 3 — Classification
    if trap_raw > 0.65:
        trap_level = "High"
    elif trap_raw > 0.45:
        trap_level = "Moderate"
    else:
        trap_level = "Low"

    if rejection_wick_score > 0.7 and time_above_level_ratio < 0.3:
        trap_type = "Liquidity Sweep"
    elif validity_score < 0.45 and time_above_level_ratio < 0.5:
        trap_type = "Breakout Failure"
    elif volume_expansion_score > 0.7 and time_above_level_ratio < 0.4:
        trap_type = "Exhaustion"
    else:
        trap_type = None

    return {
        "trap_probability": trap_probability,
        "trap_level": trap_level,
        "trap_type": trap_type,
        "validity_score": round(validity_score, 4),
        "trap_raw": round(trap_raw, 4),
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


def run_trap_engine(features: dict[str, Any], breakout: dict[str, Any], oi: dict[str, Any], volume: dict[str, Any]) -> dict[str, Any]:
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

    breakout_trigger = bool(breakout.get("breakout_up") or breakout.get("breakout_down"))
    weak_atm_oi = float(oi.get("oi_strength", 0.0) or 0.0) < 0.4
    weak_volume = (not bool(volume.get("volume_expansion"))) or (
        ((float(volume.get("rvr", {}).get("ce", 0.0) or 0.0) + float(volume.get("rvr", {}).get("pe", 0.0) or 0.0)) / 2.0)
        < 0.55
    )

    is_trap = bool(breakout_trigger and weak_atm_oi and weak_volume and (not in_open_window))
    trap_risk = 75 if is_trap else (40 if breakout_trigger and (weak_atm_oi or weak_volume) else 20)

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

    return {
        "is_trap": is_trap,
        "trap_probability_pct": int(trap_risk),
        "trap_risk": int(trap_risk),
        "trap_type": trap_type,
        "trap_message": trap_message,
        "show_affected_level": bool(trap_type is not None),
    }
