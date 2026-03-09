from __future__ import annotations

from app.engines.decision_engine import run_decision_engine_v4


def test_primary_bias_changes_only_after_sustained_force() -> None:
    out = run_decision_engine_v4(
        oi_score=-0.9,
        volume_score=-0.8,
        breakout_score=-0.8,
        sr_score=-0.7,
        trap_penalty=0.1,
        alignment_ratio=0.7,
        bias_stability_score=70,
        previous_primary_bias="Bullish",
        rolling_force_history=[70, 72],
        rolling_clarity_history=[62, 64],
        breakout_confirmed=False,
        volume_expansion_confirmed=False,
    )
    assert out["primary_bias"] == "Bearish"
    assert out["framework_status"] in {"Shifted", "Stable"}


def test_primary_bias_kept_when_threshold_not_met() -> None:
    out = run_decision_engine_v4(
        oi_score=-0.2,
        volume_score=-0.1,
        breakout_score=-0.1,
        sr_score=-0.2,
        trap_penalty=0.2,
        alignment_ratio=0.5,
        bias_stability_score=55,
        previous_primary_bias="Bullish",
        rolling_force_history=[40, 42],
        rolling_clarity_history=[40, 42],
        breakout_confirmed=False,
        volume_expansion_confirmed=False,
    )
    assert out["primary_bias"] == "Bullish"


def test_midday_requires_higher_threshold_to_flip() -> None:
    out = run_decision_engine_v4(
        oi_score=-0.8,
        volume_score=-0.8,
        breakout_score=-0.8,
        sr_score=-0.8,
        trap_penalty=0.1,
        alignment_ratio=0.8,
        bias_stability_score=70,
        previous_primary_bias="Neutral",
        rolling_force_history=[70, 72],
        rolling_clarity_history=[61, 62],
        session_phase="Midday",
    )
    # Midday threshold is stricter; this setup should not auto-flip primary bias.
    assert out["primary_bias"] == "Neutral"


def test_drift_strengthening_and_weakening() -> None:
    strengthening = run_decision_engine_v4(
        oi_score=0.4,
        volume_score=0.3,
        breakout_score=0.2,
        sr_score=0.2,
        trap_penalty=0.1,
        alignment_ratio=0.6,
        bias_stability_score=60,
        previous_primary_bias="Neutral",
        rolling_force_history=[20, 30, 35, 40],
        rolling_clarity_history=[55, 55, 55, 55],
    )
    weakening = run_decision_engine_v4(
        oi_score=0.1,
        volume_score=0.1,
        breakout_score=0.0,
        sr_score=0.1,
        trap_penalty=0.1,
        alignment_ratio=0.6,
        bias_stability_score=60,
        previous_primary_bias="Neutral",
        rolling_force_history=[60, 58, 55, 50],
        rolling_clarity_history=[55, 55, 55, 55],
    )
    assert strengthening["drift"] == "Strengthening"
    assert weakening["drift"] == "Weakening"
