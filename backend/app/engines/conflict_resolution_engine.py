from __future__ import annotations

from typing import Any


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def resolve_conflicts(
    regime: str,
    confidence: float,
    alignment_ratio: float,
    trap_risk: float,
    support_strength: float,
    resistance_strength: float,
    projection: str,
) -> dict[str, Any]:
    """
    Conflict resolution layer for projection consistency.
    confidence and alignment_ratio expected in [0, 1].
    """
    confidence = _clamp(confidence, 0.0, 1.0)
    alignment_ratio = _clamp(alignment_ratio, 0.0, 1.0)
    trap_risk = _clamp(trap_risk, 0.0, 1.0)
    support_strength = _clamp(support_strength, 0.0, 1.0)
    resistance_strength = _clamp(resistance_strength, 0.0, 1.0)

    normalized_regime = str(regime or "").strip().lower()
    resolved_projection = str(projection or "Range")
    reason_flags: list[str] = []

    if confidence < 0.25:
        resolved_projection = "Range"
        reason_flags.append("low_confidence_range_override")

    if normalized_regime == "range" or "range" in normalized_regime:
        resolved_projection = "Range"
        reason_flags.append("range_regime_override")

    if support_strength > 0.7 and resistance_strength > 0.7:
        resolved_projection = "Compression"
        reason_flags.append("compression_detected")

    projection_strength = "High" if confidence >= 0.7 and alignment_ratio >= 0.7 else "Medium"
    if confidence < 0.4 or alignment_ratio < 0.4:
        projection_strength = "Low"

    if trap_risk > 0.6:
        if projection_strength == "High":
            projection_strength = "Medium"
        elif projection_strength == "Medium":
            projection_strength = "Low"
        reason_flags.append("trap_risk_downgrade")

    return {
        "projection": resolved_projection,
        "projection_strength": projection_strength,
        "reason_flags": reason_flags,
        "alignment_ratio": round(alignment_ratio, 4),
    }


def run_conflict_resolver(
    *,
    regime: str,
    confidence: float,
    breakout_strength: float,
    trap_probability: float,
    support_strength: float,
    resistance_strength: float,
    alignment_score: float,
) -> dict[str, Any]:
    """
    Conflict resolver layer used before final decision output.
    Inputs:
      - confidence, trap_probability: 0-100
      - breakout_strength, support_strength, resistance_strength, alignment_score: 0-1
    """
    confidence = _clamp(confidence, 0.0, 100.0)
    breakout_strength = _clamp(breakout_strength, 0.0, 1.0)
    trap_probability = _clamp(trap_probability, 0.0, 100.0)
    support_strength = _clamp(support_strength, 0.0, 1.0)
    resistance_strength = _clamp(resistance_strength, 0.0, 1.0)
    alignment_score = _clamp(alignment_score, 0.0, 1.0)

    normalized_regime = str(regime or "").strip().lower()
    suppressed_signals: list[str] = []
    conflict_flags: list[str] = []
    market_state = "Balanced"
    projection = "No Confirmed Breakout"

    # Rule 1 - Low confidence suppression
    if confidence < 25:
        if "breakout" not in suppressed_signals:
            suppressed_signals.append("breakout")
        projection = "Range Compression"
        conflict_flags.append("low_confidence_suppression")

    # Rule 2 - Range regime filter
    if normalized_regime == "range" or "range" in normalized_regime:
        if "breakout" not in suppressed_signals:
            suppressed_signals.append("breakout")
        projection = "No Confirmed Breakout"
        market_state = "Range"
        conflict_flags.append("range_regime_filter")

    # Rule 3 - High trap risk
    if trap_probability > 60:
        if "breakout" not in suppressed_signals:
            suppressed_signals.append("breakout")
        market_state = "High Trap Risk"
        conflict_flags.append("high_trap_risk_filter")

    # Rule 4 - Strong support + resistance compression
    if support_strength > 0.6 and resistance_strength > 0.6:
        market_state = "Compression"
        if "expansion_targets" not in suppressed_signals:
            suppressed_signals.append("expansion_targets")
        conflict_flags.append("dual_side_strength_compression")

    # Rule 5 - Weak alignment suppression
    if alignment_score < 0.55:
        if "breakout" not in suppressed_signals:
            suppressed_signals.append("breakout")
        conflict_flags.append("weak_alignment_suppression")

    # Rule 6 - Final projection logic
    if (
        breakout_strength > 0.65
        and trap_probability < 40
        and alignment_score > 0.6
        and confidence > 35
        and "breakout" not in suppressed_signals
    ):
        projection = "Breakout Valid"
        if market_state == "Balanced":
            market_state = "Directional"
    elif projection not in ("Range Compression", "No Confirmed Breakout"):
        projection = "No Confirmed Breakout"

    return {
        "market_state": market_state,
        "projection": projection,
        "suppressed_signals": suppressed_signals,
        "conflict_flags": conflict_flags,
    }
