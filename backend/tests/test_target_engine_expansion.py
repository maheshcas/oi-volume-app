from __future__ import annotations

from app.engines.target_engine import run_target_engine


def _features() -> dict:
    return {
        "meta": {"spot": 24380, "timestamp": "05-Mar-2026 11:10:00"},
        "atm_row": {"CE_LastPrice": 120, "PE_LastPrice": 110},
        "rows": [
            {"strike": 24200, "CE_OI": 15000, "PE_OI": 30000},
            {"strike": 24300, "CE_OI": 22000, "PE_OI": 45000},
            {"strike": 24400, "CE_OI": 75000, "PE_OI": 23000},
            {"strike": 24500, "CE_OI": 90000, "PE_OI": 18000},
            {"strike": 24600, "CE_OI": 120000, "PE_OI": 12000},
        ],
    }


def _sr() -> dict:
    return {
        "support": {"strike": 24300},
        "resistance": {"strike": 24400},
    }


def test_expansion_targets_present_when_breakout_confirmed() -> None:
    out = run_target_engine(
        _features(),
        _sr(),
        breakout={"breakout_up": True, "breakout_down": False, "breakout_strength": 0.8},
        oi={"oi_velocity_score": 0.7},
        trap={"trap_probability_pct": 20},
        volume={"volume_expansion": True, "atm_participation": 0.65},
        decision={"bias": "Bullish"},
        regime={},
    )

    assert out["primary_target"] is not None
    assert out["extended_target"] is not None
    assert 0.0 <= out["gap_strength"] <= 1.0
    assert 0.0 <= out["expansion_score"] <= 1.0


def test_expansion_targets_absent_without_breakout() -> None:
    out = run_target_engine(
        _features(),
        _sr(),
        breakout={"breakout_up": False, "breakout_down": False},
        oi={"oi_velocity_score": 0.2},
        trap={"trap_probability_pct": 60},
        volume={"volume_expansion": False, "atm_participation": 0.2},
        decision={"bias": "Neutral"},
        regime={},
    )

    assert out["primary_target"] is None
    assert out["extended_target"] is None
    assert 0.0 <= out["expansion_score"] <= 1.0
