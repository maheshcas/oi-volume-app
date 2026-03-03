from __future__ import annotations

from copy import deepcopy
from typing import Any


def prioritize_signals(
    *,
    signals: list[dict[str, Any]],
    confidence: float | int,
    regime: str,
    projection: str | None,
    expiry_mode: bool,
    session_phase: str,
    reversal_probability: float | int,
) -> dict[str, Any]:
    prioritized: list[dict[str, Any]] = []
    suppression_reason_map: dict[str, str] = {}
    conf = float(confidence)
    rev = float(reversal_probability)
    reg = str(regime)
    proj = str(projection or "")
    phase = str(session_phase)

    for raw in signals:
        signal = deepcopy(raw)
        base = float(signal.get("base_priority", 0) or 0)
        stype = str(signal.get("type", "")).lower()
        msg = str(signal.get("message", "")).strip()
        signal_key = f"{stype}:{msg}" if msg else stype or "unknown"
        priority = base
        reasons: list[str] = []

        if conf < 35 and stype == "breakout":
            priority -= 40
            reasons.append("low_confidence_breakout_filter")

        if reg == "Range" and stype == "breakout":
            priority -= 20
            reasons.append("range_regime_breakout_filter")
            if proj.strip().lower() in {"no breakout", "range"}:
                priority -= 25
                reasons.append("range_no_breakout_downgrade")

        if expiry_mode and phase == "Midday Compression":
            priority -= 15
            reasons.append("expiry_midday_filter")

        if rev > 70 and stype == "trend_continuation":
            priority -= 30
            reasons.append("high_reversal_prob_filter")

        signal["adjusted_priority"] = max(int(round(priority)), 0)
        signal["_signal_key"] = signal_key
        signal["_reasons"] = reasons
        prioritized.append(signal)

    prioritized.sort(key=lambda x: x.get("adjusted_priority", 0), reverse=True)
    top3 = prioritized[:3]
    selected_keys = {str(s.get("_signal_key", "")) for s in top3}
    for s in prioritized:
        key = str(s.get("_signal_key", ""))
        if not key:
            continue
        if key in selected_keys and int(s.get("adjusted_priority", 0) or 0) > 0:
            continue
        reasons = list(s.get("_reasons", []))
        if int(s.get("adjusted_priority", 0) or 0) <= 0:
            reasons.append("priority_zero")
        if key not in selected_keys:
            reasons.append("top3_cutoff")
        suppression_reason_map[key] = "|".join(dict.fromkeys(reasons)) if reasons else "lower_priority"

    cleaned_top3: list[dict[str, Any]] = []
    for s in top3:
        x = deepcopy(s)
        x.pop("_signal_key", None)
        x.pop("_reasons", None)
        cleaned_top3.append(x)

    return {
        "prioritized_signals": cleaned_top3,
        "suppression_reason_map": suppression_reason_map,
    }
