from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any

from app.core.cache import cache
from app.engines.breakout_engine import run_breakout_engine
from app.engines.decision_engine import master_arbitration_layer
from app.engines.oi_analyzer import run_oi_analysis
from app.engines.preprocessing import build_feature_frame, normalize_chain
from app.engines.regime_engine import run_regime_engine
from app.engines.sr_engine import run_sr_engine
from app.engines.target_engine import run_target_engine
from app.engines.trap_engine import run_trap_engine
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


def _utc_iso(dt: datetime | None) -> str | None:
    if not dt:
        return None
    return dt.astimezone(timezone.utc).isoformat()


def _cache_key(symbol: str, instrument_type: str, expiry: str | None) -> str:
    return f"{instrument_type.upper()}::{symbol.upper()}::{expiry or 'AUTO'}"


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
    volume = run_volume_analysis(features)
    sr = run_sr_engine(features)
    breakout = run_breakout_engine(features, sr)
    trap = run_trap_engine(features, breakout, oi, volume)
    target = run_target_engine(features, sr, breakout, oi, trap, volume)
    regime = run_regime_engine(oi, volume, breakout, trap)

    pcr = float(features.get("pcr") or 1.0)
    pcr_bias_score = max(-1.0, min(1.0, (pcr - 1.0)))
    atr_threshold = float(breakout.get("atr_threshold") or 0.0)
    volatility_factor = max(0.0, min(1.0, atr_threshold / 200.0))

    decision = master_arbitration_layer(
        oi,
        volume,
        breakout,
        trap,
        regime,
        pcr_bias_score=pcr_bias_score,
        volatility_factor=volatility_factor,
    )

    return {
        "meta": features["meta"],
        "market_state": {
            "bias": decision["bias"],
            "regime": regime.get("regime"),
            "probability_bull": decision["probability_bull"],
            "probability_bear": decision["probability_bear"],
            "confidence": decision["confidence"],
            "trap_risk_pct": trap.get("trap_probability_pct"),
            "explanation": decision["explanation"],
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
            ),
        }

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
