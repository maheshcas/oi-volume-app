import logging

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
        return "Low Interest", "Low participation at this strike."
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

def _percentile(values, p):
    if not values:
        return 0.0
    ordered = sorted(float(v) for v in values)
    if len(ordered) == 1:
        return ordered[0]
    idx = (len(ordered) - 1) * max(0.0, min(1.0, float(p)))
    lo = int(idx)
    hi = min(lo + 1, len(ordered) - 1)
    frac = idx - lo
    return ordered[lo] * (1 - frac) + ordered[hi] * frac

MIN_STRIKE_TOTAL_OI = 10000.0

logger = logging.getLogger("optionlens.parser")


def _strike_ladder_interpretation(ce_oi, pe_oi, strike=None, spot=None, min_oi_threshold=MIN_STRIKE_TOTAL_OI):
    ce_oi = float(ce_oi or 0)
    pe_oi = float(pe_oi or 0)
    total_oi = ce_oi + pe_oi
    pe_share = ((pe_oi / total_oi) * 100.0) if total_oi > 0 else 50.0

    if total_oi < float(min_oi_threshold):
        label = "Low Interest"
    elif pe_share >= 60.0:
        label = "PE Dominant"
    elif pe_share <= 40.0:
        label = "CE Dominant"
    else:
        label = "Mixed"

    dominance_distance = abs(pe_share - 50.0)
    if dominance_distance >= 20.0:
        strength = "High"
    elif dominance_distance >= 10.0:
        strength = "Medium"
    else:
        strength = "Low"

    strike_value = float(strike) if strike is not None else None
    spot_value = float(spot) if spot is not None else None
    if label == "Low Interest":
        description = "Low participation at this strike."
    elif label == "PE Dominant":
        if strike_value is not None and spot_value is not None and strike_value <= spot_value:
            description = "Strong put writing indicates support formation."
        else:
            description = "Put side interest is dominant at this strike."
    elif label == "CE Dominant":
        if strike_value is not None and spot_value is not None and strike_value >= spot_value:
            description = "Call writers defending higher strikes."
        else:
            description = "Call side interest is dominant at this strike."
    else:
        description = "Balanced positioning suggests market indecision."

    logger.debug(
        "StrikeDominance[strike=%s] ce_oi=%s pe_oi=%s pe_percent=%.2f dominance=%s strength=%s",
        strike,
        ce_oi,
        pe_oi,
        pe_share,
        label,
        strength,
    )

    return {
        "interpretation_label": label,
        "strength_level": strength,
        "interpretation_description": description,
        "pe_percent": round(pe_share, 2),
        "dominance": label,
    }

def build_strike_ladder_interpretations(rows):
    """
    Returns only strike-ladder interpretation objects:
    {
      strike,
      interpretation_label,
      strength_level
    }
    """
    if not rows:
        return []
    output = []
    for r in rows:
        strike = r.get("strike")
        interp = _strike_ladder_interpretation(
            ce_oi=r.get("CE_OI", 0) or 0,
            pe_oi=r.get("PE_OI", 0) or 0,
            strike=r.get("strike"),
            spot=r.get("spot"),
            min_oi_threshold=MIN_STRIKE_TOTAL_OI,
        )
        output.append(
            {
                "strike": strike,
                "interpretation_label": interp["interpretation_label"],
                "strength_level": interp["strength_level"],
                "interpretation_description": interp["interpretation_description"],
                "pe_percent": interp["pe_percent"],
                "dominance": interp["dominance"],
            }
        )
    return output


def build_oi_volume_summary(nse_json, expiry: str | None = None):
    records = nse_json.get("records", {})
    data = records.get("data", [])
    spot = records.get("underlyingValue")
    expiry_filter = str(expiry or "").strip().lower()
    if expiry_filter:
        data = [
            item
            for item in data
            if str(item.get("expiryDate", "")).strip().lower() == expiry_filter
        ]

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

        ladder_interp = _strike_ladder_interpretation(
            ce_oi=ce_oi,
            pe_oi=pe_oi,
            strike=strike,
            spot=spot,
            min_oi_threshold=MIN_STRIKE_TOTAL_OI,
        )

        rows.append({
            "strike": strike,
            "spot": spot,
            "CE_OI": ce_oi,
            "CE_DeltaOI": ce_doi,
            "CE_Volume": ce_vol,
            "CE_LastPrice": ce_last,
            "CE_IV": float(ce.get("impliedVolatility", 0) or 0),
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
            "PE_IV": float(pe.get("impliedVolatility", 0) or 0),
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
            "signal": signal,
            "strike_interpretation": {
                "strike": strike,
                "interpretation_label": ladder_interp["interpretation_label"],
                "strength_level": ladder_interp["strength_level"],
                "interpretation_description": ladder_interp["interpretation_description"],
                "pe_percent": ladder_interp["pe_percent"],
                "dominance": ladder_interp["dominance"],
            },
            "strike_interpretation_label": ladder_interp["interpretation_label"],
            "strike_interpretation_strength": ladder_interp["strength_level"],
            "strike_interpretation_description": ladder_interp["interpretation_description"],
            "pe_oi": pe_oi,
            "ce_oi": ce_oi,
            "pe_percent": ladder_interp["pe_percent"],
            "dominance": ladder_interp["dominance"],
            "interpretation": ladder_interp["interpretation_description"],
        })

    return rows


def build_target_projection(
    rows,
    spot,
    break_buffer_ratio=0.10,
    midpoint_buffer_ratio=0.10,
    target_mode="fixed",
    confidence_score=1.0,
):
    """
    Clean target projection logic:
    - RANGE: rotate to opposite edge based on midpoint.
    - BREAKOUT_UP: project 0.5x and 1.0x range above resistance.
    - BREAKOUT_DOWN: project 0.5x and 1.0x range below support.
    """
    if not rows or spot is None:
        return None

    valid_rows = [r for r in rows if r.get("strike") is not None]
    if not valid_rows:
        return None

    resistance_row = max(valid_rows, key=lambda r: r.get("CE_OI", 0) or 0)
    support_row = max(valid_rows, key=lambda r: r.get("PE_OI", 0) or 0)

    resistance = resistance_row.get("strike")
    support = support_row.get("strike")

    if resistance is None or support is None:
        return None

    # Keep ordering stable even if OI-led levels invert.
    if support > resistance:
        support, resistance = resistance, support

    range_width = max(1.0, float(resistance - support))
    mid_point = (float(support) + float(resistance)) / 2.0
    break_buffer = range_width * break_buffer_ratio
    midpoint_buffer = range_width * midpoint_buffer_ratio

    state = "RANGE"
    if spot > (resistance + break_buffer):
        state = "BREAKOUT_UP"
    elif spot < (support - break_buffer):
        state = "BREAKOUT_DOWN"

    direction = "Range rotation"
    target_primary = None
    target_secondary = None
    target_note = None

    # Breakout confirmation checks (doc-aligned)
    atm_row = min(valid_rows, key=lambda r: abs(float(r.get("strike", 0)) - float(spot)))
    ce_avg_volume = sum((r.get("CE_Volume", 0) or 0) for r in valid_rows) / max(1, len(valid_rows))
    pe_avg_volume = sum((r.get("PE_Volume", 0) or 0) for r in valid_rows) / max(1, len(valid_rows))
    total_ce_oi = sum((r.get("CE_OI", 0) or 0) for r in valid_rows)
    total_pe_oi = sum((r.get("PE_OI", 0) or 0) for r in valid_rows)
    pcr = (total_pe_oi / total_ce_oi) if total_ce_oi else None

    atm_oi_rising = ((atm_row.get("CE_DeltaOI", 0) or 0) + (atm_row.get("PE_DeltaOI", 0) or 0)) > 0
    ce_unwinding = (atm_row.get("CE_DeltaOI", 0) or 0) < 0
    pe_aggressive_build = (atm_row.get("PE_DeltaOI", 0) or 0) > 0 and (atm_row.get("PE_Volume", 0) or 0) >= (
        pe_avg_volume * 1.2
    )

    pe_unwinding = (atm_row.get("PE_DeltaOI", 0) or 0) < 0
    ce_aggressive_build = (atm_row.get("CE_DeltaOI", 0) or 0) > 0 and (atm_row.get("CE_Volume", 0) or 0) >= (
        ce_avg_volume * 1.2
    )
    pcr_below_085 = pcr is not None and pcr < 0.85

    confirmation = {
        "bullish": {
            "atm_oi_rising": atm_oi_rising,
            "ce_unwinding": ce_unwinding,
            "pe_aggressive_build": pe_aggressive_build,
            "confirmed": atm_oi_rising and ce_unwinding and pe_aggressive_build,
        },
        "bearish": {
            "pe_unwinding": pe_unwinding,
            "ce_aggressive_build": ce_aggressive_build,
            "pcr_below_085": pcr_below_085,
            "confirmed": pe_unwinding and ce_aggressive_build and pcr_below_085,
        },
        "pcr": round(pcr, 4) if pcr is not None else None,
        "atmStrike": atm_row.get("strike"),
    }

    c = max(0.1, min(1.5, float(confidence_score or 1.0)))

    # Volatility-adjusted expected move using ATM straddle (CE LTP + PE LTP).
    atm_ce_ltp = float(atm_row.get("CE_LastPrice", 0) or 0)
    atm_pe_ltp = float(atm_row.get("PE_LastPrice", 0) or 0)
    expected_move = max(1.0, atm_ce_ltp + atm_pe_ltp)
    structural_range = range_width
    blended_move = (structural_range * 0.6) + (expected_move * 0.4)

    if target_mode == "dynamic":
        projected_move = blended_move * c
    else:
        projected_move = blended_move

    if state == "RANGE":
        target_primary = round(float(spot) + expected_move, 2)
        target_secondary = round(float(spot) - expected_move, 2)
        direction = "Volatility range"
        if abs(float(spot) - mid_point) < midpoint_buffer:
            target_note = "Balanced near midpoint; both edges possible"
        elif float(spot) < mid_point:
            target_note = "Bias to upside edge within range"
        else:
            target_note = "Bias to downside edge within range"
    elif state == "BREAKOUT_UP":
        direction = "Upside breakout expansion"
        target_primary = round(resistance + (0.8 * projected_move), 2)
        target_secondary = round(resistance + projected_move, 2)
        if not confirmation["bullish"]["confirmed"]:
            target_note = "Possible bull trap: breakout confirmation weak"
    else:
        direction = "Downside breakout expansion"
        target_primary = round(support - (0.8 * projected_move), 2)
        target_secondary = round(support - projected_move, 2)
        if not confirmation["bearish"]["confirmed"]:
            target_note = "Possible bear trap: breakdown confirmation weak"

    return {
        "state": state,
        "spot": spot,
        "support": support,
        "resistance": resistance,
        "rangeWidth": round(range_width, 2),
        "midPoint": round(mid_point, 2),
        "distanceToSupport": round(float(spot) - float(support), 2),
        "distanceToResistance": round(float(resistance) - float(spot), 2),
        "breakBuffer": round(break_buffer, 2),
        "midpointBuffer": round(midpoint_buffer, 2),
        "targetMode": target_mode,
        "confidenceScore": round(c, 2),
        "volatilityMethod": "atm_straddle",
        "atmCallLtp": round(atm_ce_ltp, 2),
        "atmPutLtp": round(atm_pe_ltp, 2),
        "expectedMove": round(expected_move, 2),
        "structuralRange": round(structural_range, 2),
        "blendedMove": round(blended_move, 2),
        "projectedMove": round(projected_move, 2),
        "direction": direction,
        "targetPrimary": target_primary,
        "targetSecondary": target_secondary,
        "targetNote": target_note,
        "confirmation": confirmation,
        "source": {
            "supportFrom": "Highest PE OI strike",
            "resistanceFrom": "Highest CE OI strike",
        },
    }
