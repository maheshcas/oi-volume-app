from __future__ import annotations


# Severity ordering for shift causes — higher value = more dominant.
# When multiple shifts fire simultaneously, the highest-severity cause is reported
# as the primary and weaker ones are suppressed to prevent noise.
_SHIFT_SEVERITY: dict[str, int] = {
    "Directional Bias Flip": 4,   # highest: price direction reversed
    "Regime Transition": 3,        # structural: market character changed
    "Volatility Expansion": 2,     # medium: risk environment changed
    "Structure Realignment": 1,    # lowest: alignment drift
}


def _sign(value: float) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def detect_regime_shift(
    *,
    previous_smoothed_score: float,
    current_smoothed_score: float,
    previous_regime: str,
    current_regime: str,
    previous_alignment: float,
    current_alignment: float,
    previous_atr_ratio: float,
    current_atr_ratio: float,
) -> dict[str, object]:
    """
    Detect all active regime shift causes, rank by severity, and return the
    dominant cause as the primary shift reason.  Secondary causes are also
    included so callers can assess compounding risk without being flooded.
    """
    active_shifts: list[dict[str, object]] = []

    if _sign(previous_smoothed_score) != _sign(current_smoothed_score):
        delta = abs(current_smoothed_score - previous_smoothed_score)
        if delta > 0.25:
            active_shifts.append({
                "reason": "Directional Bias Flip",
                "severity": _SHIFT_SEVERITY["Directional Bias Flip"],
                "magnitude": round(delta, 4),
            })

    if previous_regime != current_regime:
        active_shifts.append({
            "reason": "Regime Transition",
            "severity": _SHIFT_SEVERITY["Regime Transition"],
            "magnitude": None,
            "from_regime": previous_regime,
            "to_regime": current_regime,
        })

    atr_delta = abs(current_atr_ratio - previous_atr_ratio)
    if atr_delta > 0.2:
        active_shifts.append({
            "reason": "Volatility Expansion",
            "severity": _SHIFT_SEVERITY["Volatility Expansion"],
            "magnitude": round(atr_delta, 4),
        })

    alignment_delta = abs(current_alignment - previous_alignment)
    if alignment_delta > 0.3:
        active_shifts.append({
            "reason": "Structure Realignment",
            "severity": _SHIFT_SEVERITY["Structure Realignment"],
            "magnitude": round(alignment_delta, 4),
        })

    if not active_shifts:
        return {
            "regime_shift_alert": False,
            "regime_shift_reason": None,
            "regime_shift_severity": None,
            "all_shift_causes": [],
        }

    # Sort descending by severity; primary = highest severity cause.
    active_shifts.sort(key=lambda s: int(s["severity"]), reverse=True)  # type: ignore[arg-type]
    primary = active_shifts[0]
    secondary = active_shifts[1:] if len(active_shifts) > 1 else []

    severity_label: str
    sev = int(primary["severity"])  # type: ignore[arg-type]
    if sev >= 4:
        severity_label = "Critical"
    elif sev == 3:
        severity_label = "High"
    elif sev == 2:
        severity_label = "Moderate"
    else:
        severity_label = "Low"

    return {
        "regime_shift_alert": True,
        "regime_shift_reason": primary["reason"],
        "regime_shift_severity": severity_label,
        "all_shift_causes": [s["reason"] for s in active_shifts],
        "shift_details": active_shifts,
        "secondary_shifts": [s["reason"] for s in secondary],
    }

