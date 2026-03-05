from __future__ import annotations

from typing import Any

PHASE_MULTIPLIER_MAP: dict[str, float] = {
    "Opening Drive": 1.0,
    "Midday Compression": 0.7,
    "Positioning Phase": 0.9,
    "Power Hour": 1.3,
    "Transition": 1.0,
}


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def _cluster_window(rows: list[dict[str, Any]], center_idx: int, steps: int = 2) -> list[dict[str, Any]]:
    start = max(0, center_idx - steps)
    end = min(len(rows), center_idx + steps + 1)
    return rows[start:end]


def _cluster_total_oi(window: list[dict[str, Any]], direction: str) -> float:
    if direction == "up":
        key = "CE_OI"
        return sum(_to_float(r.get(key), 0.0) for r in window)
    if direction == "down":
        key = "PE_OI"
        return sum(_to_float(r.get(key), 0.0) for r in window)
    return sum(_to_float(r.get("CE_OI"), 0.0) + _to_float(r.get("PE_OI"), 0.0) for r in window)


def _build_directional_clusters(rows: list[dict[str, Any]], direction: str) -> list[dict[str, Any]]:
    clusters: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        window = _cluster_window(rows, idx, steps=2)
        center = _to_float(row.get("strike"), 0.0)
        clusters.append(
            {
                "center": center,
                "window": window,
                "cluster_oi": _cluster_total_oi(window, direction),
            }
        )
    return clusters


def _find_current_cluster(clusters: list[dict[str, Any]], spot: float) -> dict[str, Any] | None:
    if not clusters:
        return None
    return min(clusters, key=lambda c: abs(_to_float(c.get("center"), 0.0) - spot))


def _to_number_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _infer_session_phase(timestamp_text: str | None) -> str:
    if not timestamp_text:
        return "Transition"

    import re

    match = re.search(r"(\d{1,2}):(\d{2})", str(timestamp_text))
    if not match:
        return "Transition"

    hh = int(match.group(1))
    mm = int(match.group(2))
    minutes = (hh * 60) + mm

    if 9 * 60 + 15 <= minutes < 10 * 60 + 30:
        return "Opening Drive"
    if 10 * 60 + 30 <= minutes < 13 * 60 + 30:
        return "Midday Compression"
    if 13 * 60 + 30 <= minutes < 14 * 60 + 30:
        return "Positioning Phase"
    if 14 * 60 + 30 <= minutes <= 15 * 60 + 30:
        return "Power Hour"
    return "Transition"


def run_target_engine(
    features: dict[str, Any],
    sr: dict[str, Any],
    breakout: dict[str, Any],
    oi: dict[str, Any],
    trap: dict[str, Any],
    volume: dict[str, Any],
    decision: dict[str, Any] | None = None,
    regime: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _ = regime  # keep signature compatibility

    spot = _to_float(features.get("meta", {}).get("spot"), 0.0)
    support = _to_float(sr.get("support", {}).get("strike"), spot)
    resistance = _to_float(sr.get("resistance", {}).get("strike"), spot)
    bias = str((decision or {}).get("bias", "Neutral"))
    session_phase = _infer_session_phase(features.get("meta", {}).get("timestamp"))

    atm_row = features.get("atm_row") or {}
    atm_ce_ltp = _to_float(atm_row.get("CE_LastPrice"), 0.0)
    atm_pe_ltp = _to_float(atm_row.get("PE_LastPrice"), 0.0)
    expected_move = max(1.0, atm_ce_ltp + atm_pe_ltp)
    multiplier = PHASE_MULTIPLIER_MAP.get(session_phase, 1.0)
    adjusted_move = expected_move * multiplier

    if bias == "Bullish":
        target1 = resistance + (adjusted_move * 0.6)
        target2 = resistance + (adjusted_move * 1.0)
    elif bias == "Bearish":
        target1 = support - (adjusted_move * 0.6)
        target2 = support - (adjusted_move * 1.0)
    else:
        target1 = spot + adjusted_move
        target2 = spot - adjusted_move

    rows = sorted(features.get("rows", []) or [], key=lambda r: _to_float(r.get("strike"), 0.0))
    breakout_up = bool(breakout.get("breakout_up"))
    breakout_down = bool(breakout.get("breakout_down"))
    breakout_confirmed = breakout_up or breakout_down
    direction = "up" if breakout_up else "down" if breakout_down else "neutral"

    primary_target: float | None = None
    extended_target: float | None = None
    gap_strength = 0.0

    if rows and direction in {"up", "down"}:
        clusters = _build_directional_clusters(rows, direction)
        current_cluster = _find_current_cluster(clusters, spot)
        if current_cluster is not None:
            current_center = _to_float(current_cluster.get("center"), spot)
            if direction == "up":
                directional = [c for c in clusters if _to_float(c.get("center"), 0.0) > current_center]
                directional = sorted(directional, key=lambda c: _to_float(c.get("center"), 0.0))
            else:
                directional = [c for c in clusters if _to_float(c.get("center"), 0.0) < current_center]
                directional = sorted(directional, key=lambda c: _to_float(c.get("center"), 0.0), reverse=True)

            next_cluster = directional[0] if directional else None
            after_next = directional[1] if len(directional) > 1 else None

            if breakout_confirmed and next_cluster is not None:
                primary_target = _to_float(next_cluster.get("center"), 0.0)
                if after_next is not None:
                    extended_target = _to_float(after_next.get("center"), 0.0)

                low = min(current_center, primary_target)
                high = max(current_center, primary_target)
                between_rows = [r for r in rows if low <= _to_float(r.get("strike"), 0.0) <= high]
                avg_oi_between = 0.0
                if between_rows:
                    avg_oi_between = sum(
                        _to_float(r.get("CE_OI"), 0.0) + _to_float(r.get("PE_OI"), 0.0) for r in between_rows
                    ) / len(between_rows)
                max_cluster_oi = max(
                    _to_float(current_cluster.get("cluster_oi"), 0.0),
                    _to_float(next_cluster.get("cluster_oi"), 0.0),
                    1.0,
                )
                gap_strength = _clamp(1.0 - (avg_oi_between / max_cluster_oi), 0.0, 1.0)

    breakout_strength = _to_number_or_none(breakout.get("breakout_strength"))
    if breakout_strength is None:
        breakout_strength = 1.0 if breakout_confirmed else 0.0
    breakout_strength = _clamp(breakout_strength, 0.0, 1.0)

    volume_expansion = _to_number_or_none(volume.get("volume_expansion_score"))
    if volume_expansion is None:
        volume_expansion = _to_number_or_none(volume.get("atm_participation"))
    if volume_expansion is None:
        volume_expansion = 1.0 if bool(volume.get("volume_expansion")) else 0.0
    volume_expansion = _clamp(volume_expansion, 0.0, 1.0)

    oi_velocity_score = _clamp(_to_float(oi.get("oi_velocity_score"), 0.0), 0.0, 1.0)
    trap_probability = _to_number_or_none(trap.get("trap_probability"))
    if trap_probability is None:
        trap_probability = _to_number_or_none(trap.get("trap_probability_pct"))
    if trap_probability is None:
        trap_probability = _to_number_or_none(trap.get("trap_risk"))
    if trap_probability is None:
        trap_probability = 0.0
    trap_probability = _clamp(trap_probability / 100.0, 0.0, 1.0)
    expansion_score = _clamp(
        (0.4 * breakout_strength) + (0.25 * volume_expansion) + (0.20 * oi_velocity_score) - (0.15 * trap_probability),
        0.0,
        1.0,
    )

    return {
        "support": round(support, 2),
        "resistance": round(resistance, 2),
        "target1": round(target1, 2),
        "target2": round(target2, 2),
        "target_1": round(target1, 2),
        "target_2": round(target2, 2),
        "expected_move": round(expected_move, 2),
        "upper": round(spot + adjusted_move, 2),
        "lower": round(spot - adjusted_move, 2),
        "session_phase": session_phase,
        "phase_multiplier_used": round(multiplier, 2),
        "primary_target": round(primary_target, 2) if primary_target is not None else None,
        "extended_target": round(extended_target, 2) if extended_target is not None else None,
        "gap_strength": round(gap_strength, 4),
        "expansion_score": round(expansion_score, 4),
    }
