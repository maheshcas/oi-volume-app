from __future__ import annotations

from typing import Any


def generate_intraday_playbook(
    *,
    primary_bias: str,
    regime: str,
    trap_probability: float | int,
    market_structure_score: float | int,
    support_zone: Any,
    resistance_zone: Any,
    expansion_target: float | int | None,
) -> dict[str, Any]:
    strategy = "Wait for clearer structure."

    if regime == "Range":
        strategy = "Fade range extremes."
    if regime == "Trend Developing":
        strategy = "Trade pullbacks in trend direction."
    if float(market_structure_score or 0) > 80:
        strategy = "Momentum breakout trades preferred."
    if float(trap_probability or 0) > 60:
        strategy = "Avoid breakout trades."

    return {
        "bias": str(primary_bias or "Neutral"),
        "regime": str(regime or "Transition"),
        "strategy": strategy,
        "support_zone": support_zone,
        "resistance_zone": resistance_zone,
        "expansion_target": expansion_target,
    }

