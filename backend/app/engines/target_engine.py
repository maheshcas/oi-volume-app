from typing import Any


def calculate_directional_targets(
    support_level: float | None,
    resistance_level: float | None,
    weighted_score: float,
    atr_value: float,
    regime_type: str | None = None,
) -> dict[str, Any]:
    """
    Directional target model.
    - No mixed directional targets.
    - Uses weighted_score sign as the single direction authority.
    """
    _ = regime_type  # reserved for future regime-aware scaling
    if support_level is None or resistance_level is None:
        return {"direction": "neutral", "target_1": None, "target_2": None}

    move = max(1.0, float(atr_value or 0.0))
    score = float(weighted_score or 0.0)

    if score > 0:
        direction = "bull"
        target_1 = float(resistance_level) + (move * 0.6)
        target_2 = float(resistance_level) + (move * 1.2)
    elif score < 0:
        direction = "bear"
        target_1 = float(support_level) - (move * 0.6)
        target_2 = float(support_level) - (move * 1.2)
    else:
        direction = "neutral"
        target_1 = float(resistance_level)
        target_2 = float(support_level)

    return {
        "direction": direction,
        "target_1": round(target_1, 2),
        "target_2": round(target_2, 2),
    }


def run_target_engine(
    features: dict[str, Any], sr: dict[str, Any], breakout: dict[str, Any], oi: dict[str, Any], trap: dict[str, Any], volume: dict[str, Any]
) -> dict[str, Any]:
    support = sr.get("support", {}).get("strike")
    resistance = sr.get("resistance", {}).get("strike")
    regime_type = str(features.get("regime_type") or "")

    # Weighted score approximation for target direction.
    # Positive: bullish, Negative: bearish.
    oi_alignment = str(oi.get("alignment") or "mixed")
    oi_score = 1.0 if oi_alignment == "bullish" else -1.0 if oi_alignment == "bearish" else 0.0
    breakout_score = 1.0 if breakout.get("breakout_up") else -1.0 if breakout.get("breakout_down") else 0.0
    volume_score = (float(volume.get("rvr", {}).get("pe", 0.0) or 0.0) - float(volume.get("rvr", {}).get("ce", 0.0) or 0.0))
    trap_penalty = min(1.0, max(0.0, float(trap.get("trap_probability_pct", 0) or 0) / 100.0))
    weighted_score = (0.4 * oi_score) + (0.35 * breakout_score) + (0.25 * volume_score) - (0.2 * trap_penalty)

    atr_value = float(features.get("atr_proxy") or features.get("expected_move") or 0.0)
    directional = calculate_directional_targets(
        support_level=support,
        resistance_level=resistance,
        weighted_score=weighted_score,
        atr_value=atr_value,
        regime_type=regime_type,
    )

    t1 = directional.get("target_1")
    t2 = directional.get("target_2")
    return {
        "direction": directional.get("direction"),
        "target_1": t1,
        "target_2": t2,
        "acceleration_zone": f"{round(min(t1, t2), 2)} - {round(max(t1, t2), 2)}" if t1 is not None and t2 is not None else None,
        "weighted_score": round(float(weighted_score), 4),
        "atr_value": round(float(max(1.0, atr_value)), 2),
    }
