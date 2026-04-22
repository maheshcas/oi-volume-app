from __future__ import annotations
import json
import os
import re
from copy import deepcopy
from datetime import datetime
from typing import Any, Optional
from datetime import timezone

from fastapi import APIRouter, HTTPException

from app.core.cache import cache, make_cache_key
from app.application.use_cases.background_updater import _build_symbol_payloads, _seeded_runtime_flush
from app.engines.bias_probability_engine import compute_bias_probability
from app.engines.simulation_engine import simulate_breakout_performance
from app.services.engine_health import compute_engine_health
from app.infrastructure.persistence.historical_zone_context import load_latest_historical_zone_context
from app.infrastructure.persistence.historical_zone_scheduler import get_historical_zone_scheduler_status
from pathlib import Path

router = APIRouter()

_cache_key = make_cache_key

# ---------------------------------------------------------------------------
# Allowed input values — driven by the same env vars as the background updater
# so adding a new symbol in one place covers both.
# ---------------------------------------------------------------------------
_raw_symbols = os.getenv("OPTIONLENS_SYMBOLS", "NIFTY,BANKNIFTY,FINNIFTY")
_ALLOWED_SYMBOLS: frozenset[str] = frozenset(
    s.strip().upper() for s in _raw_symbols.split(",") if s.strip()
) | frozenset({"SENSEX"})

_ALLOWED_INSTRUMENT_TYPES: frozenset[str] = frozenset({"INDICES", "FUTURES", "EQUITIES"})

# Expiry dates come from NSE/BSE and look like "27-Jun-2024"; allow only safe chars.
_EXPIRY_RE = re.compile(r"^[A-Za-z0-9\-]+$")


def _validate_symbol(symbol: str) -> str:
    upper = symbol.strip().upper()
    if upper not in _ALLOWED_SYMBOLS:
        raise HTTPException(status_code=400, detail=f"Unknown symbol '{symbol}'")
    return upper


def _validate_instrument_type(instrument_type: str) -> str:
    upper = instrument_type.strip().upper()
    if upper not in _ALLOWED_INSTRUMENT_TYPES:
        raise HTTPException(status_code=400, detail=f"Unknown instrument_type '{instrument_type}'")
    return upper


def _validate_expiry(expiry: str | None) -> str | None:
    if expiry is None:
        return None
    if not _EXPIRY_RE.fullmatch(expiry.strip()):
        raise HTTPException(status_code=400, detail="Invalid expiry format")
    return expiry.strip()


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _get_next_flush_ist() -> str:
    from app.application.use_cases.background_updater import (
        IST as BG_IST,
        _SCHEDULED_FLUSH_WINDOWS_IST,
        _flushed_windows,
    )

    now = datetime.now(BG_IST)
    now_mins = now.hour * 60 + now.minute
    for h, m in sorted(_SCHEDULED_FLUSH_WINDOWS_IST):
        w_mins = h * 60 + m
        if w_mins > now_mins and (h, m) not in _flushed_windows:
            return f"{h:02d}:{m:02d} IST"
    return "09:15 IST (tomorrow)"

def _freshness_payload(last_update: datetime | None) -> dict[str, Any]:
    if not last_update:
        return {"freshness_state": "delayed", "delta_seconds": None}
    delta_seconds = max(0, int((datetime.now(timezone.utc) - last_update).total_seconds()))
    if delta_seconds < 30:
        state = "live"
    elif delta_seconds < 60:
        state = "stale"
    else:
        state = "delayed"
    return {"freshness_state": state, "delta_seconds": delta_seconds}


def _resolve_cached_v2_payload(
    data: dict[str, Any],
    symbol: str,
    instrument_type: str,
    expiry: str | None,
) -> tuple[dict[str, Any] | None, str | None]:
    """
    Resolve v2 payload with a safe fallback:
    - Try exact key first.
    - If expiry is missing, fallback to the first available cached expiry
      based on contract_info expiry ordering.
    """
    v2_map = data.get("summary_data", {}).get("v2", {}) or {}
    exact_key = _cache_key(symbol=symbol, instrument_type=instrument_type, expiry=expiry)
    payload = v2_map.get(exact_key)
    if payload:
        return payload, expiry

    if expiry:
        return None, expiry

    symbol_payload = data.get("option_chain_data", {}).get("symbols", {}).get(symbol.upper(), {}) or {}
    contract_expiries = (
        symbol_payload.get("contract_info", {}).get("expiries", [])
        if isinstance(symbol_payload, dict)
        else []
    )

    for exp in contract_expiries:
        key = _cache_key(symbol=symbol, instrument_type=instrument_type, expiry=str(exp))
        if key in v2_map:
            return v2_map[key], str(exp)

    prefix = f"{instrument_type.upper()}::{symbol.upper()}::"
    for k, v in v2_map.items():
        if isinstance(k, str) and k.startswith(prefix):
            fallback_expiry = k.split("::", 2)[2] if "::" in k else None
            return v, fallback_expiry

    return None, None


async def _warm_explicit_expiry_cache(
    symbol: str,
    instrument_type: str,
    expiry: str | None,
) -> bool:
    if not expiry:
        return False

    key = _cache_key(symbol=symbol, instrument_type=instrument_type, expiry=expiry)
    symbol_option_chain, symbol_summaries = await _build_symbol_payloads(
        symbol=symbol,
        instrument_type=instrument_type,
        requested_expiries=[expiry],
    )
    payload = symbol_summaries.get(key)
    if not payload:
        return False

    cached = await cache.get_cached_data()
    option_chain_data = deepcopy(cached.get("option_chain_data") or {})
    summary_data = deepcopy(cached.get("summary_data") or {})

    option_chain_data.setdefault("symbols", {})
    option_chain_data["symbols"][symbol.upper()] = symbol_option_chain
    option_chain_data["generated_at"] = datetime.now(timezone.utc).isoformat()
    option_chain_data["instrument_type"] = instrument_type

    summary_data.setdefault("summaries", {})
    summary_data.setdefault("target_projections", {})
    summary_data.setdefault("interpretations", {})
    summary_data.setdefault("v2", {})
    summary_data["summaries"][key] = payload["summary"]
    summary_data["target_projections"][key] = payload["target_projection"]
    summary_data["interpretations"][key] = payload["interpretations"]
    summary_data["v2"][key] = payload["v2"]

    await cache.update_cache(option_chain_data, summary_data)
    return True


async def _require_cache_ready() -> dict[str, Any]:
    data = await cache.get_cached_data()
    if not data["summary_data"]:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "initializing",
                "message": "Cache warming in progress. Try again shortly.",
            },
        )
    return data


@router.post("/debug/flush-cache")
async def debug_flush_cache():
    """
    Dev-only endpoint to clear in-memory summary cache.
    Forces next poll cycle to rebuild from scratch.
    """
    preserved_count = await _seeded_runtime_flush()
    return {
        "status": "flushed",
        "seeded": preserved_count,
        "message": "Seeded cache flush complete. Fresh state on next cycle.",
    }


@router.get("/option-chain/expiries")
async def option_chain_expiries(
    symbol: str = "NIFTY",
    instrument_type: str = "Indices",
):
    symbol = _validate_symbol(symbol)
    instrument_type = _validate_instrument_type(instrument_type)
    data = await _require_cache_ready()
    symbols = data["option_chain_data"].get("symbols", {})
    symbol_payload = symbols.get(symbol.upper(), {})
    contract = symbol_payload.get("contract_info", {})
    expiries = contract.get("expiries", [])
    strikes = contract.get("strikes", [])

    if not contract:
        raise HTTPException(
            status_code=503,
            detail={"status": "initializing", "message": f"Cache not ready for symbol {symbol.upper()}"},
        )

    return {
        "symbol": symbol.upper(),
        "instrument_type": instrument_type,
        "expiries": expiries,
        "strikes": strikes,
        "last_update": _iso(data.get("last_update")),
        "stale_data": data.get("stale_data", True),
    }


@router.get("/option-chain/summary")
async def option_chain_summary(
    symbol: str = "NIFTY",
    expiry: Optional[str] = None,
    instrument_type: str = "Indices",
):
    symbol = _validate_symbol(symbol)
    instrument_type = _validate_instrument_type(instrument_type)
    expiry = _validate_expiry(expiry)
    data = await _require_cache_ready()
    key = _cache_key(symbol=symbol, instrument_type=instrument_type, expiry=expiry)
    summaries = data["summary_data"].get("summaries", {}) or {}
    payload = summaries.get(key)
    if not payload and expiry:
        warmed = await _warm_explicit_expiry_cache(symbol=symbol, instrument_type=instrument_type, expiry=expiry)
        if warmed:
            data = await _require_cache_ready()
            summaries = data["summary_data"].get("summaries", {}) or {}
            payload = summaries.get(key)
    if not payload and expiry is None:
        prefix = f"{instrument_type.upper()}::{symbol.upper()}::"
        for k, v in summaries.items():
            if isinstance(k, str) and k.startswith(prefix):
                payload = v
                break
    if not payload:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "initializing",
                "message": f"Cached summary not ready for {symbol.upper()} {expiry or ''}".strip(),
            },
        )
    return payload


@router.get("/option-chain/target-projection")
async def option_chain_target_projection(
    symbol: str = "NIFTY",
    expiry: Optional[str] = None,
    instrument_type: str = "Indices",
):
    symbol = _validate_symbol(symbol)
    instrument_type = _validate_instrument_type(instrument_type)
    expiry = _validate_expiry(expiry)
    data = await _require_cache_ready()
    key = _cache_key(symbol=symbol, instrument_type=instrument_type, expiry=expiry)
    target_projections = data["summary_data"].get("target_projections", {}) or {}
    payload = target_projections.get(key)
    if not payload and expiry is None:
        prefix = f"{instrument_type.upper()}::{symbol.upper()}::"
        for k, v in target_projections.items():
            if isinstance(k, str) and k.startswith(prefix):
                payload = v
                break
    if not payload:
        raise HTTPException(
            status_code=503,
            detail={"status": "initializing", "message": "Target projection cache is warming up"},
        )
    return payload


@router.get("/option-chain/interpretations")
async def option_chain_interpretations(
    symbol: str = "NIFTY",
    expiry: Optional[str] = None,
    instrument_type: str = "Indices",
):
    symbol = _validate_symbol(symbol)
    instrument_type = _validate_instrument_type(instrument_type)
    expiry = _validate_expiry(expiry)
    data = await _require_cache_ready()
    key = _cache_key(symbol=symbol, instrument_type=instrument_type, expiry=expiry)
    interpretations = data["summary_data"].get("interpretations", {}) or {}
    payload = interpretations.get(key)
    if not payload and expiry is None:
        prefix = f"{instrument_type.upper()}::{symbol.upper()}::"
        for k, v in interpretations.items():
            if isinstance(k, str) and k.startswith(prefix):
                payload = v
                break
    if not payload:
        raise HTTPException(
            status_code=503,
            detail={"status": "initializing", "message": "Interpretation cache is warming up"},
        )
    return payload


@router.get("/health/nse")
async def nse_health_check():
    data = await cache.get_cached_data()
    freshness = _freshness_payload(data.get("last_update"))
    return {
        "ok": bool(data["summary_data"]),
        "timestamp": _iso(data.get("last_successful_fetch")),
        "stale_data": data.get("stale_data", True),
        "is_fetching": data.get("is_fetching", False),
        "last_error": data.get("metrics", {}).get("last_error"),
        "freshness_state": freshness["freshness_state"],
        "delta_seconds": freshness["delta_seconds"],
    }


@router.get("/health/historical-zones")
async def historical_zone_health_check():
    status = get_historical_zone_scheduler_status(symbols=sorted(_ALLOWED_SYMBOLS))
    return {
        "ok": bool(status.get("enabled", False)),
        "scheduler": status,
    }


@router.get("/index-data")
async def index_data(names: Optional[str] = None):
    data = await _require_cache_ready()
    rows = data["option_chain_data"].get("index_data", {}).get("data", [])
    if not names:
        return {"data": rows}

    requested = {name.strip().upper() for name in names.split(",") if name.strip()}
    filtered = [row for row in rows if str(row.get("indexName", "")).upper() in requested]
    return {"data": filtered}


@router.get("/engine-health")
async def engine_health():
    log_path = Path(__file__).resolve().parents[3] / "logs" / "optionlens_cycle_log.jsonl"
    payload = compute_engine_health(log_path=log_path, tail_cycles=200)
    from app.application.use_cases.background_updater import (
        _SCHEDULED_FLUSH_WINDOWS_IST,
        _flushed_windows,
        _last_seeded_flush_ist,
        _cycle_count_since_flush,
    )

    payload["scheduled_flush_windows"] = [f"{h:02d}:{m:02d} IST" for h, m in _SCHEDULED_FLUSH_WINDOWS_IST]
    payload["flushed_today"] = [f"{h:02d}:{m:02d} IST" for h, m in sorted(_flushed_windows)]
    payload["next_flush"] = _get_next_flush_ist()
    payload["seeded_flush_last_fired_at"] = (
        _last_seeded_flush_ist.isoformat() if _last_seeded_flush_ist else None
    )
    payload["cycle_count_since_flush"] = int(_cycle_count_since_flush)
    return payload


@router.get("/event-log")
async def event_log(limit: int = 20):
    log_path = Path(__file__).resolve().parents[3] / "logs" / "optionlens_market_events.txt"
    stream_path = Path(__file__).resolve().parents[3] / "logs" / "optionlens_market_events.jsonl"
    if limit < 1:
        limit = 1
    if limit > 200:
        limit = 200
    structured_events: list[dict[str, Any]] = []
    if stream_path.exists():
        try:
            raw_lines = stream_path.read_text(encoding="utf-8").splitlines()
            for line in raw_lines[-limit:]:
                line = line.strip()
                if not line:
                    continue
                structured_events.append(json.loads(line))
        except Exception:
            structured_events = []
    if not log_path.exists():
        return {
            "path": str(log_path),
            "entries": [],
            "events": structured_events,
            "message": "Event log not created yet.",
        }

    lines = log_path.read_text(encoding="utf-8").splitlines()
    if len(lines) <= 2:
        entries: list[str] = []
    else:
        entries = lines[2:][-limit:]
    return {
        "path": str(log_path),
        "entries": entries,
        "events": structured_events,
    }


@router.get("/v2/intelligence/summary")
async def intelligence_summary_v2(
    symbol: str = "NIFTY",
    expiry: Optional[str] = None,
    instrument_type: str = "Indices",
):
    symbol = _validate_symbol(symbol)
    instrument_type = _validate_instrument_type(instrument_type)
    expiry = _validate_expiry(expiry)
    data = await _require_cache_ready()
    payload, resolved_expiry = _resolve_cached_v2_payload(
        data=data,
        symbol=symbol,
        instrument_type=instrument_type,
        expiry=expiry,
    )
    if not payload:
        raise HTTPException(
            status_code=503,
            detail={"status": "initializing", "message": "Intelligence cache is warming up"},
        )
    response = deepcopy(payload)
    response.pop("_internal", None)
    response.pop("_state", None)
    response.pop("_adaptive_state", None)
    freshness = _freshness_payload(data.get("last_update"))
    market_state = response.get("market_state") or {}
    market_state["freshness_state"] = freshness["freshness_state"]
    market_state["delta_seconds"] = freshness["delta_seconds"]
    historical_context = load_latest_historical_zone_context(symbol)
    if historical_context:
        market_state["historical_context_available"] = True
        market_state["historical_context_updated_at"] = historical_context.get("generated_at_utc")
        response["historical_zone_context"] = historical_context
    else:
        market_state["historical_context_available"] = False
    response["market_state"] = market_state
    meta = response.get("meta") or {}
    if not meta.get("expiry") and resolved_expiry:
        meta["expiry"] = resolved_expiry
    response["meta"] = meta
    return response


@router.get("/v2/intelligence/trade-plan")
async def intelligence_trade_plan_v2(
    symbol: str = "NIFTY",
    expiry: Optional[str] = None,
    instrument_type: str = "Indices",
):
    symbol = _validate_symbol(symbol)
    instrument_type = _validate_instrument_type(instrument_type)
    expiry = _validate_expiry(expiry)
    data = await _require_cache_ready()
    key = _cache_key(symbol=symbol, instrument_type=instrument_type, expiry=expiry)
    payload = data["summary_data"].get("v2", {}).get(key)
    if not payload:
        raise HTTPException(
            status_code=503,
            detail={"status": "initializing", "message": "Trade plan cache is warming up"},
        )
    freshness = _freshness_payload(data.get("last_update"))
    return {
        "meta": payload.get("meta", {}),
        "trade_plan": payload.get("trade_plan", {}),
        "freshness_state": freshness["freshness_state"],
        "delta_seconds": freshness["delta_seconds"],
    }


@router.get("/v2/performance/daily")
async def performance_daily_v2(
    symbol: str = "NIFTY",
    expiry: Optional[str] = None,
    instrument_type: str = "Indices",
):
    symbol = _validate_symbol(symbol)
    instrument_type = _validate_instrument_type(instrument_type)
    expiry = _validate_expiry(expiry)
    data = await _require_cache_ready()
    key = _cache_key(symbol=symbol, instrument_type=instrument_type, expiry=expiry)
    payload = data["summary_data"].get("v2", {}).get(key)
    if not payload:
        raise HTTPException(
            status_code=503,
            detail={"status": "initializing", "message": "Performance cache is warming up"},
        )
    return payload.get(
        "performance",
        {
            "bias_accuracy_percent": 0.0,
            "trap_accuracy_percent": 0.0,
            "exit_accuracy_percent": 0.0,
            "total_signals_logged": 0,
        },
    )


@router.post("/bias/probability")
async def bias_probability(payload: dict[str, Any]):
    return compute_bias_probability(payload)


@router.post("/simulation/breakout-performance")
async def simulation_breakout_performance(payload: dict[str, Any]):
    historical_data = payload.get("historicalData")
    if not isinstance(historical_data, list):
        raise HTTPException(
            status_code=400,
            detail={"message": "historicalData must be a list of option-chain snapshots"},
        )
    return simulate_breakout_performance(historical_data)
