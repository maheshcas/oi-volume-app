from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


IST = timezone(timedelta(hours=5, minutes=30))


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _minutes_from_dt(timestamp: datetime | None) -> int | None:
    if timestamp is None:
        return None
    local_dt = timestamp.astimezone(IST)
    return (local_dt.hour * 60) + local_dt.minute


def compute_session_phase(
    *,
    timestamp: datetime | None,
    spot: float | None,
    support: float | None,
    resistance: float | None,
    volatility_ratio: float,
    range_compression_events_5m: int,
    oi_spike_events_5m: int,
    material_breach: dict[str, Any] | None,
    volume_expansion_score: float,
    oi_shift_score: float,
) -> dict[str, Any]:
    minutes = _minutes_from_dt(timestamp)
    if minutes is None:
        return {"session_phase": "Transition", "confidence": 0.45}

    spot_value = float(spot or 0.0)
    support_value = float(support or 0.0)
    resistance_value = float(resistance or 0.0)
    session_range_ratio = (
        abs(resistance_value - support_value) / spot_value
        if spot_value > 0 and support_value > 0 and resistance_value > 0
        else 0.0
    )
    breach = material_breach or {}
    support_broken = bool(breach.get("support_broken"))
    resistance_broken = bool(breach.get("resistance_broken"))
    high_volatility = float(volatility_ratio or 0.0) >= 1.15
    rapid_range_expansion = session_range_ratio >= 0.005
    range_intact = not support_broken and not resistance_broken

    session_phase = "Transition"
    confidence = 0.45

    if 9 * 60 + 15 <= minutes < 9 * 60 + 45:
        session_phase = "Opening Drive"
        confidence = 0.86 if (high_volatility or rapid_range_expansion) else 0.68
    elif 9 * 60 + 45 <= minutes < 11 * 60 + 30:
        session_phase = "Structure Formation"
        confirmations = sum(
            [
                support_value > 0,
                resistance_value > 0,
                range_intact,
                session_range_ratio > 0,
            ]
        )
        confidence = 0.58 + (0.08 * max(0, confirmations - 1))
    elif 11 * 60 + 30 <= minutes < 13 * 60 + 30:
        session_phase = "Compression Phase"
        if session_range_ratio < 0.005 and range_compression_events_5m >= 2:
            confidence = 0.68 + min(0.22, range_compression_events_5m * 0.02)
        else:
            confidence = 0.52
    elif 13 * 60 + 30 <= minutes < 14 * 60 + 45:
        session_phase = "Position Build Phase"
        if oi_spike_events_5m >= 3 and range_intact:
            confidence = 0.7 + min(0.2, (oi_spike_events_5m - 3) * 0.04)
        else:
            confidence = 0.54
    elif 14 * 60 + 45 <= minutes < 15 * 60 + 15:
        session_phase = "Expansion Window"
        if (support_broken or resistance_broken) and (
            float(volume_expansion_score or 0.0) > 0.5 or float(oi_shift_score or 0.0) > 0.6
        ):
            confidence = 0.78 + min(0.15, float(volume_expansion_score or 0.0) * 0.1)
        else:
            confidence = 0.56

    return {
        "session_phase": session_phase,
        "confidence": round(_clamp(confidence, 0.0, 0.99), 2),
    }
