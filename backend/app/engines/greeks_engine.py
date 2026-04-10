from __future__ import annotations
import math
from typing import Any
from datetime import datetime, date


def _norm_cdf(x: float) -> float:
    return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def _days_to_expiry(expiry_str: str) -> float:
    for fmt in ("%d-%b-%Y", "%Y-%m-%d", "%d %b %Y"):
        try:
            exp_date = datetime.strptime(expiry_str.strip(), fmt).date()
            days = (exp_date - date.today()).days
            return max(0.5, float(days))
        except ValueError:
            continue
    return 1.0


def _moneyness(spot: float, strike: float, option_type: str) -> str:
    ratio = (spot - strike) / spot * 100
    if option_type == "CE":
        if ratio > 3:
            return "Deep ITM"
        if ratio > 0.5:
            return "ITM"
        if ratio > -0.5:
            return "ATM"
        if ratio > -3:
            return "OTM"
        return "Deep OTM"
    else:
        if ratio < -3:
            return "Deep ITM"
        if ratio < -0.5:
            return "ITM"
        if ratio > -0.5:
            return "ATM"
        if ratio < 3:
            return "OTM"
        return "Deep OTM"


def compute_greeks(
    *,
    spot: float,
    strike: float,
    iv: float,
    expiry_str: str,
    option_type: str,
    risk_free: float = 0.065,
) -> dict[str, Any]:
    T = _days_to_expiry(expiry_str) / 365.0
    sigma = max(0.001, float(iv))
    S = float(spot)
    K = float(strike)
    r = float(risk_free)

    if T <= 0 or S <= 0 or K <= 0 or sigma <= 0:
        return {
            "delta": 0.0,
            "gamma": 0.0,
            "theta": 0.0,
            "vega": 0.0,
            "iv": round(sigma * 100, 2),
            "days_to_expiry": 0,
            "moneyness": _moneyness(S, K, option_type),
            "error": "invalid_inputs",
        }

    sqrt_T = math.sqrt(T)
    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * sqrt_T)
    d2 = d1 - sigma * sqrt_T

    if option_type == "CE":
        delta = _norm_cdf(d1)
        theta = (
            -(S * _norm_pdf(d1) * sigma) / (2 * sqrt_T)
            - r * K * math.exp(-r * T) * _norm_cdf(d2)
        ) / 365
    else:
        delta = _norm_cdf(d1) - 1.0
        theta = (
            -(S * _norm_pdf(d1) * sigma) / (2 * sqrt_T)
            + r * K * math.exp(-r * T) * _norm_cdf(-d2)
        ) / 365

    gamma = _norm_pdf(d1) / (S * sigma * sqrt_T)
    vega = S * _norm_pdf(d1) * sqrt_T / 100

    return {
        "delta": round(delta, 4),
        "gamma": round(gamma, 6),
        "theta": round(theta, 4),
        "vega": round(vega, 4),
        "iv": round(sigma * 100, 2),
        "days_to_expiry": int(_days_to_expiry(expiry_str)),
        "moneyness": _moneyness(S, K, option_type),
    }


def compute_chain_greeks(
    rows: list[dict[str, Any]],
    spot: float,
    expiry_str: str,
) -> list[dict[str, Any]]:
    result = []
    for row in rows:
        strike = float(row.get("strike", 0) or 0)
        if strike <= 0:
            continue
        ce_iv = float(row.get("CE_IV", row.get("ce_iv", 0)) or 0) / 100
        pe_iv = float(row.get("PE_IV", row.get("pe_iv", 0)) or 0) / 100
        if ce_iv <= 0:
            ce_iv = 0.15
        if pe_iv <= 0:
            pe_iv = 0.15
        ce_greeks = compute_greeks(
            spot=spot, strike=strike, iv=ce_iv,
            expiry_str=expiry_str, option_type="CE",
        )
        pe_greeks = compute_greeks(
            spot=spot, strike=strike, iv=pe_iv,
            expiry_str=expiry_str, option_type="PE",
        )
        result.append({
            "strike": strike,
            "ce": ce_greeks,
            "pe": pe_greeks,
            "ltp_ce": float(row.get("CE_LastPrice", row.get("ce_ltp", 0)) or 0),
            "ltp_pe": float(row.get("PE_LastPrice", row.get("pe_ltp", 0)) or 0),
        })
    return result
