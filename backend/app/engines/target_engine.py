from typing import Any


def _volatility_multiplier(volume_expansion: bool, trap_risk_pct: int) -> float:
    mult = 1.2 if volume_expansion else 0.9
    if trap_risk_pct >= 60:
        mult *= 0.8
    return mult


def calculate_smart_targets(
    spot: float | None,
    support: float | None,
    resistance: float | None,
    strike_gap: float,
    oi_concentration: float,
    breakout: dict[str, Any],
    volume_expansion: bool,
    trap_risk_pct: int,
) -> dict[str, Any]:
    if support is None or resistance is None:
        return {"target_1": None, "target_2": None, "acceleration_zone": None}

    volatility_mult = _volatility_multiplier(volume_expansion, trap_risk_pct)
    oi_mult = 1.0 + max(0.0, oi_concentration - 0.5)
    base_move = max(strike_gap * 2.0, abs(resistance - support) * 0.5)
    move = base_move * oi_mult * volatility_mult

    if breakout.get("breakout_up"):
        t1 = resistance + (0.8 * move)
        t2 = resistance + move
    elif breakout.get("breakout_down"):
        t1 = support - (0.8 * move)
        t2 = support - move
    else:
        center = spot if spot is not None else (support + resistance) / 2
        t1 = center + move * 0.6
        t2 = center - move * 0.6

    return {
        "target_1": round(t1, 2),
        "target_2": round(t2, 2),
        "acceleration_zone": f"{round(min(t1, t2), 2)} - {round(max(t1, t2), 2)}",
        "volatility_multiplier": round(volatility_mult, 3),
    }


def run_target_engine(
    features: dict[str, Any], sr: dict[str, Any], breakout: dict[str, Any], oi: dict[str, Any], trap: dict[str, Any], volume: dict[str, Any]
) -> dict[str, Any]:
    support = sr.get("support", {}).get("strike")
    resistance = sr.get("resistance", {}).get("strike")
    spot = features["meta"].get("spot")
    oi_concentration = max(
        float(oi.get("concentration", {}).get("ce", 0) or 0),
        float(oi.get("concentration", {}).get("pe", 0) or 0),
    )
    return calculate_smart_targets(
        spot=spot,
        support=support,
        resistance=resistance,
        strike_gap=float(features.get("strike_gap") or 50),
        oi_concentration=oi_concentration,
        breakout=breakout,
        volume_expansion=bool(volume.get("volume_expansion")),
        trap_risk_pct=int(trap.get("trap_probability_pct") or 0),
    )
