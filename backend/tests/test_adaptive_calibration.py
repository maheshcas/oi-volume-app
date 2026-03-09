from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from app.engines.adaptive_calibration import load_adaptive_weights, update_end_of_day_calibration


def test_weight_adaptation_rules(tmp_path: Path) -> None:
    store = tmp_path / "calibration.json"
    base = load_adaptive_weights(store)

    d0 = date(2026, 1, 1)
    for i in range(10):
        update_end_of_day_calibration(
            bias_accuracy=62,
            breakout_accuracy=40,  # low breakout
            trap_accuracy=55,
            clarity_vs_outcome_accuracy=58,
            oi_accuracy=66,  # strong OI
            session_date=d0 + timedelta(days=i),
            path=store,
        )

    updated = load_adaptive_weights(store)
    assert updated["breakout"] < base["breakout"]
    assert updated["oi"] > base["oi"]
    assert abs(sum(updated.values()) - 1.0) < 1e-6


def test_rolling_window_kept_at_20(tmp_path: Path) -> None:
    store = tmp_path / "calibration.json"
    d0 = date(2026, 1, 1)
    for i in range(30):
        update_end_of_day_calibration(
            bias_accuracy=50,
            breakout_accuracy=50,
            trap_accuracy=50,
            clarity_vs_outcome_accuracy=50,
            oi_accuracy=50,
            session_date=d0 + timedelta(days=i),
            path=store,
        )
    payload = json.loads(store.read_text(encoding="utf-8"))
    assert len(payload.get("sessions", [])) == 20
