def _direction(value, zero_threshold=0):
    if value > zero_threshold:
        return "↑"
    if value < -zero_threshold:
        return "↓"
    return "→"


def build_oi_volume_summary(nse_json):
    records = nse_json.get("records", {})
    data = records.get("data", [])
    spot = records.get("underlyingValue")

    # Use average volume as proxy baseline for "high" volume
    ce_vols = []
    pe_vols = []
    for item in data:
        ce = item.get("CE", {})
        pe = item.get("PE", {})
        ce_vols.append(ce.get("totalTradedVolume", 0) or 0)
        pe_vols.append(pe.get("totalTradedVolume", 0) or 0)
    ce_avg_vol = sum(ce_vols) / len(ce_vols) if ce_vols else 0
    pe_avg_vol = sum(pe_vols) / len(pe_vols) if pe_vols else 0

    rows = []

    for item in data:
        strike = item.get("strikePrice")

        ce = item.get("CE", {})
        pe = item.get("PE", {})

        ce_oi = ce.get("openInterest", 0)
        ce_doi = ce.get("changeinOpenInterest", 0)
        ce_vol = ce.get("totalTradedVolume", 0)
        ce_last = ce.get("lastPrice", 0)
        ce_change = ce.get("change", 0)

        pe_oi = pe.get("openInterest", 0)
        pe_doi = pe.get("changeinOpenInterest", 0)
        pe_vol = pe.get("totalTradedVolume", 0)
        pe_last = pe.get("lastPrice", 0)
        pe_change = pe.get("change", 0)

        # Simple signal logic
        if pe_doi > ce_doi and pe_vol > ce_vol:
            signal = "PE Buildup (Bearish)"
        elif ce_doi > pe_doi and ce_vol > pe_vol:
            signal = "CE Buildup (Bullish)"
        else:
            signal = "Neutral"

        # Core interpretation matrix (per side)
        ce_price_dir = _direction(ce_change)
        ce_oi_dir = _direction(ce_doi)
        ce_vol_dir = "↑" if ce_vol > ce_avg_vol else "↓"

        pe_price_dir = _direction(pe_change)
        pe_oi_dir = _direction(pe_doi)
        pe_vol_dir = "↑" if pe_vol > pe_avg_vol else "↓"

        def interpret(price_dir, oi_dir, vol_dir):
            if price_dir == "↑" and oi_dir == "↑" and vol_dir == "↑":
                return "Strong Long Build-up"
            if price_dir == "↓" and oi_dir == "↑" and vol_dir == "↑":
                return "Strong Short Build-up"
            if price_dir == "↑" and oi_dir == "↓" and vol_dir == "↑":
                return "Short Covering"
            if price_dir == "↓" and oi_dir == "↓" and vol_dir == "↑":
                return "Long Unwinding"
            if price_dir == "→" and oi_dir == "↑" and vol_dir == "↓":
                return "Quiet Accumulation"
            if price_dir == "→" and oi_dir == "↓" and vol_dir == "↓":
                return "No Interest"
            return "Mixed"

        rows.append({
            "strike": strike,
            "spot": spot,
            "CE_OI": ce_oi,
            "CE_DeltaOI": ce_doi,
            "CE_Volume": ce_vol,
            "CE_LastPrice": ce_last,
            "CE_PriceChange": ce_change,
            "CE_PriceDir": ce_price_dir,
            "CE_OIDir": ce_oi_dir,
            "CE_VolDir": ce_vol_dir,
            "CE_Interpretation": interpret(ce_price_dir, ce_oi_dir, ce_vol_dir),
            "PE_OI": pe_oi,
            "PE_DeltaOI": pe_doi,
            "PE_Volume": pe_vol,
            "PE_LastPrice": pe_last,
            "PE_PriceChange": pe_change,
            "PE_PriceDir": pe_price_dir,
            "PE_OIDir": pe_oi_dir,
            "PE_VolDir": pe_vol_dir,
            "PE_Interpretation": interpret(pe_price_dir, pe_oi_dir, pe_vol_dir),
            "signal": signal
        })

    return rows
