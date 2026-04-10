from typing import Any


def atr_based_threshold(atr_value: float, atr_multiplier: float = 1.2) -> float:
    return max(1.0, float(atr_value) * float(atr_multiplier))


def detect_breakout(spot: float | None, support: float | None, resistance: float | None, threshold: float) -> dict[str, Any]:
    if spot is None or support is None or resistance is None:
        return {
            "breakout_up": False,
            "breakout_down": False,
            "threshold_points": threshold,
            "invalid_sr_geometry": False,
        }
    if resistance <= support:
        return {
            "breakout_up": False,
            "breakout_down": False,
            "threshold_points": round(threshold, 2),
            "invalid_sr_geometry": True,
        }
    breakout_up = spot > (resistance + threshold)
    breakout_down = spot < (support - threshold)
    return {
        "breakout_up": breakout_up,
        "breakout_down": breakout_down,
        "threshold_points": round(threshold, 2),
        "invalid_sr_geometry": False,
    }


def run_breakout_engine(features: dict[str, Any], sr: dict[str, Any], atr_multiplier: float = 1.2) -> dict[str, Any]:
    atr_proxy = float(features.get("atr_proxy") or 0.0)
    threshold = atr_based_threshold(atr_proxy, atr_multiplier)
    spot = features["meta"].get("spot")
    support = sr.get("support", {}).get("strike")
    resistance = sr.get("resistance", {}).get("strike")
    out = detect_breakout(spot, support, resistance, threshold)
    out["atr_threshold"] = round(threshold, 2)
    return out
