from typing import Any


def _infer_session_phase(timestamp: str | None) -> str:
    if not timestamp:
        return "Transition"
    import re

    m = re.search(r"(\d{1,2}):(\d{2})", str(timestamp))
    if not m:
        return "Transition"
    hh = int(m.group(1))
    mm = int(m.group(2))
    minutes = (hh * 60) + mm
    if 9 * 60 + 15 <= minutes < 10 * 60 + 30:
        return "Opening"
    if 10 * 60 + 30 <= minutes < 13 * 60 + 30:
        return "Midday"
    if 14 * 60 + 30 <= minutes <= 15 * 60 + 30:
        return "PowerHour"
    return "Transition"


def normalize_chain(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        normalized.append(
            {
                "strike": float(row.get("strike") or 0),
                "CE_OI": float(row.get("CE_OI") or 0),
                "CE_DeltaOI": float(row.get("CE_DeltaOI") or 0),
                "CE_Volume": float(row.get("CE_Volume") or 0),
                "CE_LastPrice": float(row.get("CE_LastPrice") or 0),
                "CE_IV": float(
                    row.get("CE_IV")
                    or row.get("ce_iv")
                    or row.get("CE_ImpliedVolatility")
                    or row.get("impliedVolatility_CE")
                    or 0
                ),
                "PE_OI": float(row.get("PE_OI") or 0),
                "PE_DeltaOI": float(row.get("PE_DeltaOI") or 0),
                "PE_Volume": float(row.get("PE_Volume") or 0),
                "PE_LastPrice": float(row.get("PE_LastPrice") or 0),
                "PE_IV": float(
                    row.get("PE_IV")
                    or row.get("pe_iv")
                    or row.get("PE_ImpliedVolatility")
                    or row.get("impliedVolatility_PE")
                    or 0
                ),
                "CE_PriceDir": row.get("CE_PriceDir") or "->",
                "PE_PriceDir": row.get("PE_PriceDir") or "->",
            }
        )
    return normalized


def build_feature_frame(
    rows: list[dict[str, Any]],
    spot: float | None,
    symbol: str,
    expiry: str | None,
    timestamp: str | None,
    previous_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not rows:
        return {
            "meta": {
                "symbol": symbol,
                "expiry": expiry,
                "timestamp": timestamp,
                "spot": spot,
                "session_phase": _infer_session_phase(timestamp),
            },
            "rows": [],
            "option_chain_rows": [],
            "atm_row": None,
            "strike_gap": 0.0,
            "pcr": 1.0,
            "spot_price": spot,
            "previous_price": None,
            "oi": 0.0,
            "previous_oi": None,
            "volume": 0.0,
            "totals": {},
            "atr_proxy": 0.0,
            "atr": 0.0,
        }

    sorted_rows = sorted(rows, key=lambda r: r["strike"])
    strikes = [r["strike"] for r in sorted_rows]
    strike_diffs = [abs(strikes[i] - strikes[i - 1]) for i in range(1, len(strikes))]
    strike_gap = strike_diffs[0] if strike_diffs else 50.0

    # ATM row is the closest strike to current spot.
    atm_row = min(sorted_rows, key=lambda r: abs(r["strike"] - (spot or 0)))

    ce_total_oi = sum(r["CE_OI"] for r in sorted_rows)
    pe_total_oi = sum(r["PE_OI"] for r in sorted_rows)
    ce_total_vol = sum(r["CE_Volume"] for r in sorted_rows)
    pe_total_vol = sum(r["PE_Volume"] for r in sorted_rows)
    pcr = (pe_total_oi / ce_total_oi) if ce_total_oi else 1.0

    # ATR proxy for option-chain-only context (replace with real ATR when available).
    atr_proxy = max(strike_gap, (max(strikes) - min(strikes)) / max(1, len(strikes)))

    prev_spot_raw = (previous_state or {}).get("spot")
    prev_spot = float(prev_spot_raw) if isinstance(prev_spot_raw, (int, float)) else None
    prev_oi_raw = (previous_state or {}).get("oi_prev_value")
    prev_oi = float(prev_oi_raw) if isinstance(prev_oi_raw, (int, float)) else None

    return {
        "meta": {
            "symbol": symbol,
            "expiry": expiry,
            "timestamp": timestamp,
            "spot": spot,
            "session_phase": _infer_session_phase(timestamp),
        },
        "rows": sorted_rows,
        "option_chain_rows": sorted_rows,
        "atm_row": atm_row,
        "strike_gap": float(strike_gap),
        "pcr": float(pcr),
        "spot_price": spot,
        "previous_price": prev_spot,
        "oi": float(ce_total_oi + pe_total_oi),
        "previous_oi": prev_oi,
        "volume": float(ce_total_vol + pe_total_vol),
        "totals": {
            "ce_total_oi": ce_total_oi,
            "pe_total_oi": pe_total_oi,
            "ce_total_vol": ce_total_vol,
            "pe_total_vol": pe_total_vol,
        },
        "atr_proxy": float(atr_proxy),
        "atr": float(atr_proxy),
    }
