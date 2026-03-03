from __future__ import annotations

import pytest

from app.engines.arbitration_engine import run_arbitration


def test_trend_regime_weighting() -> None:
    out = run_arbitration(
        oi_score=0.8,
        volume_score=0.4,
        price_score=0.2,
        breakout_score=0.6,
        trap_risk=0.0,
        regime="Trend Day",
        previous_score=0.0,
    )
    assert out["regime_used"] == "Trend"
    assert out["weights"] == {"oi": 0.30, "volume": 0.25, "price": 0.25, "breakout": 0.20}
    assert -1.0 <= out["raw_score"] <= 1.0
    assert -1.0 <= out["smoothed_score"] <= 1.0


def test_range_regime_weighting() -> None:
    out = run_arbitration(
        oi_score=0.5,
        volume_score=0.5,
        price_score=0.5,
        breakout_score=0.5,
        trap_risk=0.0,
        regime="Range Day",
        previous_score=0.0,
    )
    assert out["regime_used"] == "Range"
    assert pytest.approx(1.0, abs=1e-6) == sum(out["weights"].values())


def test_trap_penalty_reduces_score() -> None:
    args = dict(
        oi_score=0.6,
        volume_score=0.6,
        price_score=0.6,
        breakout_score=0.6,
        regime="Trend",
        previous_score=0.0,
    )
    no_trap = run_arbitration(trap_risk=0.0, **args)
    high_trap = run_arbitration(trap_risk=1.0, **args)
    assert high_trap["raw_score"] < no_trap["raw_score"]


def test_smoothing_behavior() -> None:
    out = run_arbitration(
        oi_score=1.0,
        volume_score=1.0,
        price_score=1.0,
        breakout_score=1.0,
        trap_risk=0.0,
        regime="Transition",
        previous_score=-1.0,
    )
    expected_smoothed = 0.6 * (-1.0) + 0.4 * 1.0
    assert pytest.approx(expected_smoothed, abs=1e-4) == out["smoothed_score"]
