from __future__ import annotations

from app.engines.strike_intelligence_engine import _compute_max_pain_metrics


def test_max_pain_zero_avg_loss_returns_zero_confidence() -> None:
    # Single strike with all OI concentrated at one level can produce avg_loss=0.
    liquidity_map = [
        {"strike": 24200, "oi_ce": 150000, "oi_pe": 180000},
    ]
    out = _compute_max_pain_metrics(liquidity_map=liquidity_map, spot=24200, strike_gap=50)

    assert out["max_pain_strike"] == 24200
    assert out["max_pain_confidence"] == 0.0
    assert out["max_pain_strength"] == "Weak"


def test_max_pain_two_strike_loop_and_tie_breaker_nearest_spot() -> None:
    # Symmetric two-strike chain creates equal writer loss at both candidates.
    # Tie-break should select candidate nearest to spot.
    liquidity_map = [
        {"strike": 24000, "oi_ce": 1000, "oi_pe": 0},
        {"strike": 24500, "oi_ce": 0, "oi_pe": 1000},
    ]
    out = _compute_max_pain_metrics(liquidity_map=liquidity_map, spot=24180, strike_gap=50)

    # Equal losses at 24000/24500 => choose closest to spot (24000 here).
    assert out["max_pain_strike"] == 24000


def test_max_pain_uses_window_scope_for_candidates_and_is_stable_vs_far_oi() -> None:
    base_liquidity_map = [
        {"strike": 24000, "oi_ce": 5000, "oi_pe": 9000},
        {"strike": 24100, "oi_ce": 7000, "oi_pe": 8000},
        {"strike": 24200, "oi_ce": 12000, "oi_pe": 11000},
        {"strike": 24300, "oi_ce": 9500, "oi_pe": 9000},
        {"strike": 24400, "oi_ce": 13000, "oi_pe": 12000},
    ]
    with_far_otm = [
        *base_liquidity_map,
        # Far-OTM giant OI, outside ±8 gaps (±400 pts for strike_gap=50 from spot=24200).
        {"strike": 26000, "oi_ce": 8_000_000, "oi_pe": 9_000_000},
    ]

    base = _compute_max_pain_metrics(
        liquidity_map=base_liquidity_map,
        spot=24200,
        strike_gap=50,
    )
    noisy = _compute_max_pain_metrics(
        liquidity_map=with_far_otm,
        spot=24200,
        strike_gap=50,
    )

    # Window-scoped computation should be invariant to far-OTM OI.
    assert noisy["max_pain_strike"] == base["max_pain_strike"]
    assert noisy["max_pain_confidence"] == base["max_pain_confidence"]
    assert noisy["max_pain_strength"] == base["max_pain_strength"]

