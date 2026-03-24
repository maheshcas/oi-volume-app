from __future__ import annotations

from app.engines.sr_engine import run_sr_engine


def _features(rows: list[dict], spot: float) -> dict:
    return {
        "meta": {"spot": spot, "symbol": "NIFTY", "expiry": "10-Feb-2026", "timestamp": "x"},
        "rows": rows,
    }


def test_immediate_and_major_levels_can_differ() -> None:
    rows = [
        {"strike": 24000, "CE_OI": 15000, "CE_DeltaOI": 1200, "CE_Volume": 5000, "PE_OI": 80000, "PE_DeltaOI": 9000, "PE_Volume": 25000},
        {"strike": 24300, "CE_OI": 18000, "CE_DeltaOI": 1100, "CE_Volume": 7000, "PE_OI": 52000, "PE_DeltaOI": 4500, "PE_Volume": 15000},
        {"strike": 24400, "CE_OI": 70000, "CE_DeltaOI": 14000, "CE_Volume": 90000, "PE_OI": 24000, "PE_DeltaOI": 1000, "PE_Volume": 5000},
        {"strike": 24500, "CE_OI": 22000, "CE_DeltaOI": 1500, "CE_Volume": 9000, "PE_OI": 22000, "PE_DeltaOI": 900, "PE_Volume": 6000},
        {"strike": 25000, "CE_OI": 250000, "CE_DeltaOI": 45000, "CE_Volume": 280000, "PE_OI": 5000, "PE_DeltaOI": 100, "PE_Volume": 1500},
    ]
    out = run_sr_engine(_features(rows, spot=24380))

    assert out["resistance"]["immediate"] == 24400
    assert out["resistance"]["major"] == 25000
    assert out["support"]["immediate"] == 24300
    assert out["support"]["major"] == 24000

    # Backward compatibility fields still point to immediate levels.
    assert out["resistance"]["strike"] == out["resistance"]["immediate"]
    assert out["support"]["strike"] == out["support"]["immediate"]


def test_level_shift_detection_for_new_intraday_resistance() -> None:
    rows = [
        {"strike": 24300, "CE_OI": 15000, "CE_DeltaOI": 500, "CE_Volume": 7000, "PE_OI": 30000, "PE_DeltaOI": 2500, "PE_Volume": 9000},
        {"strike": 24400, "CE_OI": 120000, "CE_DeltaOI": 36000, "CE_Volume": 260000, "PE_OI": 18000, "PE_DeltaOI": 800, "PE_Volume": 4500},
        {"strike": 24500, "CE_OI": 90000, "CE_DeltaOI": 9000, "CE_Volume": 45000, "PE_OI": 16000, "PE_DeltaOI": 700, "PE_Volume": 4000},
        {"strike": 25000, "CE_OI": 180000, "CE_DeltaOI": 17000, "CE_Volume": 85000, "PE_OI": 6000, "PE_DeltaOI": 200, "PE_Volume": 1500},
    ]
    previous_state = {
        "levels": {
            "resistance": {"immediate": 24500, "immediate_score": 0.35},
            "support": {"immediate": 24300, "immediate_score": 0.2},
        }
    }
    out = run_sr_engine(_features(rows, spot=24380), previous_state=previous_state)

    shift = out["level_shift"]["resistance"]
    assert shift["shift_detected"] is True
    assert any("New Intraday Resistance Formed" in a["message"] for a in shift["alerts"])


def test_response_shape_includes_tiers_and_alerts() -> None:
    rows = [
        {"strike": 24300, "CE_OI": 15000, "CE_DeltaOI": 500, "CE_Volume": 7000, "PE_OI": 30000, "PE_DeltaOI": 2500, "PE_Volume": 9000},
        {"strike": 24400, "CE_OI": 45000, "CE_DeltaOI": 6500, "CE_Volume": 30000, "PE_OI": 22000, "PE_DeltaOI": 900, "PE_Volume": 4500},
    ]
    out = run_sr_engine(_features(rows, spot=24360))
    assert "support" in out and "resistance" in out
    assert {"immediate", "major"}.issubset(set(out["support"].keys()))
    assert {"immediate", "major"}.issubset(set(out["resistance"].keys()))
    assert "alerts" in out
    assert isinstance(out["alerts"], list)
    assert "support_center" in out
    assert "resistance_center" in out
    assert "cluster_zones" in out
    assert 0.0 <= float(out.get("support_strength", 0.0) or 0.0) <= 1.0
    assert 0.0 <= float(out.get("resistance_strength", 0.0) or 0.0) <= 1.0


def test_support_demotion_is_buffered_until_spot_breaks_25_points_below_previous_support() -> None:
    rows = [
        {"strike": 22400, "CE_OI": 10000, "CE_DeltaOI": 300, "CE_Volume": 4000, "PE_OI": 125000, "PE_DeltaOI": 22000, "PE_Volume": 52000},
        {"strike": 22500, "CE_OI": 12000, "CE_DeltaOI": 400, "CE_Volume": 4500, "PE_OI": 115000, "PE_DeltaOI": 18000, "PE_Volume": 48000},
        {"strike": 22700, "CE_OI": 140000, "CE_DeltaOI": 12000, "CE_Volume": 62000, "PE_OI": 8000, "PE_DeltaOI": 200, "PE_Volume": 2500},
    ]
    previous_state = {
        "levels": {
            "support": {"immediate": 22500, "immediate_score": 0.95},
            "resistance": {"immediate": 22700, "immediate_score": 0.75},
        }
    }

    out = run_sr_engine(_features(rows, spot=22490.95), previous_state=previous_state)

    assert out["support"]["immediate"] == 22500
    assert out["support"]["strike"] == 22500
