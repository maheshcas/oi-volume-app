import json
import os
from typing import Optional

from fastapi import APIRouter, HTTPException
from app.services.nse_client import (
    fetch_index_data,
    fetch_option_chain,
    fetch_option_chain_contract_info,
)
from app.services.parser import build_oi_volume_summary, build_target_projection

router = APIRouter()


def _load_sample():
    path = os.path.join(os.path.dirname(__file__), "..", "services", "nifty_option_chain.json")
    with open(path, "r") as f:
        return json.load(f)


@router.get("/option-chain/expiries")
def option_chain_expiries(
    symbol: str = "NIFTY",
    instrument_type: str = "Indices",
    use_sample: bool = False,
):
    """
    Returns available expiry dates for a symbol.
    """
    try:
        if use_sample:
            raw = _load_sample()
            expiries = raw.get("records", {}).get("expiryDates", [])
            strikes = sorted(
                {item.get("strikePrice") for item in raw.get("records", {}).get("data", []) if item.get("strikePrice")}
            )
        else:
            raw = fetch_option_chain_contract_info(symbol=symbol)
            expiries = raw.get("expiryDates", [])
            strikes = raw.get("strikePrice", [])
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {
        "symbol": symbol,
        "instrument_type": instrument_type,
        "expiries": expiries,
        "strikes": strikes,
    }


@router.get("/option-chain/summary")
def option_chain_summary(
    symbol: str = "NIFTY",
    expiry: Optional[str] = None,
    instrument_type: str = "Indices",
    use_sample: bool = False,
):
    """
    Returns OI vs Volume summary. If use_sample=True, loads sample JSON instead of NSE.
    """
    if expiry == "":
        expiry = None

    try:
        raw = _load_sample() if use_sample else fetch_option_chain(
            symbol=symbol, expiry=expiry, instrument_type=instrument_type
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    records = raw.get("records", {})
    inferred_expiry = expiry
    if not inferred_expiry:
        inferred_expiry = None
        expiries = records.get("expiryDates", [])
        if expiries:
            inferred_expiry = expiries[0]

    rows = build_oi_volume_summary(raw)
    if not rows:
        raise HTTPException(status_code=502, detail="No option chain data returned from NSE.")

    spot = records.get("underlyingValue")
    target_projection = build_target_projection(rows, spot)

    return {
        "meta": {
            "symbol": symbol,
            "instrument_type": instrument_type,
            "expiry": inferred_expiry,
            "spot": spot,
            "timestamp": records.get("timestamp"),
        },
        "target_projection": target_projection,
        "rows": rows,
    }


@router.get("/option-chain/target-projection")
def option_chain_target_projection(
    symbol: str = "NIFTY",
    expiry: Optional[str] = None,
    instrument_type: str = "Indices",
    use_sample: bool = False,
):
    """
    Returns clean target projection using support/resistance inferred from max OI strikes.
    """
    if expiry == "":
        expiry = None

    try:
        raw = _load_sample() if use_sample else fetch_option_chain(
            symbol=symbol, expiry=expiry, instrument_type=instrument_type
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    records = raw.get("records", {})
    rows = build_oi_volume_summary(raw)
    if not rows:
        raise HTTPException(status_code=502, detail="No option chain data returned from NSE.")

    projection = build_target_projection(rows, records.get("underlyingValue"))
    if not projection:
        raise HTTPException(status_code=502, detail="Unable to derive target projection from option chain.")

    return {
        "meta": {
            "symbol": symbol,
            "instrument_type": instrument_type,
            "expiry": expiry,
            "spot": records.get("underlyingValue"),
            "timestamp": records.get("timestamp"),
        },
        "projection": projection,
    }


@router.get("/option-chain/interpretations")
def option_chain_interpretations(
    symbol: str = "NIFTY",
    expiry: Optional[str] = None,
    instrument_type: str = "Indices",
    use_sample: bool = False,
):
    """
    Returns per-strike interpretation objects for CE and PE using the rule engine.
    """
    if expiry == "":
        expiry = None

    try:
        raw = _load_sample() if use_sample else fetch_option_chain(
            symbol=symbol, expiry=expiry, instrument_type=instrument_type
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    rows = build_oi_volume_summary(raw)
    out = []
    for row in rows:
        strike = row.get("strike")
        out.append({
            "strikePrice": strike,
            "optionType": "CE",
            "signals": {
                "priceDirection": row.get("CE_PriceDir"),
                "oiDirection": row.get("CE_OIDir"),
                "volumeDirection": row.get("CE_VolDir"),
            },
            "interpretationLabel": row.get("CE_Interpretation"),
            "interpretationDescription": row.get("CE_InterpretationDesc"),
            "confidenceScore": row.get("CE_ConfidenceScore"),
        })
        out.append({
            "strikePrice": strike,
            "optionType": "PE",
            "signals": {
                "priceDirection": row.get("PE_PriceDir"),
                "oiDirection": row.get("PE_OIDir"),
                "volumeDirection": row.get("PE_VolDir"),
            },
            "interpretationLabel": row.get("PE_Interpretation"),
            "interpretationDescription": row.get("PE_InterpretationDesc"),
            "confidenceScore": row.get("PE_ConfidenceScore"),
        })

    return {
        "meta": {
            "symbol": symbol,
            "instrument_type": instrument_type,
            "expiry": expiry,
        },
        "interpretations": out,
    }


@router.get("/health/nse")
def nse_health_check():
    """
    Simple NSE reachability check.
    """
    try:
        raw = fetch_option_chain(symbol="NIFTY", expiry=None, instrument_type="Indices")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    records = raw.get("records", {})
    return {
        "ok": True,
        "timestamp": records.get("timestamp"),
        "spot": records.get("underlyingValue"),
    }


@router.get("/index-data")
def index_data(names: Optional[str] = None):
    """
    Live NSE index data. Optionally filter by comma-separated index names.
    Example: names=NIFTY%2050,NIFTY%20BANK
    """
    try:
        raw = fetch_index_data()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    data = raw.get("data", [])
    if not names:
        return {"data": data}

    requested = {name.strip().upper() for name in names.split(",") if name.strip()}
    filtered = [row for row in data if str(row.get("indexName", "")).upper() in requested]
    return {"data": filtered}
