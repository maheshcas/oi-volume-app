from __future__ import annotations

from app.engines.decision_engine import run_decision_engine_v4


def test_clarity_computation_bounds() -> None:
    out = run_decision_engine_v4(
        oi_score=0.8,
        volume_score=0.8,
        breakout_score=0.8,
        sr_score=0.8,
        trap_penalty=0.1,
        alignment_ratio=0.9,
        bias_stability_score=80,
    )
    assert 0 <= out["clarity"] <= 100


def test_state_transition_aggressive_trend() -> None:
    out = run_decision_engine_v4(
        oi_score=1.0,
        volume_score=1.0,
        breakout_score=1.0,
        sr_score=1.0,
        trap_penalty=0.05,
        alignment_ratio=1.0,
        bias_stability_score=80,
        regime_type="Trend Day",
        volatility_ratio=1.0,
    )
    assert out["state"] in {"Aggressive Trend", "Cautious Trend"}


def test_state_transition_standby_with_high_risk() -> None:
    out = run_decision_engine_v4(
        oi_score=0.3,
        volume_score=0.2,
        breakout_score=0.1,
        sr_score=0.2,
        trap_penalty=0.95,
        alignment_ratio=0.4,
        bias_stability_score=40,
        regime_type="Trap Risk",
        volatility_ratio=1.6,
    )
    assert out["state"] == "Standby"
    assert out["execution_risk"] > 60


def test_session_phase_adjustments_affect_weights() -> None:
    opening = run_decision_engine_v4(
        oi_score=0.6,
        volume_score=0.4,
        breakout_score=0.5,
        sr_score=0.3,
        trap_penalty=0.1,
        alignment_ratio=0.6,
        bias_stability_score=60,
        session_phase="Opening",
    )
    midday = run_decision_engine_v4(
        oi_score=0.6,
        volume_score=0.4,
        breakout_score=0.5,
        sr_score=0.3,
        trap_penalty=0.1,
        alignment_ratio=0.6,
        bias_stability_score=60,
        session_phase="Midday",
    )
    assert opening["weight_distribution"]["breakout"] > midday["weight_distribution"]["breakout"]
