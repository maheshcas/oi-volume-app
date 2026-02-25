from typing import Any


def normalize_chain(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = []
    for row in rows:
        normalized.append(
            {
                "strike": float(row.get("strike") or 0),
                "CE_OI": float(row.get("CE_OI") or 0),
                "CE_DeltaOI": float(row.get("CE_DeltaOI") or 0),
                "CE_Volume": float(row.get("CE_Volume") or 0),
                "CE_LastPrice": float(row.get("CE_LastPrice") or 0),
                "PE_OI": float(row.get("PE_OI") or 0),
                "PE_DeltaOI": float(row.get("PE_DeltaOI") or 0),
                "PE_Volume": float(row.get("PE_Volume") or 0),
                "PE_LastPrice": float(row.get("PE_LastPrice") or 0),
                "CE_PriceDir": row.get("CE_PriceDir") or "→",
                "PE_PriceDir": row.get("PE_PriceDir") or "→",
            }
        )
    return normalized


def build_feature_frame(
    rows: list[dict[str, Any]],
    spot: float | None,
    symbol: str,
    expiry: str | None,
    timestamp: str | None,
) -> dict[str, Any]:
    if not rows:
        return {
            "meta": {"symbol": symbol, "expiry": expiry, "timestamp": timestamp, "spot": spot},
            "rows": [],
            "atm_row": None,
            "strike_gap": 0.0,
            "pcr": 1.0,
            "totals": {},
            "atr_proxy": 0.0,
        }

    sorted_rows = sorted(rows, key=lambda r: r["strike"])
    strikes = [r["strike"] for r in sorted_rows]
    strike_diffs = [abs(strikes[i] - strikes[i - 1]) for i in range(1, len(strikes))]
    strike_gap = strike_diffs[0] if strike_diffs else 50.0

    atm_row = min(sorted_rows, key=lambda r: abs(r["strike"] - (spot or 0)))

    ce_total_oi = sum(r["CE_OI"] for r in sorted_rows)
    pe_total_oi = sum(r["PE_OI"] for r in sorted_rows)
    ce_total_vol = sum(r["CE_Volume"] for r in sorted_rows)
    pe_total_vol = sum(r["PE_Volume"] for r in sorted_rows)
    pcr = (pe_total_oi / ce_total_oi) if ce_total_oi else 1.0

    # ATR proxy for option-chain-only context (replace with real ATR when available).
    atr_proxy = max(strike_gap, (max(strikes) - min(strikes)) / max(1, len(strikes)))

    return {
        "meta": {"symbol": symbol, "expiry": expiry, "timestamp": timestamp, "spot": spot},
        "rows": sorted_rows,
        "atm_row": atm_row,
        "strike_gap": float(strike_gap),
        "pcr": float(pcr),
        "totals": {
            "ce_total_oi": ce_total_oi,
            "pe_total_oi": pe_total_oi,
            "ce_total_vol": ce_total_vol,
            "pe_total_vol": pe_total_vol,
        },
        "atr_proxy": float(atr_proxy),
    }
