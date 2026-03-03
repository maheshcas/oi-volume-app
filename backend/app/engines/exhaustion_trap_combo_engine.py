from __future__ import annotations

from typing import Any


def detect_exhaustion_trap_combo(
    *,
    trap_risk: float | int,
    momentum_exhaustion: bool,
    confidence: float | int,
    volatility_state: str,
) -> dict[str, Any]:
    combo_alert = False
    combo_severity: str | None = None

    if (
        float(trap_risk) > 40
        and bool(momentum_exhaustion) is True
        and float(confidence) < 65
        and str(volatility_state) != "Expanding"
    ):
        combo_alert = True
        combo_severity = "High Reversal Risk"

    return {
        "combo_alert": combo_alert,
        "combo_severity": combo_severity,
    }

