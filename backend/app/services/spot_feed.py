from __future__ import annotations

import asyncio
import logging
import os
import time
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

import requests

from app.services.nse_client import fetch_index_data

logger = logging.getLogger("optionlens.spot_feed")

SPOT_API_URL = os.getenv("OPTIONLENS_SPOT_API_URL", "https://www.nseindia.com/api/NextApi/apiClient")
SPOT_FUNCTION_NAME = os.getenv("OPTIONLENS_SPOT_FUNCTION_NAME", "getQuoteData")
SPOT_INTERVAL_SECONDS = float(os.getenv("OPTIONLENS_SPOT_INTERVAL_SECONDS", "2"))
SPOT_TIMEOUT_SECONDS = float(os.getenv("OPTIONLENS_SPOT_TIMEOUT_SECONDS", "3"))
SPOT_RETRIES = int(os.getenv("OPTIONLENS_SPOT_RETRIES", "2"))

SPOT_SYMBOL_MAP = {
    "NIFTY": "in;NSX",
    "BANKNIFTY": "in;nbx",
    "SENSEX": "in;SEN",
}

_spot_lock = asyncio.Lock()
_spot_cache: dict[str, dict[str, Any]] = {k: {} for k in SPOT_SYMBOL_MAP}
_spot_last_update: datetime | None = None
_spot_last_error: str | None = None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _get_first_present(data: dict[str, Any], keys: list[str]) -> Any:
    for k in keys:
        if k in data and data[k] is not None:
            return data[k]
    return None


def _normalize_payload(symbol: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "pricecurrent": _to_float(_get_first_present(payload, ["pricecurrent", "last", "lastPrice", "ltp"])),
        "pricepercentchange": _to_float(
            _get_first_present(payload, ["pricepercentchange", "percChange", "percentChange", "pChange"])
        ),
        "pricechange": _to_float(_get_first_present(payload, ["pricechange", "change", "variation"])),
        "OPEN": _to_float(_get_first_present(payload, ["OPEN", "open", "dayOpen"])),
        "HIGH": _to_float(_get_first_present(payload, ["HIGH", "high", "dayHigh"])),
        "LOW": _to_float(_get_first_present(payload, ["LOW", "low", "dayLow"])),
        "market_state": str(_get_first_present(payload, ["market_state", "marketState", "state"]) or ""),
        "lastupd_epoch": int(_get_first_present(payload, ["lastupd_epoch", "lastUpdateEpoch", "timestamp", "time"]) or int(time.time())),
    }


def _fallback_from_index_data() -> dict[str, dict[str, Any]]:
    # Uses existing NSE index endpoint as fallback to retain last valid values.
    raw = fetch_index_data()
    rows = raw.get("data", []) if isinstance(raw, dict) else []
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        name = str(row.get("indexName", "")).upper()
        if "NIFTY 50" in name:
            out["NIFTY"] = _normalize_payload("NIFTY", row)
        elif "NIFTY BANK" in name:
            out["BANKNIFTY"] = _normalize_payload("BANKNIFTY", row)
        elif "SENSEX" in name:
            out["SENSEX"] = _normalize_payload("SENSEX", row)
    return out


def _fetch_one_symbol_sync(symbol: str, token: str) -> dict[str, Any] | None:
    params = {
        "functionName": SPOT_FUNCTION_NAME,
        "symbol": token,
        "type": token,
    }
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.nseindia.com/",
        "X-Requested-With": "XMLHttpRequest",
    }
    last_exc: Exception | None = None
    for _ in range(max(1, SPOT_RETRIES)):
        try:
            r = requests.get(SPOT_API_URL, params=params, headers=headers, timeout=SPOT_TIMEOUT_SECONDS)
            r.raise_for_status()
            data = r.json()
            if isinstance(data, dict):
                # Try direct dict first, then known wrappers.
                for key in ("data", "result", "payload", "response"):
                    if key in data and isinstance(data[key], dict):
                        data = data[key]
                        break
                return _normalize_payload(symbol, data)
        except Exception as exc:
            last_exc = exc
            time.sleep(0.15)
    if last_exc:
        logger.debug("spot fetch failed for %s: %s", symbol, last_exc)
    return None


async def update_spot_cache_once() -> None:
    global _spot_last_update, _spot_last_error
    result: dict[str, dict[str, Any]] = {}

    try:
        tasks = [
            asyncio.to_thread(_fetch_one_symbol_sync, symbol=symbol, token=token)
            for symbol, token in SPOT_SYMBOL_MAP.items()
        ]
        fetched = await asyncio.gather(*tasks, return_exceptions=True)
        for symbol, payload in zip(SPOT_SYMBOL_MAP.keys(), fetched):
            if isinstance(payload, dict) and payload:
                result[symbol] = payload
    except Exception as exc:
        _spot_last_error = str(exc)
        logger.debug("spot api batch failed: %s", exc)

    # Fallback per cycle for missing symbols.
    try:
        fallback = await asyncio.to_thread(_fallback_from_index_data)
    except Exception as exc:
        fallback = {}
        _spot_last_error = str(exc)
        logger.debug("spot fallback failed: %s", exc)

    async with _spot_lock:
        for symbol in SPOT_SYMBOL_MAP:
            new_payload = result.get(symbol) or fallback.get(symbol)
            if new_payload:
                _spot_cache[symbol] = new_payload
        _spot_last_update = _utc_now()


async def spot_updater(stop_event: asyncio.Event) -> None:
    logger.info("Starting spot updater loop every %.2fs", SPOT_INTERVAL_SECONDS)
    while not stop_event.is_set():
        try:
            await update_spot_cache_once()
        except Exception as exc:
            logger.exception("spot updater cycle failed: %s", exc)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=SPOT_INTERVAL_SECONDS)
        except TimeoutError:
            continue
    logger.info("Spot updater loop stopped")


async def get_spot_cache_snapshot() -> dict[str, Any]:
    async with _spot_lock:
        return {
            "data": deepcopy(_spot_cache),
            "last_update": _spot_last_update.isoformat() if _spot_last_update else None,
            "last_error": _spot_last_error,
        }
