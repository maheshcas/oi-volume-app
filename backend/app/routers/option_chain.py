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
from app.services.decision_engine import build_decision_input, master_decision_engine
from app.engines.data_fetcher import fetch_option_chain_data
from app.engines.preprocessing import normalize_chain, build_feature_frame
from app.engines.oi_analyzer import run_oi_analysis
from app.engines.volume_analyzer import run_volume_analysis
from app.engines.sr_engine import run_sr_engine
from app.engines.breakout_engine import run_breakout_engine
from app.engines.trap_engine import run_trap_engine
from app.engines.target_engine import run_target_engine
from app.engines.regime_engine import run_regime_engine
from app.engines.decision_engine import master_arbitration_layer

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
    target_mode: str = "fixed",
    confidence_score: float = 1.0,
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
    mode = "dynamic" if str(target_mode).lower() == "dynamic" else "fixed"
    target_projection = build_target_projection(
        rows,
        spot,
        target_mode=mode,
        confidence_score=confidence_score,
    )
    support = target_projection.get("support") if target_projection else None
    resistance = target_projection.get("resistance") if target_projection else None
    break_buffer = float(target_projection.get("breakBuffer", 0) or 0) if target_projection else 0.0
    decision_input = build_decision_input(rows, spot, support, resistance, break_buffer)
    master_decision = master_decision_engine(decision_input)

    return {
        "meta": {
            "symbol": symbol,
            "instrument_type": instrument_type,
            "expiry": inferred_expiry,
            "spot": spot,
            "timestamp": records.get("timestamp"),
        },
        "target_projection": target_projection,
        "decision_input": decision_input,
        "master_decision": master_decision,
        "rows": rows,
    }


@router.get("/option-chain/target-projection")
def option_chain_target_projection(
    symbol: str = "NIFTY",
    expiry: Optional[str] = None,
    instrument_type: str = "Indices",
    use_sample: bool = False,
    target_mode: str = "fixed",
    confidence_score: float = 1.0,
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

    mode = "dynamic" if str(target_mode).lower() == "dynamic" else "fixed"
    projection = build_target_projection(
        rows,
        records.get("underlyingValue"),
        target_mode=mode,
        confidence_score=confidence_score,
    )
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


@router.get("/v2/intelligence/summary")
def intelligence_summary_v2(
    symbol: str = "NIFTY",
    expiry: Optional[str] = None,
    instrument_type: str = "Indices",
    use_sample: bool = False,
):
    """
    Modular intelligence pipeline (v2):
    data_fetcher -> preprocessing -> analyzers/engines -> arbitration.
    """
    if expiry == "":
        expiry = None

    try:
        raw = _load_sample() if use_sample else fetch_option_chain_data(
            symbol=symbol, expiry=expiry, instrument_type=instrument_type
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    records = raw.get("records", {})
    rows = build_oi_volume_summary(raw)
    if not rows:
        raise HTTPException(status_code=502, detail="No option chain data returned from NSE.")

    normalized = normalize_chain(rows)
    features = build_feature_frame(
        normalized,
        spot=records.get("underlyingValue"),
        symbol=symbol,
        expiry=expiry,
        timestamp=records.get("timestamp"),
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
            "institutional_zones": [sr.get("support", {}).get("strike"), sr.get("resistance", {}).get("strike")],
        },
    }
