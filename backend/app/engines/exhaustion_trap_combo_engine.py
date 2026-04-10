from __future__ import annotations

from typing import Any


def detect_exhaustion_trap_combo(
    *,
    trap_risk: float | int,
    momentum_exhaustion: bool,
    confidence: float | int,
    volatility_state: str,
) -> dict[str, Any]:
    trap = float(trap_risk)
    conf = float(confidence)
    exhaustion = bool(momentum_exhaustion)
    vol_expanding = str(volatility_state).strip() == "Expanding"

    # Score each condition individually.
    conditions_met: list[str] = []
    if trap > 40:
        conditions_met.append("trap_risk")
    if exhaustion:
        conditions_met.append("momentum_exhaustion")
    if conf < 65:
        conditions_met.append("low_confidence")
    if not vol_expanding:
        conditions_met.append("volatility_not_expanding")

    count = len(conditions_met)

    if count < 2:
        # Need at least 2 conditions before issuing any alert.
        return {
            "combo_alert": False,
            "combo_severity": None,
            "conditions_met": conditions_met,
            "conditions_count": count,
        }

    combo_alert = True

    # Severity tiers based on count and which high-impact conditions fired.
    core_conditions = {"trap_risk", "momentum_exhaustion"}
    core_count = sum(1 for c in conditions_met if c in core_conditions)

    if count == 4 or (core_count == 2 and trap > 60):
        combo_severity = "High Reversal Risk"
    elif core_count == 2 or (count >= 3 and trap > 50):
        combo_severity = "Moderate Reversal Risk"
    else:
        combo_severity = "Low Reversal Risk"

    return {
        "combo_alert": combo_alert,
        "combo_severity": combo_severity,
        "conditions_met": conditions_met,
        "conditions_count": count,
    }

