from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from app.services.bse_fetcher import fetch_expiry_and_spot, get_sensex_option_chain

IST = timezone(timedelta(hours=5, minutes=30))


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _to_display_expiry(expiry_label: str | None) -> str | None:
    text = str(expiry_label or "").strip()
    return text.replace(" ", "-") if text else None


def _to_bse_expiry(expiry_label: str | None) -> str | None:
    text = str(expiry_label or "").strip()
    return text.replace("-", " ") if text else None


def _now_ist_str() -> str:
    return datetime.now(IST).strftime("%d-%b-%Y %H:%M:%S")


def fetch_sensex_contract_info(symbol: str) -> dict[str, Any]:
    if str(symbol or "").strip().upper() != "SENSEX":
        raise ValueError(f"Unsupported BSE symbol: {symbol}")

    session = requests.Session()
    try:
        expiry_list, _, strike_list = fetch_expiry_and_spot(session)
        expiries = [
            converted
            for converted in (_to_display_expiry(row.get("ExpiryDate")) for row in expiry_list)
            if converted
        ]
        strike_prices = sorted(
            {
                value
                for value in (_safe_float(row.get("StrikePrice")) for row in strike_list)
                if value is not None and value > 0
            }
        )
        return {
            "expiryDates": expiries,
            "strikePrice": strike_prices,
        }
    finally:
        session.close()


def fetch_sensex_option_chain(
    symbol: str,
    expiry: str | None = None,
    instrument_type: str = "Indices",
) -> dict[str, Any]:
    if str(symbol or "").strip().upper() != "SENSEX":
        raise ValueError(f"Unsupported BSE symbol: {symbol}")
    _ = instrument_type

    display_expiry = str(expiry or "").strip() or None
    bse_expiry = _to_bse_expiry(display_expiry)
    chain = get_sensex_option_chain(expiry_override=bse_expiry)

    if chain.fetch_error:
        return {
            "records": {
                "timestamp": _now_ist_str(),
                "underlyingValue": 0.0,
                "expiryDates": [display_expiry] if display_expiry else [],
                "data": [],
            },
            "filtered": {"data": []},
            "error": chain.fetch_error,
        }

    record_expiry = _to_display_expiry(chain.expiry_date)
    timestamp = chain.timestamp or _now_ist_str()
    try:
        timestamp = datetime.fromisoformat(timestamp).strftime("%d-%b-%Y %H:%M:%S")
    except (TypeError, ValueError):
        timestamp = _now_ist_str()

    data = []
    for strike in chain.strikes:
        ce_prev_oi = max(0, strike.ce_oi - strike.ce_change_oi)
        pe_prev_oi = max(0, strike.pe_oi - strike.pe_change_oi)
        data.append(
            {
                "strikePrice": strike.strike_price,
                "expiryDate": record_expiry,
                "CE": {
                    "openInterest": strike.ce_oi,
                    "changeinOpenInterest": strike.ce_change_oi,
                    "totalTradedVolume": strike.ce_volume,
                    "lastPrice": strike.ce_ltp,
                    "prevPrice": strike.ce_ltp,
                    "previousClose": strike.ce_ltp,
                    "prevOpenInterest": ce_prev_oi,
                    "previousOpenInterest": ce_prev_oi,
                    "impliedVolatility": strike.ce_iv,
                },
                "PE": {
                    "openInterest": strike.pe_oi,
                    "changeinOpenInterest": strike.pe_change_oi,
                    "totalTradedVolume": strike.pe_volume,
                    "lastPrice": strike.pe_ltp,
                    "prevPrice": strike.pe_ltp,
                    "previousClose": strike.pe_ltp,
                    "prevOpenInterest": pe_prev_oi,
                    "previousOpenInterest": pe_prev_oi,
                    "impliedVolatility": strike.pe_iv,
                },
            }
        )

    return {
        "records": {
            "timestamp": timestamp,
            "underlyingValue": chain.spot_price,
            "previousClose": None,
            "OPEN": None,
            "HIGH": None,
            "LOW": None,
            "expiryDates": [record_expiry] if record_expiry else [],
            "data": data,
        },
        "filtered": {"data": data},
    }


async def fetch_sensex_contract_info_async(symbol: str) -> dict[str, Any]:
    return await asyncio.to_thread(fetch_sensex_contract_info, symbol)


async def fetch_sensex_option_chain_async(
    symbol: str,
    expiry: str | None = None,
    instrument_type: str = "Indices",
) -> dict[str, Any]:
    return await asyncio.to_thread(fetch_sensex_option_chain, symbol, expiry, instrument_type)
