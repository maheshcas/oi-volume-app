from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, Literal


OptionType = Literal["CE", "PE"]

logger = logging.getLogger("optionlens.sr_engine")


@dataclass
class _ScoredStrike:
    strike: float
    score: float
    oi: float
    doi: float
    vol: float
    distance_pct: float
    side: OptionType
    normalized_oi: float = 0.0
    normalized_doi: float = 0.0
    proximity_to_spot: float = 0.0


def _to_float(value: Any, fallback: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return fallback
    return out


def _find_strike_row(rows: list[dict[str, Any]], strike: float | None) -> dict[str, Any] | None:
    if strike is None:
        return None
    for row in rows:
        row_strike = _to_float(row.get("strike"), 0.0)
        if abs(row_strike - float(strike)) < 1e-6:
            return row
    return None


def _compute_raw_score(row: dict[str, Any], side: OptionType) -> tuple[float, float, float, float]:
    if side == "CE":
        oi = _to_float(row.get("CE_OI"), 0.0)
        doi = max(0.0, _to_float(row.get("CE_DeltaOI"), 0.0))
        vol = _to_float(row.get("CE_Volume"), 0.0)
    else:
        oi = _to_float(row.get("PE_OI"), 0.0)
        doi = max(0.0, _to_float(row.get("PE_DeltaOI"), 0.0))
        vol = _to_float(row.get("PE_Volume"), 0.0)
    return 0.0, oi, doi, vol


def _hydrate_previous_sr_state(previous_state: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(previous_state, dict):
        return previous_state

    hydrated = dict(previous_state)
    levels = dict(hydrated.get("levels") or {})
    support_levels = dict(levels.get("support") or {})
    resistance_levels = dict(levels.get("resistance") or {})

    top_support = _to_float(
        hydrated.get("support_level", hydrated.get("current_support", hydrated.get("previous_support"))),
        0.0,
    )
    top_resistance = _to_float(
        hydrated.get("resistance_level", hydrated.get("current_resistance", hydrated.get("previous_resistance"))),
        0.0,
    )

    if _to_float(support_levels.get("immediate"), 0.0) <= 0 and top_support > 0:
        support_levels["immediate"] = top_support
    if _to_float(support_levels.get("major"), 0.0) <= 0 and top_support > 0:
        support_levels["major"] = top_support
    if _to_float(resistance_levels.get("immediate"), 0.0) <= 0 and top_resistance > 0:
        resistance_levels["immediate"] = top_resistance
    if _to_float(resistance_levels.get("major"), 0.0) <= 0 and top_resistance > 0:
        resistance_levels["major"] = top_resistance

    levels["support"] = support_levels
    levels["resistance"] = resistance_levels
    hydrated["levels"] = levels
    return hydrated


def _resolve_sr_cold_start_anchor(
    previous_state: dict[str, Any] | None,
    side: OptionType,
) -> dict[str, Any]:
    state = previous_state or {}
    side_key = "resistance" if side == "CE" else "support"
    nested_levels = (state.get("levels") or {}) if isinstance(state.get("levels"), dict) else {}
    nested_side = dict(nested_levels.get(side_key) or {})
    nested_immediate = _to_float(nested_side.get("immediate"), 0.0)
    nested_major = _to_float(nested_side.get("major"), 0.0)

    top_keys = (
        ("current_resistance", "resistance_level", "previous_resistance")
        if side == "CE"
        else ("current_support", "support_level", "previous_support")
    )
    top_anchor = 0.0
    for key in top_keys:
        candidate = _to_float(state.get(key), 0.0)
        if candidate > 0:
            top_anchor = candidate
            break

    anchor = nested_immediate if nested_immediate > 0 else top_anchor if top_anchor > 0 else nested_major
    used_top_level = nested_immediate <= 0 < top_anchor
    first_cycle_after_reset = bool(state.get("sr_first_cycle_after_reset", False)) or int(state.get("support_shift_cycle", 0) or 0) < 0
    guard_active = bool(anchor > 0 and (first_cycle_after_reset or used_top_level))
    return {
        "anchor": anchor if anchor > 0 else None,
        "used_top_level": used_top_level,
        "first_cycle_after_reset": first_cycle_after_reset,
        "guard_active": guard_active,
    }


def _held_candidate_from_anchor(
    *,
    anchor: float,
    prev_score: float,
    side: OptionType,
    spot: float | None,
) -> _ScoredStrike:
    distance_pct = 0.0
    if spot is not None and spot > 0:
        distance_pct = abs(anchor - spot) / spot
    return _ScoredStrike(
        strike=float(anchor),
        score=float(prev_score),
        oi=0.0,
        doi=0.0,
        vol=0.0,
        distance_pct=distance_pct,
        side=side,
    )


def _normalize_scores(values: list[float]) -> list[float]:
    if not values:
        return []
    lo = min(values)
    hi = max(values)
    if hi <= lo:
        return [1.0 for _ in values]
    return [max(0.0, min(1.0, (v - lo) / (hi - lo))) for v in values]


def _build_scored_rows(rows: list[dict[str, Any]], side: OptionType, spot: float | None) -> list[_ScoredStrike]:
    raw_list: list[tuple[dict[str, Any], float, float, float, float]] = []
    strikes = [_to_float(row.get("strike"), 0.0) for row in rows]
    if strikes:
        min_strike = min(strikes)
        max_strike = max(strikes)
        max_strike_range = max(1.0, max_strike - min_strike)
    else:
        max_strike_range = 1.0

    for row in rows:
        strike = _to_float(row.get("strike"), 0.0)
        _, oi, doi, vol = _compute_raw_score(row, side)
        if spot is not None:
            proximity = 1.0 - (abs(strike - spot) / max_strike_range)
            proximity = max(0.0, min(1.0, proximity))
        else:
            proximity = 0.0
        raw_list.append((row, oi, doi, vol, proximity))

    normalized_oi = _normalize_scores([item[1] for item in raw_list])
    normalized_doi = _normalize_scores([item[2] for item in raw_list])
    scored: list[_ScoredStrike] = []
    for idx, (row, oi, doi, vol, proximity) in enumerate(raw_list):
        strike = _to_float(row.get("strike"), 0.0)
        distance_pct = 999.0
        if spot is not None and spot > 0:
            distance_pct = abs(strike - spot) / spot
        strike_strength = (0.5 * normalized_oi[idx]) + (0.3 * normalized_doi[idx]) + (0.2 * proximity)
        scored.append(
            _ScoredStrike(
                strike=strike,
                score=round(max(0.0, min(1.0, strike_strength)), 6),
                oi=oi,
                doi=doi,
                vol=vol,
                distance_pct=distance_pct,
                side=side,
                normalized_oi=round(normalized_oi[idx], 6),
                normalized_doi=round(normalized_doi[idx], 6),
                proximity_to_spot=round(proximity, 6),
            )
        )
    return scored


def _top_levels(scored: list[_ScoredStrike]) -> list[dict[str, Any]]:
    ordered = sorted(scored, key=lambda x: x.score, reverse=True)[:5]
    return [{"strike": item.strike, "score": round(item.score * 100, 2)} for item in ordered]


def _trace_candidates(stage: str, side: OptionType, candidates: list[_ScoredStrike], *, reasons: dict[float, str] | None = None) -> None:
    ordered = sorted(candidates, key=lambda x: x.score, reverse=True)[:5]
    payload = [
        {
            "strike": item.strike,
            "normalized_oi": round(item.normalized_oi, 4),
            "normalized_oi_change": round(item.normalized_doi, 4),
            "proximity_to_spot": round(item.proximity_to_spot, 4),
            "total_score": round(item.score, 6),
            "distance_pct": round(item.distance_pct, 6),
            "rejection_reason": (reasons or {}).get(item.strike),
        }
        for item in ordered
    ]
    logger.debug("SRTrace[%s][%s] %s", side, stage, payload)


def _pick_major(scored: list[_ScoredStrike]) -> _ScoredStrike | None:
    if not scored:
        return None
    return max(scored, key=lambda x: x.score)


def _immediate_distance_pct_limit(symbol: str | None) -> float:
    text = str(symbol or "").strip().upper()
    if "SENSEX" in text:
        return 0.008  # 0.8%
    if "BANKNIFTY" in text or text == "BANK NIFTY":
        return 0.012  # 1.2%
    if "FINNIFTY" in text or text == "FIN NIFTY":
        return 0.010  # 1.0%
    if "NIFTY" in text:
        return 0.010  # 1.0%
    return 0.010


def _pick_immediate(
    scored: list[_ScoredStrike],
    spot: float | None,
    side: OptionType,
    *,
    symbol: str | None = None,
) -> _ScoredStrike | None:
    if not scored or spot is None or spot <= 0:
        return None

    _trace_candidates("raw_score_ranking", side, scored)

    directional: list[_ScoredStrike] = []
    directional_reasons: dict[float, str] = {}
    for item in scored:
        allowed = item.strike > spot if side == "CE" else item.strike < spot
        if allowed:
            directional.append(item)
        else:
            directional_reasons[item.strike] = "failed_spot_constraint"
    if not directional:
        logger.debug("SRTrace[%s][directional_filter] no candidates after spot constraint", side)
        return None
    _trace_candidates("after_spot_constraint", side, directional, reasons=directional_reasons)

    max_distance_pct = _immediate_distance_pct_limit(symbol)
    zone = [s for s in directional if s.distance_pct <= max_distance_pct]
    zone_reasons: dict[float, str] = {
        item.strike: f"above_max_distance_{round(max_distance_pct * 100.0, 2)}pct"
        for item in directional
        if item not in zone
    }
    stage = f"after_zone_filter_le_{round(max_distance_pct * 100.0, 2)}pct"
    if not zone:
        zone = directional
        stage = "after_zone_filter_full_directional_fallback"
        zone_reasons = {}

    _trace_candidates(stage, side, zone, reasons=zone_reasons)

    chosen = max(zone, key=lambda x: x.score) if zone else None
    if chosen is None:
        return None
    logger.debug(
        "SRTrace[%s][final_immediate] chosen=%s score=%.6f distance_pct=%.6f major_candidate=%s",
        side,
        chosen.strike,
        chosen.score,
        chosen.distance_pct,
        max(scored, key=lambda x: x.score).strike if scored else None,
    )
    return chosen


def _apply_level_hysteresis(
    *,
    side: OptionType,
    immediate: _ScoredStrike | None,
    scored: list[_ScoredStrike],
    previous_state: dict[str, Any] | None,
    spot: float | None,
    debug_state: dict[str, Any] | None = None,
    score_margin: float = 0.18,
    oi_margin: float = 0.15,
    resistance_upward_buffer: float = 25.0,
    support_downward_buffer: float = 25.0,
) -> _ScoredStrike | None:
    if immediate is None:
        return None

    prev_levels = (previous_state or {}).get("levels", {})
    side_key = "resistance" if side == "CE" else "support"
    prev_obj = prev_levels.get(side_key, {}) if isinstance(prev_levels, dict) else {}
    cold_start = _resolve_sr_cold_start_anchor(previous_state, side)
    prev_immediate = _to_float(cold_start.get("anchor"), 0.0)
    prev_score = _to_float((prev_obj.get("immediate_score") if isinstance(prev_obj, dict) else None), 0.0)
    if isinstance(debug_state, dict):
        debug_state["first_cycle_after_reset"] = bool(cold_start.get("first_cycle_after_reset"))
        debug_state["anchor_used"] = float(prev_immediate) if prev_immediate > 0 else None
        debug_state["used_top_level"] = bool(cold_start.get("used_top_level"))
        debug_state["guard_active"] = bool(cold_start.get("guard_active"))
        debug_state["guard_applied"] = False
        debug_state["buffer_blocked"] = False

    if prev_immediate <= 0:
        return immediate
    if abs(immediate.strike - prev_immediate) < 1e-6:
        return immediate

    prev_candidate = next((item for item in scored if abs(item.strike - prev_immediate) < 1e-6), None)
    used_synthetic_anchor = False
    if prev_candidate is None:
        if not bool(cold_start.get("guard_active")):
            return immediate
        prev_candidate = _held_candidate_from_anchor(
            anchor=float(prev_immediate),
            prev_score=float(prev_score),
            side=side,
            spot=spot,
        )
        used_synthetic_anchor = True
        if isinstance(debug_state, dict):
            debug_state["guard_applied"] = True

    if spot is not None:
        if side == "CE" and immediate.strike > prev_candidate.strike and spot < (prev_candidate.strike + resistance_upward_buffer):
            if isinstance(debug_state, dict):
                debug_state["buffer_blocked"] = True
                debug_state["guard_applied"] = True
            logger.debug(
                "SRTrace[%s][buffer_hold] prev=%s current=%s spot=%.2f required_spot=%.2f",
                side,
                prev_candidate.strike,
                immediate.strike,
                spot,
                prev_candidate.strike + resistance_upward_buffer,
            )
            return prev_candidate
        if side == "PE" and immediate.strike > prev_candidate.strike:
            logger.debug(
                "SRTrace[%s][free_upward_support] prev=%s current=%s spot=%.2f",
                side,
                prev_candidate.strike,
                immediate.strike,
                spot,
            )
            return immediate
        if side == "PE" and immediate.strike < prev_candidate.strike and spot > (prev_candidate.strike - support_downward_buffer):
            if isinstance(debug_state, dict):
                debug_state["buffer_blocked"] = True
                debug_state["guard_applied"] = True
            logger.debug(
                "SRTrace[%s][buffer_hold] prev=%s current=%s spot=%.2f required_spot=%.2f",
                side,
                prev_candidate.strike,
                immediate.strike,
                spot,
                prev_candidate.strike - support_downward_buffer,
            )
            return prev_candidate
        prev_is_directional = prev_candidate.strike > spot if side == "CE" else prev_candidate.strike < spot
        if not prev_is_directional:
            return immediate

    baseline_score = max(prev_score, prev_candidate.score)
    current_score_gain = (immediate.score / max(1e-9, baseline_score)) - 1.0
    current_oi_gain = (immediate.oi / max(1.0, prev_candidate.oi)) - 1.0

    if side in {"CE", "PE"}:
        if current_oi_gain >= oi_margin:
            return immediate
    elif current_score_gain >= score_margin or current_oi_gain >= oi_margin:
        return immediate

    logger.debug(
        "SRTrace[%s][hysteresis_hold] prev=%s prev_score=%.6f current=%s current_score=%.6f score_gain=%.4f oi_gain=%.4f",
        side,
        prev_candidate.strike,
        baseline_score,
        immediate.strike,
        immediate.score,
        current_score_gain,
        current_oi_gain,
    )
    if used_synthetic_anchor and isinstance(debug_state, dict):
        debug_state["guard_applied"] = True
    return prev_candidate


def _resolve_display_candidate(
    *,
    side: OptionType,
    immediate: _ScoredStrike | None,
    major: _ScoredStrike | None,
    scored: list[_ScoredStrike],
    previous_state: dict[str, Any] | None,
    spot: float | None,
    resistance_upward_buffer: float = 25.0,
    support_downward_buffer: float = 25.0,
) -> _ScoredStrike | None:
    candidate = immediate or major
    if candidate is None:
        return None

    prev_levels = (previous_state or {}).get("levels", {})
    side_key = "resistance" if side == "CE" else "support"
    prev_obj = prev_levels.get(side_key, {}) if isinstance(prev_levels, dict) else {}
    cold_start = _resolve_sr_cold_start_anchor(previous_state, side)
    prev_immediate = _to_float(cold_start.get("anchor"), 0.0)
    prev_score = _to_float((prev_obj.get("immediate_score") if isinstance(prev_obj, dict) else None), 0.0)

    if prev_immediate <= 0 or abs(candidate.strike - prev_immediate) < 1e-6:
        return candidate

    prev_candidate = next((item for item in scored if abs(item.strike - prev_immediate) < 1e-6), None)
    held_candidate = prev_candidate or _ScoredStrike(
        strike=float(prev_immediate),
        score=float(prev_score),
        oi=0.0,
        doi=0.0,
        vol=0.0,
        distance_pct=0.0,
        side=side,
    )

    if spot is not None:
        if side == "CE" and candidate.strike > held_candidate.strike and spot < (held_candidate.strike + resistance_upward_buffer):
            logger.debug(
                "SRTrace[%s][display_buffer_hold] prev=%s current=%s spot=%.2f required_spot=%.2f",
                side,
                held_candidate.strike,
                candidate.strike,
                spot,
                held_candidate.strike + resistance_upward_buffer,
            )
            return held_candidate
        if side == "PE" and candidate.strike < held_candidate.strike and spot > (held_candidate.strike - support_downward_buffer):
            logger.debug(
                "SRTrace[%s][display_buffer_hold] prev=%s current=%s spot=%.2f required_spot=%.2f",
                side,
                held_candidate.strike,
                candidate.strike,
                spot,
                held_candidate.strike - support_downward_buffer,
            )
            return held_candidate
    return candidate


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
    previous_state = _hydrate_previous_sr_state(previous_state)
    rows = features.get("rows", []) or []
    symbol = str(features.get("meta", {}).get("symbol") or "").strip()
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
    logger.debug("SRTrace[PE][major_support] chosen=%s score=%.6f", major_sup.strike if major_sup else None, major_sup.score if major_sup else 0.0)
    logger.debug("SRTrace[CE][major_resistance] chosen=%s score=%.6f", major_res.strike if major_res else None, major_res.score if major_res else 0.0)
    immediate_res = _pick_immediate(ce_scored, spot_num, "CE", symbol=symbol)
    immediate_sup = _pick_immediate(pe_scored, spot_num, "PE", symbol=symbol)
    support_hysteresis_debug: dict[str, Any] = {}
    resistance_hysteresis_debug: dict[str, Any] = {}
    immediate_res = _apply_level_hysteresis(
        side="CE",
        immediate=immediate_res,
        scored=ce_scored,
        previous_state=previous_state,
        spot=spot_num,
        debug_state=resistance_hysteresis_debug,
    )
    immediate_sup = _apply_level_hysteresis(
        side="PE",
        immediate=immediate_sup,
        scored=pe_scored,
        previous_state=previous_state,
        spot=spot_num,
        debug_state=support_hysteresis_debug,
    )

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

    display_res = _resolve_display_candidate(
        side="CE",
        immediate=immediate_res,
        major=major_res,
        scored=ce_scored,
        previous_state=previous_state,
        spot=spot_num,
    )
    display_sup = _resolve_display_candidate(
        side="PE",
        immediate=immediate_sup,
        major=major_sup,
        scored=pe_scored,
        previous_state=previous_state,
        spot=spot_num,
    )

    resistance_immediate = display_res.strike if display_res is not None else None
    support_immediate = display_sup.strike if display_sup is not None else None
    support_row = _find_strike_row(rows, support_immediate)
    resistance_row = _find_strike_row(rows, resistance_immediate)
    support_defense_score = None
    resistance_defense_score = None
    if support_row is not None:
        support_defense_score = round(
            _to_float(support_row.get("PE_OI"), 0.0) / max(_to_float(support_row.get("CE_OI"), 0.0), 1.0),
            2,
        )
    if resistance_row is not None:
        resistance_defense_score = round(
            _to_float(resistance_row.get("CE_OI"), 0.0) / max(_to_float(resistance_row.get("PE_OI"), 0.0), 1.0),
            2,
        )
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

    logger.debug(
        "SRTrace[return] support_immediate=%s support_major=%s support_frontend=%s resistance_immediate=%s resistance_major=%s resistance_frontend=%s support_center=%s resistance_center=%s",
        support_immediate,
        major_sup.strike if major_sup else None,
        support_immediate,
        resistance_immediate,
        major_res.strike if major_res else None,
        resistance_immediate,
        support_zone.get("center"),
        resistance_zone.get("center"),
    )

    return {
        # Backward compatible fields: strike/score default to immediate levels.
        "resistance": {
            "strike": resistance_immediate,
            "score": round((display_res.score if display_res else 0.0) * 100, 2),
            "immediate": resistance_immediate,
            "major": major_res.strike if major_res else None,
            "defense_score": resistance_defense_score,
            "immediate_score": round(display_res.score if display_res else 0.0, 6),
            "major_score": round(major_res.score if major_res else 0.0, 6),
            "levels": _top_levels(ce_scored),
        },
        "support": {
            "strike": support_immediate,
            "score": round((display_sup.score if display_sup else 0.0) * 100, 2),
            "immediate": support_immediate,
            "major": major_sup.strike if major_sup else None,
            "defense_score": support_defense_score,
            "immediate_score": round(display_sup.score if display_sup else 0.0, 6),
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
        "sr_first_cycle_after_reset": bool(
            support_hysteresis_debug.get("first_cycle_after_reset")
            or resistance_hysteresis_debug.get("first_cycle_after_reset")
        ),
        "sr_cold_start_guard_applied": bool(
            support_hysteresis_debug.get("guard_applied") or resistance_hysteresis_debug.get("guard_applied")
        ),
        "sr_previous_support_anchor_used": support_hysteresis_debug.get("anchor_used"),
        "sr_previous_resistance_anchor_used": resistance_hysteresis_debug.get("anchor_used"),
        "sr_support_buffer_blocked": bool(support_hysteresis_debug.get("buffer_blocked")),
        "sr_resistance_buffer_blocked": bool(resistance_hysteresis_debug.get("buffer_blocked")),
        "alerts": alerts,
    }
