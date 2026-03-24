from __future__ import annotations

from app.services.background_updater import _canonicalize_trap_reference


def test_trap_reference_uses_support_side_when_spot_is_closer_to_support() -> None:
    affected_level, direction = _canonicalize_trap_reference(
        trap={"trap_direction": "downside", "trap_type": "False-Break Risk"},
        spot=22506.6,
        support_level=22500.0,
        resistance_level=22700.0,
        breakout_up=False,
        breakout_down=False,
    )

    assert affected_level == 22500.0
    assert direction == "upside"


def test_trap_reference_uses_resistance_side_when_spot_is_closer_to_resistance() -> None:
    affected_level, direction = _canonicalize_trap_reference(
        trap={"trap_direction": "upside", "trap_type": "False-Break Risk"},
        spot=22611.7,
        support_level=22500.0,
        resistance_level=22700.0,
        breakout_up=False,
        breakout_down=False,
    )

    assert affected_level == 22700.0
    assert direction == "downside"
