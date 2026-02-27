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
from app.engines.bias_probability_engine import compute_bias_probability
from app.engines.decision_engine import master_arbitration_layer
from app.engines.oi_analyzer import run_oi_analysis
from app.engines.preprocessing import build_feature_frame, normalize_chain
from app.engines.regime_engine import run_regime_engine
from app.engines.sr_engine import run_sr_engine
from app.engines.target_engine import run_target_engine
from app.engines.trap_engine import adjust_trap_by_confidence, run_trap_engine
from app.engines.volume_analyzer import run_volume_analysis
from app.services.decision_engine import build_decision_input, master_decision_engine
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

# Rolling ATR history per symbol+expiry to stabilize confidence.
_atr_history: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=ATR_ROLLING_WINDOW))


def _utc_iso(dt: datetime | None) -> str | None:
    if not dt:
        return None
    return dt.astimezone(timezone.utc).isoformat()


def _cache_key(symbol: str, instrument_type: str, expiry: str | None) -> str:
    return f"{instrument_type.upper()}::{symbol.upper()}::{expiry or 'AUTO'}"


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


def _build_v2_intelligence(
    rows: list[dict[str, Any]],
    spot: float | None,
    symbol: str,
    expiry: str | None,
    timestamp: str | None,
    previous_score: float | None = None,
    last_10_scores: list[float] | None = None,
) -> dict[str, Any]:
    normalized = normalize_chain(rows)
    features = build_feature_frame(
        normalized,
        spot=spot,
        symbol=symbol,
        expiry=expiry,
        timestamp=timestamp,
    )

    oi = run_oi_analysis(features)
    sr = run_sr_engine(features)
    base_volume = run_volume_analysis(features)
    base_breakout = run_breakout_engine(features, sr)
    base_trap = run_trap_engine(features, base_breakout, oi, base_volume)
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

    pre_adjusted_thresholds = regime.get("adjusted_thresholds", {})
    volume_threshold = float(pre_adjusted_thresholds.get("volume_expansion_threshold", 1.2) or 1.2)
    breakout_atr_multiplier = float(pre_adjusted_thresholds.get("breakout_atr_multiplier", 1.2) or 1.2)

    # Recompute with regime-adjusted sensitivities.
    volume = run_volume_analysis(features, expansion_threshold=volume_threshold)
    breakout = run_breakout_engine(features, sr, atr_multiplier=breakout_atr_multiplier)
    trap = run_trap_engine(features, breakout, oi, volume)
    target = run_target_engine(features, sr, breakout, oi, trap, volume)
    regime = run_regime_engine(oi, volume, breakout, trap)
    adjusted_thresholds = regime.get("adjusted_thresholds", pre_adjusted_thresholds)

    pcr = float(features.get("pcr") or 1.0)
    pcr_bias_score = max(-1.0, min(1.0, (pcr - 1.0)))
    atr_threshold = float(breakout.get("atr_threshold") or 0.0)
    volatility_factor = max(0.0, min(1.0, atr_threshold / 200.0))
    avg_atr = _update_and_get_avg_atr(symbol=symbol, expiry=expiry, atr_value=atr_threshold)
    if avg_atr is None:
        avg_atr = float(features.get("atr_proxy") or 0.0)

    decision = master_arbitration_layer(
        oi,
        volume,
        breakout,
        trap,
        regime,
        regime_type=regime.get("regime_type"),
        weights_override=regime.get("adjusted_weights"),
        previous_score=previous_score,
        pcr_bias_score=pcr_bias_score,
        volatility_factor=volatility_factor,
        atr_value=atr_threshold,
        avg_atr=avg_atr,
    )

    bias_input = {
        "records": {
            "underlyingValue": spot,
            "data": [
                {
                    "CE": {
                        "openInterest": row.get("CE_OI", 0),
                        "changeinOpenInterest": row.get("CE_DeltaOI", 0),
                        "totalTradedVolume": row.get("CE_Volume", 0),
                    },
                    "PE": {
                        "openInterest": row.get("PE_OI", 0),
                        "changeinOpenInterest": row.get("PE_DeltaOI", 0),
                        "totalTradedVolume": row.get("PE_Volume", 0),
                    },
                }
                for row in rows
            ],
        }
    }
    bias_result = compute_bias_probability(bias_input)
    trap_conf_adj = adjust_trap_by_confidence(
        base_trap=float(trap.get("trap_probability_pct", 0) or 0),
        smoothed_score=float(decision.get("weighted_score", 0.0) or 0.0),
        confidence_percent=float(decision.get("confidence_percent", decision.get("confidence", 0)) or 0),
    )
    trap["trap_probability_pct"] = int(trap_conf_adj["trap_probability"])
    trap["trap_risk"] = int(trap_conf_adj["trap_probability"])
    trap["confidence_factor"] = float(trap_conf_adj["confidence_factor"])
    trap["is_trap"] = bool(trap["trap_probability_pct"] >= 60)

    weighted_score = float(decision.get("weighted_score", 0.0) or 0.0)
    resistance_strike = sr.get("resistance", {}).get("strike")
    support_strike = sr.get("support", {}).get("strike")
    breakout_up = bool(breakout.get("breakout_up"))
    breakout_down = bool(breakout.get("breakout_down"))
    strong_bias = abs(weighted_score) > 0.5
    dominant_direction = "up" if weighted_score > 0 else "down" if weighted_score < 0 else "neutral"

    alerts: list[dict[str, str]] = []
    if breakout_up and resistance_strike is not None:
        alert = {"message": f"Breakout above {resistance_strike}", "direction": "up"}
        alerts.append(alert)

    if breakout_down and support_strike is not None:
        alert = {"message": f"Breakdown below {support_strike}", "direction": "down"}
        alerts.append(alert)

    typed_alerts: list[dict[str, str]] = []
    suppressed_counter = 0
    for alert in alerts:
        alert_type = "primary" if alert["direction"] == dominant_direction else "counter"
        if strong_bias and alert_type == "counter":
            suppressed_counter += 1
            continue
        typed_alerts.append(
            {
                "message": alert["message"],
                "direction": alert["direction"],
                "type": alert_type,
            }
        )

    return {
        "meta": features["meta"],
        "market_state": {
            "bias": bias_result["biasLabel"],
            "regime": regime.get("regime"),
            "probability_bull": bias_result["bullishProbability"],
            "probability_bear": bias_result["bearishProbability"],
            "confidence": bias_result["confidence"],
            "trap_risk_pct": trap.get("trap_probability_pct"),
            "weighted_score": decision.get("weighted_score"),
            "volatility_state": decision.get("volatility_state"),
            "volatility_ratio": decision.get("volatility_ratio"),
            "explanation": decision["summary_statement"],
            "bias_detail": bias_result.get("detail", {}),
            "arbitration": {
                "bias": decision.get("bias"),
                "probability_bull": decision.get("probability_bull"),
                "probability_bear": decision.get("probability_bear"),
                "confidence": decision.get("confidence"),
            },
            "adjusted_thresholds": adjusted_thresholds,
            "weight_distribution": decision.get("weight_distribution", {}),
            "regime_used": decision.get("regime_used"),
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
            "alerts": typed_alerts,
            "alerts_meta": {
                "strong_directional_bias": strong_bias,
                "dominant_direction": dominant_direction,
                "suppressed_count": suppressed_counter,
                "counter_trend_count": len([a for a in typed_alerts if a.get("type") == "counter"]),
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
        last_10_scores = await cache.get_score_history(key, limit=10)
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
            "v2": _build_v2_intelligence(
                rows=rows,
                spot=records.get("underlyingValue"),
                symbol=symbol,
                expiry=expiry,
                timestamp=records.get("timestamp"),
                previous_score=previous_score,
                last_10_scores=last_10_scores,
            ),
        }
        weighted_score = summary_section[key]["v2"].get("market_state", {}).get("weighted_score")
        if isinstance(weighted_score, (int, float)):
            await cache.set_previous_score(key, float(weighted_score))
            await cache.append_score_history(key, float(weighted_score))

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
