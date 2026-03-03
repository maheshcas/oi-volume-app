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
