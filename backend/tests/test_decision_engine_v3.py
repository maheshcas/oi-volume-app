from __future__ import annotations

from app.engines.decision_engine import run_decision_engine_v3


def test_structural_clarity_penalty_applies_when_major_levels_far() -> None:
    base = run_decision_engine_v3(
        oi_score=0.4,
        volume_score=0.4,
        breakout_score=0.3,
        sr_score=0.2,
        trap_penalty=0.1,
        alignment_ratio=0.7,
        bias_stability_score=70,
        spot=24400,
        support_immediate=24300,
        support_major=24250,
        resistance_immediate=24450,
        resistance_major=24500,
    )
    far = run_decision_engine_v3(
        oi_score=0.4,
        volume_score=0.4,
        breakout_score=0.3,
        sr_score=0.2,
        trap_penalty=0.1,
        alignment_ratio=0.7,
        bias_stability_score=70,
        spot=24400,
        support_immediate=24300,
        support_major=23800,
        resistance_immediate=24450,
        resistance_major=25000,
    )

    assert far["structural_clarity_score"] < base["structural_clarity_score"]
    assert far["confidence"] < base["confidence"]


def test_near_immediate_resistance_boosts_breakout_component() -> None:
    near = run_decision_engine_v3(
        oi_score=0.2,
        volume_score=0.2,
        breakout_score=0.7,
        sr_score=0.0,
        trap_penalty=0.0,
        alignment_ratio=0.6,
        bias_stability_score=60,
        spot=24400,
        support_immediate=24300,
        support_major=24250,
        resistance_immediate=24430,
        resistance_major=24600,
    )
    far = run_decision_engine_v3(
        oi_score=0.2,
        volume_score=0.2,
        breakout_score=0.7,
        sr_score=0.0,
        trap_penalty=0.0,
        alignment_ratio=0.6,
        bias_stability_score=60,
        spot=24400,
        support_immediate=24300,
        support_major=24250,
        resistance_immediate=24800,
        resistance_major=25000,
    )
    assert near["bull_probability"] >= far["bull_probability"]
