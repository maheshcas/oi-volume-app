def _direction(value, zero_threshold=0):
    if value > zero_threshold:
        return "↑"
    if value < -zero_threshold:
        return "↓"
    return "→"

def _price_direction(last_price, prev_price):
    if not prev_price:
        return "→", 0.0
    price_change_pct = ((last_price - prev_price) / prev_price) * 100
    if price_change_pct >= 0.5:
        return "↑", price_change_pct
    if price_change_pct <= -0.5:
        return "↓", price_change_pct
    return "→", price_change_pct

def _oi_direction(open_interest, prev_open_interest):
    oi_change = (open_interest or 0) - (prev_open_interest or 0)
    if not prev_open_interest:
        return "→", oi_change, 0.0
    oi_change_pct = (oi_change / prev_open_interest) * 100
    if oi_change_pct > 1:
        return "↑", oi_change, oi_change_pct
    if oi_change_pct < -1:
        return "↓", oi_change, oi_change_pct
    return "→", oi_change, oi_change_pct

def _volume_direction(volume, avg_volume, top_20_threshold):
    volume_ratio = (volume / avg_volume) if avg_volume else 0
    if volume_ratio >= 1.2 or (top_20_threshold and volume >= top_20_threshold):
        return "↑", volume_ratio
    if volume_ratio <= 0.8:
        return "↓", volume_ratio
    return "→", volume_ratio

def _interpret(price_dir, oi_dir, vol_dir):
    if price_dir == "↑" and oi_dir == "↑" and vol_dir == "↑":
        return "Strong Long Build-up", "Fresh bullish positions added aggressively."
    if price_dir == "↓" and oi_dir == "↑" and vol_dir == "↑":
        return "Strong Short Build-up", "Bearish positions building with conviction."
    if price_dir == "↑" and oi_dir == "↓" and vol_dir == "↑":
        return "Short Covering", "Short sellers exiting positions rapidly. Fast upside move possible."
    if price_dir == "↓" and oi_dir == "↓" and vol_dir == "↑":
        return "Long Unwinding", "Bulls exiting positions. Trend weakening."
    if price_dir == "→" and oi_dir == "↑" and vol_dir == "↓":
        return "Quiet Position Building", "Smart money accumulation without price movement."
    if price_dir == "→" and oi_dir == "↓" and vol_dir == "↓":
        return "No Interest Zone", "Low participation. Time decay dominates."
    return "Mixed", "Signals are not aligned."
def _confidence(price_change_pct, oi_change, volume_ratio, vol_dir):
    score = 50
    if abs(price_change_pct) >= 0.5:
        score += 15
    if abs(oi_change) > 0:
        score += 15
    if vol_dir == "↑":
        score += 20
    # Extra boost if volume is significantly above average
    if volume_ratio >= 1.5:
        score += 5
    return max(0, min(100, score))


def build_oi_volume_summary(nse_json):
    records = nse_json.get("records", {})
    data = records.get("data", [])
    spot = records.get("underlyingValue")

    # Average volume + top 20% thresholds (per option type)
    ce_vols = []
    pe_vols = []
    for item in data:
        ce = item.get("CE", {})
        pe = item.get("PE", {})
        ce_vols.append(ce.get("totalTradedVolume", 0) or 0)
        pe_vols.append(pe.get("totalTradedVolume", 0) or 0)
    ce_avg_vol = sum(ce_vols) / len(ce_vols) if ce_vols else 0
    pe_avg_vol = sum(pe_vols) / len(pe_vols) if pe_vols else 0
    ce_sorted = sorted(ce_vols, reverse=True)
    pe_sorted = sorted(pe_vols, reverse=True)
    ce_top_20 = ce_sorted[max(0, int(len(ce_sorted) * 0.2) - 1)] if ce_sorted else None
    pe_top_20 = pe_sorted[max(0, int(len(pe_sorted) * 0.2) - 1)] if pe_sorted else None

    rows = []

    for item in data:
        strike = item.get("strikePrice")

        ce = item.get("CE", {})
        pe = item.get("PE", {})

        ce_oi = ce.get("openInterest", 0)
        ce_doi = ce.get("changeinOpenInterest", 0)
        ce_vol = ce.get("totalTradedVolume", 0)
        ce_last = ce.get("lastPrice", 0)
        ce_prev = ce.get("prevPrice", ce.get("previousClose", 0))
        ce_prev_oi = ce.get("prevOpenInterest", ce.get("previousOpenInterest", ce_oi - ce_doi))

        pe_oi = pe.get("openInterest", 0)
        pe_doi = pe.get("changeinOpenInterest", 0)
        pe_vol = pe.get("totalTradedVolume", 0)
        pe_last = pe.get("lastPrice", 0)
        pe_prev = pe.get("prevPrice", pe.get("previousClose", 0))
        pe_prev_oi = pe.get("prevOpenInterest", pe.get("previousOpenInterest", pe_oi - pe_doi))

        # Simple signal logic
        if pe_doi > ce_doi and pe_vol > ce_vol:
            signal = "PE Buildup (Bearish)"
        elif ce_doi > pe_doi and ce_vol > pe_vol:
            signal = "CE Buildup (Bullish)"
        else:
            signal = "Neutral"

        # Core interpretation matrix (per side)
        ce_price_dir, ce_price_pct = _price_direction(ce_last, ce_prev)
        ce_oi_dir, ce_oi_change, ce_oi_change_pct = _oi_direction(ce_oi, ce_prev_oi)
        ce_vol_dir, ce_vol_ratio = _volume_direction(ce_vol, ce_avg_vol, ce_top_20)

        pe_price_dir, pe_price_pct = _price_direction(pe_last, pe_prev)
        pe_oi_dir, pe_oi_change, pe_oi_change_pct = _oi_direction(pe_oi, pe_prev_oi)
        pe_vol_dir, pe_vol_ratio = _volume_direction(pe_vol, pe_avg_vol, pe_top_20)

        # Noise filter
        ce_noise = abs(ce_oi_change_pct) < 0.5 and ce_vol_ratio < 1.1
        pe_noise = abs(pe_oi_change_pct) < 0.5 and pe_vol_ratio < 1.1

        ce_label, ce_desc = _interpret(ce_price_dir, ce_oi_dir, ce_vol_dir) if not ce_noise else ("Noise", "Ignored due to low OI change and volume.")
        pe_label, pe_desc = _interpret(pe_price_dir, pe_oi_dir, pe_vol_dir) if not pe_noise else ("Noise", "Ignored due to low OI change and volume.")

        ce_context = None
        pe_context = None
        if ce_label == "Strong Short Build-up":
            ce_context = "Resistance Zone"
        elif ce_label == "Short Covering":
            ce_context = "Resistance weakening"
        if pe_label == "Strong Short Build-up":
            pe_context = "Support Zone"
        elif pe_label == "Short Covering":
            pe_context = "Support strengthening"

        ce_strength = (ce_vol_ratio * 2) + abs(ce_oi_change_pct) + abs(ce_price_pct)
        pe_strength = (pe_vol_ratio * 2) + abs(pe_oi_change_pct) + abs(pe_price_pct)

        def _tag(vol_dir, oi_dir):
            if vol_dir == "↑" and oi_dir == "↑":
                return "🔥 Aggressive"
            if vol_dir == "↑" and oi_dir == "↓":
                return "⚡ Exit Activity"
            if vol_dir == "↓":
                return "💤 Low Participation"
            return "—"

        rows.append({
            "strike": strike,
            "spot": spot,
            "CE_OI": ce_oi,
            "CE_DeltaOI": ce_doi,
            "CE_Volume": ce_vol,
            "CE_LastPrice": ce_last,
            "CE_PriceChange": ce_last - ce_prev if ce_prev else 0,
            "CE_PriceDir": ce_price_dir,
            "CE_OIDir": ce_oi_dir,
            "CE_VolDir": ce_vol_dir,
            "CE_Interpretation": ce_label,
            "CE_InterpretationDesc": ce_desc,
            "CE_ConfidenceScore": _confidence(ce_price_pct, ce_oi_change, ce_vol_ratio, ce_vol_dir),
            "CE_OIChangePct": ce_oi_change_pct,
            "CE_VolumeRatio": ce_vol_ratio,
            "CE_StrengthScore": ce_strength,
            "CE_ContextTag": ce_context,
            "CE_UITag": _tag(ce_vol_dir, ce_oi_dir),
            "PE_OI": pe_oi,
            "PE_DeltaOI": pe_doi,
            "PE_Volume": pe_vol,
            "PE_LastPrice": pe_last,
            "PE_PriceChange": pe_last - pe_prev if pe_prev else 0,
            "PE_PriceDir": pe_price_dir,
            "PE_OIDir": pe_oi_dir,
            "PE_VolDir": pe_vol_dir,
            "PE_Interpretation": pe_label,
            "PE_InterpretationDesc": pe_desc,
            "PE_ConfidenceScore": _confidence(pe_price_pct, pe_oi_change, pe_vol_ratio, pe_vol_dir),
            "PE_OIChangePct": pe_oi_change_pct,
            "PE_VolumeRatio": pe_vol_ratio,
            "PE_StrengthScore": pe_strength,
            "PE_ContextTag": pe_context,
            "PE_UITag": _tag(pe_vol_dir, pe_oi_dir),
            "signal": signal
        })

    return rows
