from __future__ import annotations

import asyncio
import logging
import os
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any

from app.core.cache import cache
from app.engines.breakout_engine import run_breakout_engine
from app.engines.auto_exit_suggestion_engine import generate_auto_exit_suggestion
from app.engines.adaptive_weighting_engine import compute_adaptive_weights
from app.engines.bias_stability_engine import compute_bias_stability
from app.engines.decision_engine import run_decision_engine_v3
from app.engines.expiry_mode_engine import run_expiry_adaptive_mode
from app.engines.exhaustion_trap_combo_engine import detect_exhaustion_trap_combo
from app.engines.early_reversal_probability_engine import compute_early_reversal_probability
from app.engines.oi_analyzer import run_oi_analysis
from app.engines.momentum_exhaustion_engine import detect_momentum_exhaustion
from app.engines.preprocessing import build_feature_frame, normalize_chain
from app.engines.regime_engine import run_regime_engine
from app.engines.regime_shift_engine import detect_regime_shift
from app.engines.signal_priority_engine import prioritize_signals
from app.engines.sr_engine import run_sr_engine
from app.engines.target_engine import run_target_engine
from app.engines.trade_plan_engine import generate_trade_plan
from app.engines.trap_engine import adjust_trap_by_confidence, run_trap_engine
from app.engines.volume_analyzer import run_volume_analysis
from app.services.decision_engine import build_decision_input, master_decision_engine
from app.services.intraday_performance_tracker import tracker
from app.services.nse_client import fetch_index_data, fetch_option_chain, fetch_option_chain_contract_info
from app.services.parser import build_oi_volume_summary, build_target_projection

logger = logging.getLogger("optionlens.background_updater")

REFRESH_SECONDS = int(os.getenv("OPTIONLENS_REFRESH_SECONDS", "15"))
STALE_AFTER_SECONDS = int(os.getenv("OPTIONLENS_STALE_AFTER_SECONDS", "60"))
SYMBOLS = [s.strip().upper() for s in os.getenv("OPTIONLENS_SYMBOLS", "NIFTY,BANKNIFTY,FINNIFTY").split(",") if s.strip()]
INSTRUMENT_TYPE = os.getenv("OPTIONLENS_INSTRUMENT_TYPE", "Indices")
MAX_EXPIRIES_PER_SYMBOL = max(1, int(os.getenv("OPTIONLENS_PREFETCH_EXPIRIES", "3")))
ATR_ROLLING_WINDOW = max(5, int(os.getenv("OPTIONLENS_ATR_ROLLING_WINDOW", "40")))
ATR_MIN_SAMPLES = max(3, int(os.getenv("OPTIONLENS_ATR_MIN_SAMPLES", "5")))
ATR_MIN_SAMPLES = min(ATR_MIN_SAMPLES, ATR_ROLLING_WINDOW)
ADAPTIVE_RECALC_MINUTES = max(30, int(os.getenv("OPTIONLENS_ADAPTIVE_RECALC_MINUTES", "30")))

# Rolling ATR history per symbol+expiry to stabilize confidence.
_atr_history: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=ATR_ROLLING_WINDOW))


def _utc_iso(dt: datetime | None) -> str | None:
    if not dt:
        return None
    return dt.astimezone(timezone.utc).isoformat()


def _cache_key(symbol: str, instrument_type: str, expiry: str | None) -> str:
    return f"{instrument_type.upper()}::{symbol.upper()}::{expiry or 'AUTO'}"


def _parse_timestamp_utc(text: str | None) -> datetime:
    if not text:
        return datetime.now(timezone.utc)
    for fmt in ("%d-%b-%Y %H:%M:%S", "%d-%b-%Y %H:%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return datetime.now(timezone.utc)


def _atr_key(symbol: str, expiry: str | None) -> str:
    return f"{symbol.upper()}::{expiry or 'AUTO'}"


def _update_and_get_avg_atr(symbol: str, expiry: str | None, atr_value: float) -> float | None:
    key = _atr_key(symbol, expiry)
    if atr_value > 0:
        _atr_history[key].append(float(atr_value))

    series = _atr_history.get(key)
    if not series or len(series) < ATR_MIN_SAMPLES:
        return None
    return float(sum(series) / len(series))


async def _fetch_option_chain_async(symbol: str, expiry: str | None, instrument_type: str) -> dict[str, Any]:
    return await asyncio.to_thread(fetch_option_chain, symbol, expiry, instrument_type)


async def _fetch_contract_info_async(symbol: str) -> dict[str, Any]:
    return await asyncio.to_thread(fetch_option_chain_contract_info, symbol)


async def _fetch_index_data_async() -> dict[str, Any]:
    return await asyncio.to_thread(fetch_index_data)


def _run_ordered_pipeline(
    *,
    features: dict[str, Any],
    symbol: str,
    expiry: str | None,
    previous_score: float | None,
    last_10_scores: list[float] | None,
) -> dict[str, Any]:
    """
    Enforced execution order to avoid circular dependencies:
    preprocessing -> feature engines -> regime -> trap -> arbitration/decision -> trade plan.
    This helper runs the stages up to regime-adjusted feature outputs.
    """
    # Stage 1: Feature engines
    oi = run_oi_analysis(features)
    sr = run_sr_engine(features)
    base_volume = run_volume_analysis(features)
    base_breakout = run_breakout_engine(features, sr)
    base_trap = run_trap_engine(features, base_breakout, oi, base_volume)

    # Stage 2: Regime from base features
    atr_threshold_for_regime = float(base_breakout.get("atr_threshold") or 0.0)
    avg_atr_for_regime = _update_and_get_avg_atr(symbol=symbol, expiry=expiry, atr_value=atr_threshold_for_regime)
    if not avg_atr_for_regime or avg_atr_for_regime <= 0:
        avg_atr_for_regime = float(features.get("atr_proxy") or 1.0)
    atr_ratio = atr_threshold_for_regime / max(1e-9, float(avg_atr_for_regime))
    regime = run_regime_engine(
        oi,
        base_volume,
        base_breakout,
        base_trap,
        context={
            "atr_ratio": atr_ratio,
            "score": float(previous_score or 0.0),
            "last_10_scores": list(last_10_scores or []),
            "breakout_confirmed": bool(base_breakout.get("breakout_up") or base_breakout.get("breakout_down")),
        },
    )

    # Stage 3: Recompute sensitive engines with regime-adjusted thresholds
    pre_adjusted_thresholds = regime.get("adjusted_thresholds", {})
    volume_threshold = float(pre_adjusted_thresholds.get("volume_expansion_threshold", 1.2) or 1.2)
    breakout_atr_multiplier = float(pre_adjusted_thresholds.get("breakout_atr_multiplier", 1.2) or 1.2)

    volume = run_volume_analysis(features, expansion_threshold=volume_threshold)
    breakout = run_breakout_engine(features, sr, atr_multiplier=breakout_atr_multiplier)
    trap = run_trap_engine(features, breakout, oi, volume)
    regime = run_regime_engine(oi, volume, breakout, trap)

    return {
        "oi": oi,
        "sr": sr,
        "volume": volume,
        "breakout": breakout,
        "trap": trap,
        "regime": regime,
        "adjusted_thresholds": regime.get("adjusted_thresholds", pre_adjusted_thresholds),
    }


def _build_v2_intelligence(
    rows: list[dict[str, Any]],
    spot: float | None,
    symbol: str,
    expiry: str | None,
    timestamp: str | None,
    previous_score: float | None = None,
    last_10_scores: list[float] | None = None,
    previous_bias_score: float | None = None,
    previous_regime: str | None = None,
    previous_alignment: float | None = None,
    previous_atr_ratio: float | None = None,
    previous_volume_ratio: float | None = None,
    previous_oi_delta: float | None = None,
    adaptive_state: dict[str, Any] | None = None,
    total_signals_logged: int = 0,
    engine_stats: dict[str, float] | None = None,
    evaluation_time: datetime | None = None,
) -> dict[str, Any]:
    normalized = normalize_chain(rows)
    features = build_feature_frame(
        normalized,
        spot=spot,
        symbol=symbol,
        expiry=expiry,
        timestamp=timestamp,
    )

    pipeline = _run_ordered_pipeline(
        features=features,
        symbol=symbol,
        expiry=expiry,
        previous_score=previous_score,
        last_10_scores=last_10_scores,
    )
    oi = pipeline["oi"]
    sr = pipeline["sr"]
    volume = pipeline["volume"]
    breakout = pipeline["breakout"]
    trap = pipeline["trap"]
    regime = pipeline["regime"]
    adjusted_thresholds = pipeline["adjusted_thresholds"]

    atr_threshold = float(breakout.get("atr_threshold") or 0.0)
    avg_atr = _update_and_get_avg_atr(symbol=symbol, expiry=expiry, atr_value=atr_threshold)
    if avg_atr is None or avg_atr <= 0:
        avg_atr = float(features.get("atr_proxy") or 1.0)
    current_atr_ratio = float(atr_threshold / max(1e-9, avg_atr))
    volatility_state = "Expanding" if current_atr_ratio > 1.2 else "Contracting" if current_atr_ratio < 0.8 else "Stable"

    oi_alignment = str(oi.get("alignment", "mixed"))
    oi_strength = max(0.0, min(1.0, float(oi.get("oi_strength", 0.0) or 0.0)))
    oi_score = oi_strength if oi_alignment == "bullish" else (-oi_strength if oi_alignment == "bearish" else 0.0)

    rvr_ce = max(0.0, min(1.0, float(volume.get("rvr", {}).get("ce", 0.0) or 0.0)))
    rvr_pe = max(0.0, min(1.0, float(volume.get("rvr", {}).get("pe", 0.0) or 0.0)))
    volume_score = max(-1.0, min(1.0, rvr_pe - rvr_ce))
    breakout_score = 1.0 if breakout.get("breakout_up") else -1.0 if breakout.get("breakout_down") else 0.0

    support_score = float(sr.get("support", {}).get("score") or 0.0)
    resistance_score = float(sr.get("resistance", {}).get("score") or 0.0)
    sr_score = max(-1.0, min(1.0, (support_score - resistance_score) / 100.0))
    trap_penalty = max(0.0, min(1.0, float(trap.get("trap_probability_pct", 0) or 0) / 100.0))

    directional_scores = [oi_score, volume_score, breakout_score, sr_score]
    mean_dir = sum(directional_scores) / max(1, len(directional_scores))
    dominant_sign = 1 if mean_dir > 0 else -1 if mean_dir < 0 else 0
    aligned = 0
    for s in directional_scores:
        sign_s = 1 if s > 0 else -1 if s < 0 else 0
        if dominant_sign != 0 and sign_s == dominant_sign:
            aligned += 1
    current_alignment = aligned / max(1, len(directional_scores))

    bias_stability = compute_bias_stability(last_10_scores)
    now_dt = evaluation_time or datetime.now(timezone.utc)
    base_weights = {"oi": 0.30, "volume": 0.25, "breakout": 0.20, "sr": 0.15}
    state = adaptive_state or {}
    current_weights = state.get("weights") if isinstance(state.get("weights"), dict) else base_weights
    session_start_raw = state.get("session_start_utc")
    try:
        session_start_dt = (
            datetime.fromisoformat(session_start_raw)
            if isinstance(session_start_raw, str)
            else now_dt
        )
        if session_start_dt.tzinfo is None:
            session_start_dt = session_start_dt.replace(tzinfo=timezone.utc)
    except Exception:
        session_start_dt = now_dt
    elapsed_minutes = max(0.0, (now_dt - session_start_dt).total_seconds() / 60.0)
    allow_adaptation = (total_signals_logged >= 5) or (elapsed_minutes >= 60.0)
    if not allow_adaptation:
        current_weights = base_weights
    last_recalc_raw = state.get("last_recalc_utc")
    try:
        last_recalc_dt = (
            datetime.fromisoformat(last_recalc_raw)
            if isinstance(last_recalc_raw, str)
            else None
        )
        if last_recalc_dt and last_recalc_dt.tzinfo is None:
            last_recalc_dt = last_recalc_dt.replace(tzinfo=timezone.utc)
    except Exception:
        last_recalc_dt = None
    recalc_due = (
        allow_adaptation
        and (
            last_recalc_dt is None
            or ((now_dt - last_recalc_dt).total_seconds() / 60.0) >= ADAPTIVE_RECALC_MINUTES
        )
    )
    if recalc_due:
        effective_stats = engine_stats or {
            "oi_accuracy": 0.55,
            "volume_accuracy": 0.55,
            "breakout_accuracy": 0.55,
            "sr_accuracy": 0.55,
        }
        current_weights = compute_adaptive_weights(
            engine_stats=effective_stats,
            current_weights=current_weights,
        ).get("adaptive_weights", current_weights)

    decision_v3 = run_decision_engine_v3(
        oi_score=oi_score,
        volume_score=volume_score,
        breakout_score=breakout_score,
        sr_score=sr_score,
        trap_penalty=trap_penalty,
        alignment_ratio=current_alignment,
        bias_stability_score=float(bias_stability.get("bias_stability_score", 55) or 55),
        weights=current_weights,
    )
    current_regime = str(regime.get("regime_type") or regime.get("regime") or "Transition")
    regime_mapped = (
        "Trend"
        if current_regime in ("Trend", "Trend Day", "Breakdown")
        else "Range"
        if current_regime in ("Range", "Range Day")
        else "Transition"
    )
    decision = {
        "bias": decision_v3["bias"],
        "bull_probability": decision_v3["bull_probability"],
        "bear_probability": decision_v3["bear_probability"],
        "confidence": decision_v3["confidence"],
        "weighted_score": decision_v3["composite_score"],
        "composite_score": decision_v3["composite_score"],
        "alignment_ratio": round(current_alignment, 4),
        "volatility_ratio": round(current_atr_ratio, 4),
        "volatility_state": volatility_state,
        "regime": regime_mapped,
        "weight_distribution": decision_v3.get("weight_distribution", base_weights),
    }
    target = run_target_engine(features, sr, breakout, oi, trap, volume, decision=decision, regime=regime)
    support_level = sr.get("support", {}).get("strike")
    resistance_level = sr.get("resistance", {}).get("strike")
    strongest_oi_strike = support_level
    if resistance_score > support_score:
        strongest_oi_strike = resistance_level
    expiry_adaptive = run_expiry_adaptive_mode(
        expiry=expiry,
        spot=spot,
        support=support_level,
        resistance=resistance_level,
        expected_move=target.get("expected_move"),
        bias=str((decision or {}).get("bias", "Neutral")),
        trap_risk=trap.get("trap_probability_pct", 0),
        session_phase=target.get("session_phase"),
        strongest_oi_strike=strongest_oi_strike,
        strike_gap=features.get("strike_gap"),
    )
    target["target_1"] = expiry_adaptive["target1"]
    target["target_2"] = expiry_adaptive["target2"]
    target["target1"] = expiry_adaptive["target1"]
    target["target2"] = expiry_adaptive["target2"]
    target["adjustedMove"] = expiry_adaptive["adjustedMove"]
    target["expiry_multiplier"] = expiry_adaptive["expiry_multiplier"]
    target["expiry_mode"] = expiry_adaptive["expiry_mode"]

    bias_score = float(decision.get("bull_probability", 0.5) or 0.5) * 100.0
    prev_bias_score = float(previous_bias_score) if previous_bias_score is not None else None
    if prev_bias_score is not None and abs(bias_score - prev_bias_score) < 5.0:
        if prev_bias_score > 55:
            stable_bias = "Bullish"
        elif prev_bias_score < 45:
            stable_bias = "Bearish"
        else:
            stable_bias = "Neutral"
    else:
        stable_bias = str(decision.get("bias", "Neutral"))
    trap_conf_adj = adjust_trap_by_confidence(
        base_trap=float(trap.get("trap_probability_pct", 0) or 0),
        smoothed_score=float(decision.get("weighted_score", 0.0) or 0.0),
        confidence_percent=float(decision.get("confidence", 0) or 0),
    )
    trap["trap_probability_pct"] = int(trap_conf_adj["trap_probability"])
    trap["trap_risk"] = int(trap_conf_adj["trap_probability"])
    trap["confidence_factor"] = float(trap_conf_adj["confidence_factor"])
    trap["is_trap"] = bool(trap["trap_probability_pct"] >= 60)

    weighted_score = float(decision.get("weighted_score", 0.0) or 0.0)
    current_alignment = float(decision.get("alignment_ratio", 0.0) or 0.0)
    current_atr_ratio = float(decision.get("volatility_ratio", 1.0) or 1.0)
    current_regime = str(decision.get("regime", "Range"))
    atm_row = features.get("atm_row") or {}
    rows = features.get("rows") or []
    atm_total_volume = float(atm_row.get("CE_Volume", 0.0) or 0.0) + float(atm_row.get("PE_Volume", 0.0) or 0.0)
    avg_total_volume = (
        sum(float(r.get("CE_Volume", 0.0) or 0.0) + float(r.get("PE_Volume", 0.0) or 0.0) for r in rows) / max(1, len(rows))
    )
    current_volume_ratio = atm_total_volume / max(1.0, avg_total_volume)
    current_oi_delta = abs(float(atm_row.get("CE_DeltaOI", 0.0) or 0.0)) + abs(
        float(atm_row.get("PE_DeltaOI", 0.0) or 0.0)
    )
    regime_shift = detect_regime_shift(
        previous_smoothed_score=float(previous_score or 0.0),
        current_smoothed_score=weighted_score,
        previous_regime=str(previous_regime or current_regime),
        current_regime=current_regime,
        previous_alignment=float(previous_alignment or 0.0),
        current_alignment=current_alignment,
        previous_atr_ratio=float(previous_atr_ratio or current_atr_ratio),
        current_atr_ratio=current_atr_ratio,
    )
    momentum_exhaustion = detect_momentum_exhaustion(
        smoothed_score=weighted_score,
        previous_smoothed_score=float(previous_score or 0.0),
        volume_ratio=current_volume_ratio,
        previous_volume_ratio=float(previous_volume_ratio or current_volume_ratio),
        oi_delta=current_oi_delta,
        previous_oi_delta=float(previous_oi_delta or current_oi_delta),
        atr_ratio=current_atr_ratio,
        previous_atr_ratio=float(previous_atr_ratio or current_atr_ratio),
    )
    combo_detector = detect_exhaustion_trap_combo(
        trap_risk=float(expiry_adaptive.get("trap_risk", trap.get("trap_probability_pct", 0)) or 0),
        momentum_exhaustion=bool(momentum_exhaustion.get("momentum_exhaustion")),
        confidence=float(decision.get("confidence", 50.0) or 50.0),
        volatility_state=str(decision.get("volatility_state", "Stable") or "Stable"),
    )
    resistance_strike = sr.get("resistance", {}).get("strike")
    support_strike = sr.get("support", {}).get("strike")
    breakout_up = bool(breakout.get("breakout_up"))
    breakout_down = bool(breakout.get("breakout_down"))
    strong_bias = abs(weighted_score) > 0.5
    dominant_direction = "up" if weighted_score > 0 else "down" if weighted_score < 0 else "neutral"

    alerts: list[dict[str, str]] = []
    suppression_reason_map: dict[str, str] = {}
    if breakout_up and resistance_strike is not None:
        alert = {"message": f"Breakout above {resistance_strike}", "direction": "up"}
        alerts.append(alert)

    if breakout_down and support_strike is not None:
        alert = {"message": f"Breakdown below {support_strike}", "direction": "down"}
        alerts.append(alert)

    regime_now = str(decision.get("regime", "") or "")
    projection_now = str(decision.get("projection", "") or "")
    is_range_no_breakout = regime_now == "Range" and projection_now.strip().lower() in {"no breakout", "range"}
    if is_range_no_breakout:
        downgraded: list[dict[str, str]] = []
        for alert in alerts:
            msg = str(alert.get("message", ""))
            if msg.lower().startswith("breakout above"):
                suppression_reason_map[f"alert:{msg}"] = "range_no_breakout_downgrade"
                downgraded.append({"message": msg.replace("Breakout above", "Low conviction breakout watch above"), "direction": "neutral"})
            elif msg.lower().startswith("breakdown below"):
                suppression_reason_map[f"alert:{msg}"] = "range_no_breakout_downgrade"
                downgraded.append({"message": msg.replace("Breakdown below", "Low conviction breakdown watch below"), "direction": "neutral"})
            else:
                downgraded.append(alert)
        alerts = downgraded

    typed_alerts: list[dict[str, str]] = []
    suppressed_counter = 0
    for alert in alerts:
        alert_type = "primary" if alert["direction"] == dominant_direction else "counter"
        if strong_bias and alert_type == "counter":
            suppressed_counter += 1
            suppression_reason_map[f"alert:{alert['message']}"] = "counter_trend_strong_bias"
            continue
        typed_alerts.append(
            {
                "message": alert["message"],
                "direction": alert["direction"],
                "type": alert_type,
            }
        )

    trap["trap_probability_pct"] = int(expiry_adaptive["trap_risk"])
    trap["trap_risk"] = int(expiry_adaptive["trap_risk"])
    reversal_prob = compute_early_reversal_probability(
        momentum_exhaustion=bool(momentum_exhaustion.get("momentum_exhaustion")),
        trap_risk=float(expiry_adaptive.get("trap_risk", trap.get("trap_probability_pct", 0)) or 0),
        bias_stability_score=float(bias_stability.get("bias_stability_score", 55) or 55),
        atr_ratio=float(current_atr_ratio),
        alignment_ratio=float(current_alignment),
    )
    auto_exit = generate_auto_exit_suggestion(
        bias=stable_bias,
        momentum_exhaustion=bool(momentum_exhaustion.get("momentum_exhaustion")),
        reversal_probability=float(reversal_prob.get("reversal_probability", 0) or 0),
        regime_shift_alert=bool(regime_shift.get("regime_shift_alert")),
        confidence=float(decision.get("confidence", 50.0) or 50.0),
    )
    reversal_risk = int(reversal_prob.get("reversal_probability", 0) or 0)
    candidate_signals: list[dict[str, Any]] = []
    if breakout_up or breakout_down:
        candidate_signals.append(
            {
                "type": "breakout",
                "base_priority": 80,
                "message": "Breakout setup active" if breakout_up else "Breakdown setup active",
            }
        )
    if abs(weighted_score) > 0.35 and current_alignment >= 0.5:
        candidate_signals.append(
            {
                "type": "trend_continuation",
                "base_priority": 75,
                "message": "Trend continuation structure",
            }
        )
    if bool(momentum_exhaustion.get("momentum_exhaustion")):
        candidate_signals.append(
            {
                "type": "exhaustion",
                "base_priority": 70,
                "message": str(momentum_exhaustion.get("exhaustion_type") or "Momentum exhaustion"),
            }
        )
    if bool(trap.get("trap_probability_pct", 0) >= 60):
        candidate_signals.append(
            {
                "type": "trap_warning",
                "base_priority": 72,
                "message": "Trap risk elevated",
            }
        )
    if bool(auto_exit.get("exit_signal")):
        candidate_signals.append(
            {
                "type": "exit_signal",
                "base_priority": 78,
                "message": str(auto_exit.get("exit_reason") or "Consider protecting open gains"),
            }
        )
    prioritized = prioritize_signals(
        signals=candidate_signals,
        confidence=float(decision.get("confidence", 50.0) or 50.0),
        regime=str(decision.get("regime", "Range") or "Range"),
        projection=str(decision.get("projection", "") or ""),
        expiry_mode=bool(expiry_adaptive.get("expiry_mode")),
        session_phase=str(target.get("session_phase", "Transition") or "Transition"),
        reversal_probability=float(reversal_prob.get("reversal_probability", 0) or 0),
    )
    suppression_reason_map.update(
        {
            f"signal:{k}": v
            for k, v in (prioritized.get("suppression_reason_map", {}) or {}).items()
            if isinstance(k, str) and isinstance(v, str)
        }
    )
    engine_scores = decision.get("engine_scores", {}) if isinstance(decision.get("engine_scores"), dict) else {}
    weight_distribution = (
        decision.get("weight_distribution", {})
        if isinstance(decision.get("weight_distribution"), dict)
        else {}
    )
    engine_debug_map: dict[str, dict[str, float]] = {}
    for key in ("oi", "volume", "breakout", "sr"):
        if key not in engine_scores or key not in weight_distribution:
            continue
        raw_score = float(engine_scores.get(key, 0.0))
        weight = float(weight_distribution.get(key, 0.0))
        engine_debug_map[key] = {
            "raw_score": round(raw_score, 4),
            "weight": round(weight, 4),
            "contribution": round(raw_score * weight, 4),
        }
    logger.debug(
        "Decision[%s %s] composite=%.4f smoothed=%.4f bias=%s conf=%.1f engine_map=%s",
        symbol,
        expiry or "AUTO",
        float(decision.get("composite_score", 0.0) or 0.0),
        float(decision.get("weighted_score", 0.0) or 0.0),
        stable_bias,
        float(decision.get("confidence", 0.0) or 0.0),
        engine_debug_map,
    )
    logger.debug(
        "Alerts[%s %s] dominant=%s strong_bias=%s suppressed_counter=%d emitted=%d prioritized=%d suppression_reasons=%s",
        symbol,
        expiry or "AUTO",
        dominant_direction,
        strong_bias,
        suppressed_counter,
        len(typed_alerts),
        len(prioritized.get("prioritized_signals", [])),
        suppression_reason_map,
    )
    summary_line = (
        f"Put writers defending {support_level}; upside momentum building."
        if stable_bias == "Bullish"
        else f"Call writers active near {resistance_level}; downside pressure holding."
        if stable_bias == "Bearish"
        else f"Price balancing between {support_level} and {resistance_level}; wait for cleaner move."
    )
    trade_plan = generate_trade_plan(
        bias=stable_bias,
        probability_bull=float((decision.get("bull_probability", 0.5) or 0.5) * 100.0),
        confidence=float(decision.get("confidence", 50.0) or 50.0),
        support=support_level,
        resistance=resistance_level,
        target1=target.get("target_1"),
        target2=target.get("target_2"),
        trap_risk=int(expiry_adaptive["trap_risk"] or 0),
        volatility_state=decision.get("volatility_state"),
    )

    return {
        "meta": features["meta"],
        "_internal": {
            "smoothed_score": decision.get("weighted_score"),
        },
        "market_state": {
            "volatility_state": decision.get("volatility_state"),
            "bias": stable_bias,
            "probability_bull": round(float((decision.get("bull_probability", 0.5) or 0.5) * 100.0), 2),
            "probability_bear": round(float((decision.get("bear_probability", 0.5) or 0.5) * 100.0), 2),
            "confidence": float(decision.get("confidence", 50.0) or 50.0),
            "composite_score": float(decision.get("composite_score", 0.0) or 0.0),
            "adaptive_mode": "Active" if allow_adaptation else "Base",
            "adaptive_weights": decision.get("weight_distribution", base_weights),
            "bias_stability_label": bias_stability.get("bias_stability_label"),
            "bias_stability_score": bias_stability.get("bias_stability_score"),
            "trap_risk": int(trap.get("trap_probability_pct", 0) or 0),
            "reversal_risk": reversal_risk,
            "support": support_level,
            "resistance": resistance_level,
            "target1": target.get("target_1"),
            "target2": target.get("target_2"),
            "summary_line": summary_line,
        },
        "levels": {
            "resistance": sr.get("resistance"),
            "support": sr.get("support"),
            "target_1": target.get("target_1"),
            "target_2": target.get("target_2"),
            "acceleration_zone": target.get("acceleration_zone"),
        },
        "signals": {
            "oi": oi,
            "volume": volume,
            "breakout": breakout,
            "trap": trap,
            "regime_shift": regime_shift,
            "momentum_exhaustion": momentum_exhaustion,
            "exhaustion_trap_combo": combo_detector,
            "early_reversal": reversal_prob,
            "auto_exit": auto_exit,
            "prioritized_signals": prioritized.get("prioritized_signals", []),
            "expiry_adaptive": expiry_adaptive,
            "alerts": typed_alerts,
            "alerts_meta": {
                "strong_directional_bias": strong_bias,
                "dominant_direction": dominant_direction,
                "suppressed_count": suppressed_counter,
                "counter_trend_count": len([a for a in typed_alerts if a.get("type") == "counter"]),
                "suppression_reason_map": suppression_reason_map,
            },
        },
        "advanced": {
            "writers_activity": {
                "ce_top": sr.get("resistance", {}).get("levels", [])[:3],
                "pe_top": sr.get("support", {}).get("levels", [])[:3],
            },
            "futures_basis": {"basis": None, "type": "Unavailable"},
            "shift_tracker": {"support_shift": 0, "resistance_shift": 0},
            "pinning_pct": 0,
            "expiry_risk": trap.get("trap_probability_pct", 0),
            "institutional_zones": [
                sr.get("support", {}).get("strike"),
                sr.get("resistance", {}).get("strike"),
            ],
        },
        "trade_plan": trade_plan.get("trade_plan", {}),
        "_state": {
            "regime": current_regime,
            "alignment_ratio": current_alignment,
            "atr_ratio": current_atr_ratio,
            "volume_ratio": round(current_volume_ratio, 4),
            "oi_delta": round(current_oi_delta, 4),
        },
        "_adaptive_state": {
            "session_start_utc": session_start_dt.isoformat(),
            "last_recalc_utc": now_dt.isoformat() if recalc_due else (last_recalc_dt.isoformat() if last_recalc_dt else None),
            "weights": current_weights,
        },
    }


async def _build_symbol_payloads(symbol: str, instrument_type: str) -> tuple[dict[str, Any], dict[str, Any]]:
    option_chain_section: dict[str, Any] = {}
    summary_section: dict[str, Any] = {}

    contract_info = await _fetch_contract_info_async(symbol)
    expiries = list(contract_info.get("expiryDates", []))
    strikes = list(contract_info.get("strikePrice", []))

    option_chain_section["contract_info"] = {
        "symbol": symbol,
        "instrument_type": instrument_type,
        "expiries": expiries,
        "strikes": strikes,
    }

    expiries_to_fetch = expiries[:MAX_EXPIRIES_PER_SYMBOL]
    if not expiries_to_fetch:
        return option_chain_section, summary_section

    for expiry in expiries_to_fetch:
        raw = await _fetch_option_chain_async(symbol=symbol, expiry=expiry, instrument_type=instrument_type)
        records = raw.get("records", {})
        rows = build_oi_volume_summary(raw)
        if not rows:
            continue

        target_projection = build_target_projection(rows, records.get("underlyingValue"))
        support = target_projection.get("support") if target_projection else None
        resistance = target_projection.get("resistance") if target_projection else None
        break_buffer = float(target_projection.get("breakBuffer", 0) or 0) if target_projection else 0.0

        decision_input = build_decision_input(rows, records.get("underlyingValue"), support, resistance, break_buffer)
        master_decision = master_decision_engine(decision_input)

        key = _cache_key(symbol=symbol, instrument_type=instrument_type, expiry=expiry)
        previous_score = await cache.get_previous_score(key)
        previous_bias_score = await cache.get_previous_score(f"BIAS::{key}")
        last_10_scores = await cache.get_score_history(key, limit=10)
        previous_state = await cache.get_previous_state(f"STATE::{key}") or {}
        previous_adaptive_state = await cache.get_previous_state(f"ADAPT::{key}") or {}
        perf_snapshot = tracker.get_daily_metrics(key)
        bias_acc = float(perf_snapshot.get("bias_accuracy_percent", 55.0) or 55.0) / 100.0
        trap_acc = float(perf_snapshot.get("trap_accuracy_percent", 55.0) or 55.0) / 100.0
        exit_acc = float(perf_snapshot.get("exit_accuracy_percent", 55.0) or 55.0) / 100.0
        engine_stats = {
            "oi_accuracy": bias_acc,
            "volume_accuracy": exit_acc if exit_acc > 0 else bias_acc,
            "breakout_accuracy": bias_acc,
            "sr_accuracy": trap_acc if trap_acc > 0 else bias_acc,
        }
        meta = {
            "symbol": symbol,
            "instrument_type": instrument_type,
            "expiry": expiry,
            "spot": records.get("underlyingValue"),
            "timestamp": records.get("timestamp"),
        }
        summary_payload = {
            "meta": meta,
            "target_projection": target_projection,
            "decision_input": decision_input,
            "master_decision": master_decision,
            "rows": rows,
        }

        v2_payload = _build_v2_intelligence(
            rows=rows,
            spot=records.get("underlyingValue"),
            symbol=symbol,
            expiry=expiry,
            timestamp=records.get("timestamp"),
            previous_score=previous_score,
            last_10_scores=last_10_scores,
            previous_bias_score=previous_bias_score,
            previous_regime=previous_state.get("regime"),
            previous_alignment=previous_state.get("alignment_ratio"),
            previous_atr_ratio=previous_state.get("atr_ratio"),
            previous_volume_ratio=previous_state.get("volume_ratio"),
            previous_oi_delta=previous_state.get("oi_delta"),
            adaptive_state=previous_adaptive_state,
            total_signals_logged=int(perf_snapshot.get("total_signals_logged", 0) or 0),
            engine_stats=engine_stats,
            evaluation_time=_parse_timestamp_utc(records.get("timestamp")),
        )
        mstate = v2_payload.get("market_state", {}) or {}
        signals = v2_payload.get("signals", {}) or {}
        auto_exit = (signals.get("auto_exit", {}) or {}).get("exit_signal", False)
        reversal_probability = (signals.get("early_reversal", {}) or {}).get("reversal_probability", 0)
        metrics = tracker.process_snapshot(
            key=key,
            timestamp=_parse_timestamp_utc(records.get("timestamp")),
            spot=records.get("underlyingValue"),
            bias=str(mstate.get("bias", "Neutral")),
            confidence=float(mstate.get("confidence", 50) or 50),
            target1=mstate.get("target1"),
            target2=mstate.get("target2"),
            trap_risk=float(mstate.get("trap_risk", 0) or 0),
            reversal_probability=float(reversal_probability or 0),
            exit_signal=bool(auto_exit),
            expected_move=float((v2_payload.get("signals", {}).get("expiry_adaptive", {}) or {}).get("adjustedMove", target_projection.get("expectedMove", 1) if target_projection else 1) or 1),
        )
        v2_payload["performance"] = metrics

        summary_section[key] = {
            "summary": summary_payload,
            "target_projection": {"meta": meta, "projection": target_projection},
            "interpretations": {
                "meta": {
                    "symbol": symbol,
                    "instrument_type": instrument_type,
                    "expiry": expiry,
                },
                "interpretations": [
                    {
                        "strikePrice": row.get("strike"),
                        "optionType": "CE",
                        "signals": {
                            "priceDirection": row.get("CE_PriceDir"),
                            "oiDirection": row.get("CE_OIDir"),
                            "volumeDirection": row.get("CE_VolDir"),
                        },
                        "interpretationLabel": row.get("CE_Interpretation"),
                        "interpretationDescription": row.get("CE_InterpretationDesc"),
                        "confidenceScore": row.get("CE_ConfidenceScore"),
                    }
                    for row in rows
                ]
                + [
                    {
                        "strikePrice": row.get("strike"),
                        "optionType": "PE",
                        "signals": {
                            "priceDirection": row.get("PE_PriceDir"),
                            "oiDirection": row.get("PE_OIDir"),
                            "volumeDirection": row.get("PE_VolDir"),
                        },
                        "interpretationLabel": row.get("PE_Interpretation"),
                        "interpretationDescription": row.get("PE_InterpretationDesc"),
                        "confidenceScore": row.get("PE_ConfidenceScore"),
                    }
                    for row in rows
                ],
            },
            "v2": v2_payload,
        }
        weighted_score = summary_section[key]["v2"].get("_internal", {}).get("smoothed_score")
        if isinstance(weighted_score, (int, float)):
            await cache.set_previous_score(key, float(weighted_score))
            await cache.append_score_history(key, float(weighted_score))
        current_bias_score = summary_section[key]["v2"].get("market_state", {}).get("probability_bull")
        if isinstance(current_bias_score, (int, float)):
            await cache.set_previous_score(f"BIAS::{key}", float(current_bias_score))
        current_state = summary_section[key]["v2"].get("_state", {})
        if isinstance(current_state, dict):
            await cache.set_previous_state(f"STATE::{key}", current_state)
        current_adaptive_state = summary_section[key]["v2"].get("_adaptive_state", {})
        if isinstance(current_adaptive_state, dict):
            await cache.set_previous_state(f"ADAPT::{key}", current_adaptive_state)

    return option_chain_section, summary_section


async def run_update_cycle() -> None:
    if not await cache.begin_fetch():
        logger.debug("Skipping update cycle: previous fetch still in progress.")
        return

    started = time.perf_counter()
    try:
        option_chain_data: dict[str, Any] = {
            "generated_at": _utc_iso(datetime.now(timezone.utc)),
            "symbols": {},
            "instrument_type": INSTRUMENT_TYPE,
        }
        summary_data: dict[str, Any] = {
            "summaries": {},
            "target_projections": {},
            "interpretations": {},
            "v2": {},
        }

        index_raw = await _fetch_index_data_async()
        option_chain_data["index_data"] = {"data": index_raw.get("data", [])}

        for symbol in SYMBOLS:
            symbol_option_chain, symbol_summaries = await _build_symbol_payloads(symbol, INSTRUMENT_TYPE)
            option_chain_data["symbols"][symbol] = symbol_option_chain

            for key, payload in symbol_summaries.items():
                summary_data["summaries"][key] = payload["summary"]
                summary_data["target_projections"][key] = payload["target_projection"]
                summary_data["interpretations"][key] = payload["interpretations"]
                summary_data["v2"][key] = payload["v2"]

        await cache.update_cache(option_chain_data, summary_data)
        latency_ms = (time.perf_counter() - started) * 1000
        await cache.mark_fetch_success(latency_ms=latency_ms)
        logger.info("Background refresh success in %.2f ms", latency_ms)
    except Exception as exc:
        await cache.mark_fetch_failure(str(exc))
        logger.exception("Background refresh failed: %s", exc)
    finally:
        await cache.recompute_stale(stale_after_seconds=STALE_AFTER_SECONDS)
        await cache.end_fetch()


async def background_update_loop(stop_event: asyncio.Event) -> None:
    logger.info("Starting background updater loop: every %s sec", REFRESH_SECONDS)
    while not stop_event.is_set():
        try:
            await run_update_cycle()
        except Exception as exc:  # belt-and-suspenders: loop must stay alive
            logger.exception("Background loop error: %s", exc)

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=REFRESH_SECONDS)
        except TimeoutError:
            continue

    logger.info("Background updater loop stopped")
