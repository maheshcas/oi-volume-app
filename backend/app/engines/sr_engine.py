from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


OptionType = Literal["CE", "PE"]


@dataclass
class _ScoredStrike:
    strike: float
    score: float
    oi: float
    doi: float
    vol: float
    distance_pct: float
    side: OptionType


def _to_float(value: Any, fallback: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return fallback
    return out


def _compute_raw_score(row: dict[str, Any], side: OptionType) -> tuple[float, float, float, float]:
    if side == "CE":
        oi = _to_float(row.get("CE_OI"), 0.0)
        doi = max(0.0, _to_float(row.get("CE_DeltaOI"), 0.0))
        vol = _to_float(row.get("CE_Volume"), 0.0)
    else:
        oi = _to_float(row.get("PE_OI"), 0.0)
        doi = max(0.0, _to_float(row.get("PE_DeltaOI"), 0.0))
        vol = _to_float(row.get("PE_Volume"), 0.0)
    raw = (oi * 0.5) + (doi * 0.3) + (vol * 0.2)
    return raw, oi, doi, vol


def _normalize_scores(values: list[float]) -> list[float]:
    if not values:
        return []
    lo = min(values)
    hi = max(values)
    if hi <= lo:
        return [1.0 for _ in values]
    return [max(0.0, min(1.0, (v - lo) / (hi - lo))) for v in values]


def _build_scored_rows(rows: list[dict[str, Any]], side: OptionType, spot: float | None) -> list[_ScoredStrike]:
    raw_list: list[tuple[float, dict[str, Any], float, float, float]] = []
    for row in rows:
        strike = _to_float(row.get("strike"), 0.0)
        raw, oi, doi, vol = _compute_raw_score(row, side)
        raw_list.append((raw, row, oi, doi, vol))

    normalized = _normalize_scores([item[0] for item in raw_list])
    scored: list[_ScoredStrike] = []
    for idx, (_, row, oi, doi, vol) in enumerate(raw_list):
        strike = _to_float(row.get("strike"), 0.0)
        distance_pct = 999.0
        if spot is not None and spot > 0:
            distance_pct = abs(strike - spot) / spot
        scored.append(
            _ScoredStrike(
                strike=strike,
                score=round(normalized[idx], 6),
                oi=oi,
                doi=doi,
                vol=vol,
                distance_pct=distance_pct,
                side=side,
            )
        )
    return scored


def _top_levels(scored: list[_ScoredStrike]) -> list[dict[str, Any]]:
    ordered = sorted(scored, key=lambda x: x.score, reverse=True)[:5]
    return [{"strike": item.strike, "score": round(item.score * 100, 2)} for item in ordered]


def _pick_major(scored: list[_ScoredStrike]) -> _ScoredStrike | None:
    if not scored:
        return None
    return max(scored, key=lambda x: x.score)


def _pick_immediate(scored: list[_ScoredStrike], spot: float | None, side: OptionType) -> _ScoredStrike | None:
    if not scored or spot is None or spot <= 0:
        return None
    if side == "CE":
        directional = [s for s in scored if s.strike > spot]
    else:
        directional = [s for s in scored if s.strike < spot]
    if not directional:
        return None

    zone = [s for s in directional if 0.005 <= s.distance_pct <= 0.01]
    if not zone:
        zone = [s for s in directional if s.distance_pct <= 0.01]
    if not zone:
        zone = directional

    top3 = sorted(zone, key=lambda x: x.score, reverse=True)[:3]
    if not top3:
        return None
    return min(top3, key=lambda x: abs(x.strike - spot))


def _compute_cluster_zone(
    rows: list[dict[str, Any]],
    *,
    side: OptionType,
    spot: float | None,
    step_window: int = 2,
) -> dict[str, Any]:
    if not rows:
        return {"center": None, "range": [None, None], "strength": 0.0}

    sorted_rows = sorted(rows, key=lambda r: _to_float(r.get("strike"), 0.0))
    oi_key = "CE_OI" if side == "CE" else "PE_OI"
    total_chain_oi = sum(max(0.0, _to_float(r.get(oi_key), 0.0)) for r in sorted_rows)
    if total_chain_oi <= 0:
        return {"center": None, "range": [None, None], "strength": 0.0}

    candidates: list[dict[str, Any]] = []
    for idx, row in enumerate(sorted_rows):
        strike = _to_float(row.get("strike"), 0.0)
        if spot is not None:
            if side == "CE" and strike <= spot:
                continue
            if side == "PE" and strike >= spot:
                continue

        start = max(0, idx - step_window)
        end = min(len(sorted_rows) - 1, idx + step_window)
        window = sorted_rows[start : end + 1]
        cluster_oi = sum(max(0.0, _to_float(w.get(oi_key), 0.0)) for w in window)
        strength = cluster_oi / total_chain_oi
        candidates.append(
            {
                "center": strike,
                "range": [_to_float(window[0].get("strike"), 0.0), _to_float(window[-1].get("strike"), 0.0)],
                "strength": round(max(0.0, min(1.0, strength)), 6),
            }
        )

    if not candidates:
        return {"center": None, "range": [None, None], "strength": 0.0}
    return max(candidates, key=lambda c: c["strength"])


def _safe_range(zone_range: list[Any] | None, center: float | None, step: float) -> tuple[float | None, float | None]:
    if isinstance(zone_range, list) and len(zone_range) == 2:
        low = _to_float(zone_range[0], 0.0)
        high = _to_float(zone_range[1], 0.0)
        if high >= low:
            return low, high
    if center is None:
        return None, None
    w = max(step, 1.0)
    return float(center - w), float(center + w)


def _zone_proximity_to_edge(spot: float | None, low: float | None, high: float | None) -> float:
    if spot is None or low is None or high is None or high <= low:
        return 0.0
    if spot < low or spot > high:
        return 0.0
    width = max(1e-9, high - low)
    dist_left = abs(spot - low)
    dist_right = abs(high - spot)
    dist_edge = min(dist_left, dist_right)
    return max(0.0, min(1.0, 1.0 - (dist_edge / (width / 2.0))))


def _time_inside_zone_ratio(
    observations: list[dict[str, Any]],
    low: float | None,
    high: float | None,
) -> float:
    if low is None or high is None or high <= low:
        return 0.0
    if len(observations) < 2:
        if not observations:
            return 0.0
        px = _to_float(observations[-1].get("spot"), 0.0)
        return 1.0 if low <= px <= high else 0.0

    total = 0.0
    inside = 0.0
    for i in range(1, len(observations)):
        prev = observations[i - 1]
        cur = observations[i]
        dt = max(0.0, _to_float(cur.get("ts"), 0.0) - _to_float(prev.get("ts"), 0.0))
        total += dt
        px = _to_float(prev.get("spot"), 0.0)
        if low <= px <= high:
            inside += dt
    if total <= 0:
        return 0.0
    return max(0.0, min(1.0, inside / total))


def _zone_oi_unwinding_score(rows: list[dict[str, Any]], low: float | None, high: float | None, side: OptionType) -> float:
    if low is None or high is None or high <= low:
        return 0.0
    in_zone = [r for r in rows if low <= _to_float(r.get("strike"), 0.0) <= high]
    if not in_zone:
        return 0.0
    if side == "PE":
        unwind = sum(max(0.0, -_to_float(r.get("PE_DeltaOI"), 0.0)) for r in in_zone)
        base = sum(abs(_to_float(r.get("PE_DeltaOI"), 0.0)) for r in in_zone)
    else:
        unwind = sum(max(0.0, -_to_float(r.get("CE_DeltaOI"), 0.0)) for r in in_zone)
        base = sum(abs(_to_float(r.get("CE_DeltaOI"), 0.0)) for r in in_zone)
    return max(0.0, min(1.0, unwind / max(1.0, base)))


def _zone_volume_expansion_near_zone(rows: list[dict[str, Any]], low: float | None, high: float | None) -> float:
    if low is None or high is None or high <= low:
        return 0.0
    in_zone = [r for r in rows if low <= _to_float(r.get("strike"), 0.0) <= high]
    if not in_zone:
        return 0.0
    zone_vol = sum(_to_float(r.get("CE_Volume"), 0.0) + _to_float(r.get("PE_Volume"), 0.0) for r in in_zone)
    avg_row_vol = (
        sum(_to_float(r.get("CE_Volume"), 0.0) + _to_float(r.get("PE_Volume"), 0.0) for r in rows) / max(1, len(rows))
    )
    zone_avg_vol = zone_vol / max(1, len(in_zone))
    ratio = zone_avg_vol / max(1.0, avg_row_vol)
    return max(0.0, min(1.0, ratio / 2.0))


def _zone_retest_count_score(
    observations: list[dict[str, Any]],
    low: float | None,
    high: float | None,
) -> float:
    if low is None or high is None or high <= low or len(observations) < 2:
        return 0.0
    transitions = 0
    prev_inside = low <= _to_float(observations[0].get("spot"), 0.0) <= high
    for i in range(1, len(observations)):
        cur_inside = low <= _to_float(observations[i].get("spot"), 0.0) <= high
        if cur_inside and not prev_inside:
            transitions += 1
        prev_inside = cur_inside
    return max(0.0, min(1.0, transitions / 4.0))


def _zone_state_from_pressure(pressure: float) -> str:
    if pressure < 35:
        return "Stable"
    if pressure < 60:
        return "Under Pressure"
    return "Likely Break"


def _compute_zone_pressure(
    rows: list[dict[str, Any]],
    spot: float | None,
    observations: list[dict[str, Any]],
    *,
    center: float | None,
    zone_range: list[Any] | None,
    side: OptionType,
    step: float,
) -> dict[str, Any]:
    low, high = _safe_range(zone_range, center, step)
    proximity_to_edge = _zone_proximity_to_edge(spot, low, high)
    time_inside_zone_ratio = _time_inside_zone_ratio(observations, low, high)
    oi_unwinding_score = _zone_oi_unwinding_score(rows, low, high, side)
    volume_expansion_near_zone = _zone_volume_expansion_near_zone(rows, low, high)
    retest_count_score = _zone_retest_count_score(observations, low, high)

    pressure = (
        0.30 * proximity_to_edge
        + 0.25 * time_inside_zone_ratio
        + 0.20 * oi_unwinding_score
        + 0.15 * volume_expansion_near_zone
        + 0.10 * retest_count_score
    )
    pressure_100 = max(0.0, min(100.0, pressure * 100.0))
    return {
        "center": center,
        "range": [low, high],
        "pressure": round(pressure_100, 2),
        "state": _zone_state_from_pressure(pressure_100),
        "components": {
            "proximity_to_edge": round(proximity_to_edge, 4),
            "time_inside_zone_ratio": round(time_inside_zone_ratio, 4),
            "oi_unwinding_score": round(oi_unwinding_score, 4),
            "volume_expansion_near_zone": round(volume_expansion_near_zone, 4),
            "retest_count_score": round(retest_count_score, 4),
        },
    }


def _detect_shift(
    *,
    side: OptionType,
    immediate: _ScoredStrike | None,
    previous_state: dict[str, Any] | None,
    avg_volume: float,
    volume_threshold: float,
    oi_spike_threshold: float,
) -> dict[str, Any]:
    if immediate is None:
        return {"shift_detected": False, "alerts": [], "details": {}}

    prev_levels = (previous_state or {}).get("levels", {})
    side_key = "resistance" if side == "CE" else "support"
    prev_obj = prev_levels.get(side_key, {}) if isinstance(prev_levels, dict) else {}
    prev_immediate = prev_obj.get("immediate") if isinstance(prev_obj, dict) else None
    prev_score = _to_float((prev_obj.get("immediate_score") if isinstance(prev_obj, dict) else None), 0.0)

    if prev_immediate is None:
        return {"shift_detected": False, "alerts": [], "details": {}}

    is_nearer = False
    try:
        prev_immediate_num = float(prev_immediate)
        if side == "CE":
            is_nearer = immediate.strike < prev_immediate_num
        else:
            is_nearer = immediate.strike > prev_immediate_num
    except (TypeError, ValueError):
        return {"shift_detected": False, "alerts": [], "details": {}}

    oi_base = max(1.0, immediate.oi)
    oi_spike = (immediate.doi / oi_base) > oi_spike_threshold
    vol_expansion = immediate.vol > (avg_volume * volume_threshold)
    stronger = immediate.score > prev_score
    shifted = is_nearer and stronger and oi_spike and vol_expansion

    alerts: list[dict[str, str]] = []
    if shifted:
        if side == "CE":
            alerts.append(
                {
                    "type": "sr_shift",
                    "message": f"New Intraday Resistance Formed at {int(immediate.strike)}",
                    "tier": "immediate",
                }
            )
        else:
            direction = "Down" if immediate.strike < prev_immediate_num else "Up"
            alerts.append(
                {
                    "type": "sr_shift",
                    "message": f"Support Shift {direction} to {int(immediate.strike)}",
                    "tier": "immediate",
                }
            )
    return {
        "shift_detected": shifted,
        "alerts": alerts,
        "details": {
            "previous_immediate": prev_immediate,
            "previous_score": round(prev_score, 6),
            "current_score": round(immediate.score, 6),
            "is_nearer": is_nearer,
            "oi_spike": oi_spike,
            "volume_expansion": vol_expansion,
        },
    }


def run_sr_engine(
    features: dict[str, Any],
    previous_state: dict[str, Any] | None = None,
    *,
    oi_spike_threshold: float = 0.2,
    volume_expansion_threshold: float = 1.2,
) -> dict[str, Any]:
    rows = features.get("rows", []) or []
    spot = features.get("meta", {}).get("spot")
    spot_num = _to_float(spot, 0.0) if spot is not None else None
    if spot_num is not None and spot_num <= 0:
        spot_num = None

    if not rows:
        return {
            "support": {"strike": None, "score": 0.0, "immediate": None, "major": None, "levels": []},
            "resistance": {"strike": None, "score": 0.0, "immediate": None, "major": None, "levels": []},
            "alerts": [],
            "level_shift": {"support": {"shift_detected": False}, "resistance": {"shift_detected": False}},
        }

    ce_scored = _build_scored_rows(rows, "CE", spot_num)
    pe_scored = _build_scored_rows(rows, "PE", spot_num)

    major_res = _pick_major(ce_scored)
    major_sup = _pick_major(pe_scored)
    immediate_res = _pick_immediate(ce_scored, spot_num, "CE")
    immediate_sup = _pick_immediate(pe_scored, spot_num, "PE")

    ce_avg_vol = sum(s.vol for s in ce_scored) / max(1, len(ce_scored))
    pe_avg_vol = sum(s.vol for s in pe_scored) / max(1, len(pe_scored))

    res_shift = _detect_shift(
        side="CE",
        immediate=immediate_res,
        previous_state=previous_state,
        avg_volume=ce_avg_vol,
        volume_threshold=volume_expansion_threshold,
        oi_spike_threshold=oi_spike_threshold,
    )
    sup_shift = _detect_shift(
        side="PE",
        immediate=immediate_sup,
        previous_state=previous_state,
        avg_volume=pe_avg_vol,
        volume_threshold=volume_expansion_threshold,
        oi_spike_threshold=oi_spike_threshold,
    )

    alerts = [*res_shift.get("alerts", []), *sup_shift.get("alerts", [])]
    if major_res is not None:
        alerts.append(
            {
                "type": "sr_major",
                "message": f"Major Resistance Confirmed at {int(major_res.strike)}",
                "tier": "major",
            }
        )
    if immediate_sup is not None and major_sup is not None and major_sup.score >= 0.75:
        alerts.append(
            {
                "type": "sr_major",
                "message": f"Support Strengthening near {int(immediate_sup.strike)}",
                "tier": "immediate",
            }
        )

    resistance_immediate = immediate_res.strike if immediate_res is not None else (major_res.strike if major_res else None)
    support_immediate = immediate_sup.strike if immediate_sup is not None else (major_sup.strike if major_sup else None)
    support_zone = _compute_cluster_zone(rows, side="PE", spot=spot_num, step_window=2)
    resistance_zone = _compute_cluster_zone(rows, side="CE", spot=spot_num, step_window=2)
    sorted_strikes = sorted({_to_float(r.get("strike"), 0.0) for r in rows})
    strike_step = 50.0
    if len(sorted_strikes) >= 2:
        diffs = [abs(sorted_strikes[i] - sorted_strikes[i - 1]) for i in range(1, len(sorted_strikes))]
        diffs = [d for d in diffs if d > 0]
        if diffs:
            strike_step = min(diffs)
    observations = (previous_state or {}).get("spot_observations", [])
    observations = observations if isinstance(observations, list) else []

    support_pressure = _compute_zone_pressure(
        rows,
        spot_num,
        observations,
        center=support_zone.get("center"),
        zone_range=support_zone.get("range"),
        side="PE",
        step=strike_step,
    )
    resistance_pressure = _compute_zone_pressure(
        rows,
        spot_num,
        observations,
        center=resistance_zone.get("center"),
        zone_range=resistance_zone.get("range"),
        side="CE",
        step=strike_step,
    )

    return {
        # Backward compatible fields: strike/score default to immediate levels.
        "resistance": {
            "strike": resistance_immediate,
            "score": round((immediate_res.score if immediate_res else (major_res.score if major_res else 0.0)) * 100, 2),
            "immediate": resistance_immediate,
            "major": major_res.strike if major_res else None,
            "immediate_score": round(immediate_res.score if immediate_res else 0.0, 6),
            "major_score": round(major_res.score if major_res else 0.0, 6),
            "levels": _top_levels(ce_scored),
        },
        "support": {
            "strike": support_immediate,
            "score": round((immediate_sup.score if immediate_sup else (major_sup.score if major_sup else 0.0)) * 100, 2),
            "immediate": support_immediate,
            "major": major_sup.strike if major_sup else None,
            "immediate_score": round(immediate_sup.score if immediate_sup else 0.0, 6),
            "major_score": round(major_sup.score if major_sup else 0.0, 6),
            "levels": _top_levels(pe_scored),
        },
        "level_shift": {"resistance": res_shift, "support": sup_shift},
        "cluster_zones": {
            "support_zone": {
                "support_center": support_zone.get("center"),
                "support_range": support_zone.get("range"),
                "support_strength": support_zone.get("strength"),
            },
            "resistance_zone": {
                "resistance_center": resistance_zone.get("center"),
                "resistance_range": resistance_zone.get("range"),
                "resistance_strength": resistance_zone.get("strength"),
            },
        },
        "support_center": support_zone.get("center"),
        "support_range": support_zone.get("range"),
        "support_strength": support_zone.get("strength"),
        "support_zone_pressure": support_pressure.get("pressure"),
        "support_zone_state": support_pressure.get("state"),
        "resistance_center": resistance_zone.get("center"),
        "resistance_range": resistance_zone.get("range"),
        "resistance_strength": resistance_zone.get("strength"),
        "resistance_zone_pressure": resistance_pressure.get("pressure"),
        "resistance_zone_state": resistance_pressure.get("state"),
        "zone_pressure": {
            "support": support_pressure,
            "resistance": resistance_pressure,
        },
        "alerts": alerts,
    }
