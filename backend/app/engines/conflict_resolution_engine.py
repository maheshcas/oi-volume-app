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
    support_zone_pressure: float = 0.0,
    resistance_zone_pressure: float = 0.0,
    material_breach: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Conflict resolver layer used before final decision output.
    Inputs:
      - confidence, trap_probability: 0-100 scale
      - breakout_strength, support_strength, resistance_strength, alignment_score: 0-1 scale

    Internally all thresholds are applied on a unified 0-1 scale to prevent
    scale-mixing bugs (e.g. confidence=35 being compared against alignment=0.6).
    """
    # Accept both scales: if confidence > 1.0 assume it's on 0-100 scale, normalise to 0-1.
    raw_conf = float(confidence)
    conf_01 = _clamp(raw_conf / 100.0 if raw_conf > 1.0 else raw_conf, 0.0, 1.0)

    raw_trap = float(trap_probability)
    trap_01 = _clamp(raw_trap / 100.0 if raw_trap > 1.0 else raw_trap, 0.0, 1.0)

    breakout_strength = _clamp(breakout_strength, 0.0, 1.0)
    support_strength = _clamp(support_strength, 0.0, 1.0)
    resistance_strength = _clamp(resistance_strength, 0.0, 1.0)
    alignment_score = _clamp(alignment_score, 0.0, 1.0)

    raw_sup_pressure = float(support_zone_pressure)
    sup_pressure_01 = _clamp(raw_sup_pressure / 100.0 if raw_sup_pressure > 1.0 else raw_sup_pressure, 0.0, 1.0)
    raw_res_pressure = float(resistance_zone_pressure)
    res_pressure_01 = _clamp(raw_res_pressure / 100.0 if raw_res_pressure > 1.0 else raw_res_pressure, 0.0, 1.0)

    # Keep 0-100 values available for callers that expect them in the response.
    confidence = conf_01 * 100.0
    trap_probability = trap_01 * 100.0
    support_zone_pressure = sup_pressure_01 * 100.0
    resistance_zone_pressure = res_pressure_01 * 100.0

    breach = material_breach or {}
    support_broken = bool(breach.get("support_broken"))
    resistance_broken = bool(breach.get("resistance_broken"))
    has_material_breach = support_broken or resistance_broken
    # All trap comparisons use the unified 0-1 scale (trap_01).
    effective_trap_01 = trap_01 * 0.6 if has_material_breach else trap_01
    adjusted_breakout_strength = breakout_strength
    if has_material_breach and max(sup_pressure_01, res_pressure_01) > 0.50:
        adjusted_breakout_strength = _clamp(breakout_strength * 1.2, 0.0, 1.0)

    normalized_regime = str(regime or "").strip().lower()
    suppressed_signals: list[str] = []
    conflict_flags: list[str] = []
    market_state = "Balanced"
    projection = "No Confirmed Breakout"

    # Rule 1 — Low confidence suppression (0-1 scale: 0.25 = 25%).
    if conf_01 < 0.25:
        if "breakout" not in suppressed_signals:
            suppressed_signals.append("breakout")
        projection = "Range Compression"
        conflict_flags.append("low_confidence_suppression")

    # Rule 2 — Range regime filter.
    if not has_material_breach and (normalized_regime == "range" or "range" in normalized_regime):
        if "breakout" not in suppressed_signals:
            suppressed_signals.append("breakout")
        projection = "No Confirmed Breakout"
        market_state = "Range"
        conflict_flags.append("range_regime_filter")
    elif has_material_breach and (normalized_regime == "range" or "range" in normalized_regime):
        conflict_flags.append("range_regime_relaxed_on_breach")

    # Rule 3 — High trap risk (0-1 scale: 0.60 = 60%).
    if effective_trap_01 > 0.60:
        if "breakout" not in suppressed_signals:
            suppressed_signals.append("breakout")
        market_state = "High Trap Risk"
        conflict_flags.append("high_trap_risk_filter" if not has_material_breach else "high_trap_risk_relaxed_on_breach")

    # Rule 4 — Strong support + resistance compression.
    if support_strength > 0.6 and resistance_strength > 0.6:
        market_state = "Compression"
        if "expansion_targets" not in suppressed_signals:
            suppressed_signals.append("expansion_targets")
        conflict_flags.append("dual_side_strength_compression")

    # Rule 5 — Weak alignment suppression.
    if alignment_score < 0.55:
        if "breakout" not in suppressed_signals:
            suppressed_signals.append("breakout")
        conflict_flags.append("weak_alignment_suppression")

    # Rule 6 — Final projection logic (all thresholds on 0-1 scale).
    if (
        adjusted_breakout_strength > 0.65
        and effective_trap_01 < 0.40
        and alignment_score > 0.60
        and conf_01 > 0.35            # was: confidence > 35 (100-scale) = 0.35 (0-1 scale)
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
        "adjusted_breakout_strength": round(adjusted_breakout_strength, 4),
        "effective_trap_probability": round(effective_trap_01 * 100.0, 2),
    }
