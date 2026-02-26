from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, HTTPException

from app.core.cache import cache

router = APIRouter()


def _cache_key(symbol: str, instrument_type: str, expiry: str | None) -> str:
    return f"{instrument_type.upper()}::{symbol.upper()}::{expiry or 'AUTO'}"


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


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


@router.get("/option-chain/expiries")
async def option_chain_expiries(
    symbol: str = "NIFTY",
    instrument_type: str = "Indices",
    use_sample: bool = False,  # kept for compatibility; cache-only backend ignores this flag
):
    _ = use_sample
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
    use_sample: bool = False,  # compatibility
    target_mode: str = "fixed",  # compatibility; precomputed in background
    confidence_score: float = 1.0,  # compatibility; precomputed in background
):
    _ = (use_sample, target_mode, confidence_score)
    data = await _require_cache_ready()
    key = _cache_key(symbol=symbol, instrument_type=instrument_type, expiry=expiry)
    payload = data["summary_data"].get("summaries", {}).get(key)
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
    use_sample: bool = False,
    target_mode: str = "fixed",
    confidence_score: float = 1.0,
):
    _ = (use_sample, target_mode, confidence_score)
    data = await _require_cache_ready()
    key = _cache_key(symbol=symbol, instrument_type=instrument_type, expiry=expiry)
    payload = data["summary_data"].get("target_projections", {}).get(key)
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
    use_sample: bool = False,
):
    _ = use_sample
    data = await _require_cache_ready()
    key = _cache_key(symbol=symbol, instrument_type=instrument_type, expiry=expiry)
    payload = data["summary_data"].get("interpretations", {}).get(key)
    if not payload:
        raise HTTPException(
            status_code=503,
            detail={"status": "initializing", "message": "Interpretation cache is warming up"},
        )
    return payload


@router.get("/health/nse")
async def nse_health_check():
    data = await cache.get_cached_data()
    return {
        "ok": bool(data["summary_data"]),
        "timestamp": _iso(data.get("last_successful_fetch")),
        "stale_data": data.get("stale_data", True),
        "is_fetching": data.get("is_fetching", False),
        "last_error": data.get("metrics", {}).get("last_error"),
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


@router.get("/v2/intelligence/summary")
async def intelligence_summary_v2(
    symbol: str = "NIFTY",
    expiry: Optional[str] = None,
    instrument_type: str = "Indices",
    use_sample: bool = False,
):
    _ = use_sample
    data = await _require_cache_ready()
    key = _cache_key(symbol=symbol, instrument_type=instrument_type, expiry=expiry)
    payload = data["summary_data"].get("v2", {}).get(key)
    if not payload:
        raise HTTPException(
            status_code=503,
            detail={"status": "initializing", "message": "Intelligence cache is warming up"},
        )
    return payload
