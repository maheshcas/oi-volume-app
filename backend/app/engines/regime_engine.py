from typing import Any


def classify_session_regime(oi: dict[str, Any], volume: dict[str, Any], breakout: dict[str, Any], trap: dict[str, Any]) -> str:
    if trap.get("is_trap"):
        return "Trap Risk"
    if breakout.get("breakout_up"):
        return "Trend Day"
    if breakout.get("breakout_down"):
        return "Breakdown"
    buildup = oi.get("buildup_type", "")
    if "Unwinding" in buildup:
        return "Short Covering"
    if volume.get("volume_expansion") and oi.get("alignment") in ("bullish", "bearish"):
        return "Trend Day"
    return "Range Day"


def run_regime_engine(oi: dict[str, Any], volume: dict[str, Any], breakout: dict[str, Any], trap: dict[str, Any]) -> dict[str, Any]:
    regime = classify_session_regime(oi, volume, breakout, trap)
    return {"regime": regime}
