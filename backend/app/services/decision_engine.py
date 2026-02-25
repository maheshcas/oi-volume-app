from typing import Literal, TypedDict


OIAlignment = Literal["bullish", "bearish", "mixed"]


class DecisionInput(TypedDict):
    breakout_up: bool
    breakout_down: bool
    volume_expansion: bool
    oi_alignment: OIAlignment
    trap_signal: bool
    pcr: float
    atm_oi_strength: float


class DecisionOutput(TypedDict):
    bias: Literal["Bullish", "Bearish", "Neutral"]
    regime: Literal["Trend", "Range", "Trap Risk"]
    probability_bull: int
    probability_bear: int
    confidence: int
    explanation: str


def master_decision_engine(input_data: DecisionInput) -> DecisionOutput:
    """
    Hierarchical arbitration engine for OptionLens.

    Priority:
    1) Breakout confirmation
    2) Strong OI + volume build-up
    3) Range structure
    4) Trap override
    """
    breakout_up = bool(input_data["breakout_up"])
    breakout_down = bool(input_data["breakout_down"])
    volume_expansion = bool(input_data["volume_expansion"])
    oi_alignment: OIAlignment = input_data["oi_alignment"]
    trap_signal = bool(input_data["trap_signal"])
    pcr = float(input_data["pcr"])
    atm_oi_strength = float(input_data["atm_oi_strength"])

    bias: Literal["Bullish", "Bearish", "Neutral"] = "Neutral"
    regime: Literal["Trend", "Range", "Trap Risk"] = "Range"
    probability_bull = 50
    probability_bear = 50
    confidence = 50
    reason = "Default range state."

    breakout_confirmed_up = breakout_up and volume_expansion
    breakout_confirmed_down = breakout_down and volume_expansion

    # Reject conflicting breakout confirmations.
    if breakout_confirmed_up and breakout_confirmed_down:
        breakout_confirmed_up = False
        breakout_confirmed_down = False

    # LEVEL 1
    if breakout_confirmed_up:
        bias = "Bullish"
        regime = "Trend"
        probability_bull = 70
        probability_bear = 30
        confidence = 80
        reason = "Confirmed upside breakout with volume expansion."
    elif breakout_confirmed_down:
        bias = "Bearish"
        regime = "Trend"
        probability_bull = 30
        probability_bear = 70
        confidence = 80
        reason = "Confirmed downside breakout with volume expansion."

    # LEVEL 2
    elif oi_alignment in ("bullish", "bearish") and volume_expansion:
        regime = "Trend"
        confidence = 62
        if oi_alignment == "bullish":
            bias = "Bullish"
            probability_bull = 60
            probability_bear = 40
            reason = "OI and volume alignment indicates bullish developing trend."
        else:
            bias = "Bearish"
            probability_bull = 40
            probability_bear = 60
            reason = "OI and volume alignment indicates bearish developing trend."

    # LEVEL 3
    else:
        bias = "Neutral"
        regime = "Range"
        probability_bull = 50
        probability_bear = 50
        confidence = 48
        reason = "No strong directional confirmation; structure favors range."
        if pcr >= 1.2:
            probability_bull = 47
            probability_bear = 53
            reason += " PCR leans mildly bearish."
        elif pcr <= 0.8:
            probability_bull = 53
            probability_bear = 47
            reason += " PCR leans mildly bullish."

    # LEVEL 4 override
    breakout_attempt = breakout_up or breakout_down
    weak_atm_oi = atm_oi_strength < 0.4
    if trap_signal or (breakout_attempt and weak_atm_oi):
        regime = "Trap Risk"
        confidence = max(0, confidence - 20)
        reason += " Trap override applied due to weak ATM OI confirmation."

    return {
        "bias": bias,
        "regime": regime,
        "probability_bull": int(probability_bull),
        "probability_bear": int(probability_bear),
        "confidence": int(confidence),
        "explanation": reason,
    }


def build_decision_input(rows, spot, support, resistance, break_buffer=0.0) -> DecisionInput:
    """
    Build DecisionInput from parsed option rows.
    """
    if not rows:
        return {
            "breakout_up": False,
            "breakout_down": False,
            "volume_expansion": False,
            "oi_alignment": "mixed",
            "trap_signal": False,
            "pcr": 1.0,
            "atm_oi_strength": 0.0,
        }

    ce_total_oi = sum((r.get("CE_OI", 0) or 0) for r in rows)
    pe_total_oi = sum((r.get("PE_OI", 0) or 0) for r in rows)
    pcr = (pe_total_oi / ce_total_oi) if ce_total_oi else 1.0

    avg_total_vol = sum(
        ((r.get("CE_Volume", 0) or 0) + (r.get("PE_Volume", 0) or 0)) for r in rows
    ) / max(1, len(rows))

    atm_row = min(rows, key=lambda r: abs((r.get("strike") or 0) - (spot or 0)))
    atm_total_vol = (atm_row.get("CE_Volume", 0) or 0) + (atm_row.get("PE_Volume", 0) or 0)
    volume_expansion = atm_total_vol > (avg_total_vol * 1.2)

    ce_doi = atm_row.get("CE_DeltaOI", 0) or 0
    pe_doi = atm_row.get("PE_DeltaOI", 0) or 0
    if pe_doi > ce_doi:
        oi_alignment: OIAlignment = "bullish"
    elif ce_doi > pe_doi:
        oi_alignment = "bearish"
    else:
        oi_alignment = "mixed"

    abs_doi_values = [abs((r.get("CE_DeltaOI", 0) or 0)) + abs((r.get("PE_DeltaOI", 0) or 0)) for r in rows]
    avg_abs_doi = sum(abs_doi_values) / max(1, len(abs_doi_values))
    atm_abs_doi = abs(ce_doi) + abs(pe_doi)
    atm_oi_strength = min(1.0, atm_abs_doi / max(1.0, avg_abs_doi))

    breakout_up = bool(spot is not None and resistance is not None and spot > (resistance + break_buffer))
    breakout_down = bool(spot is not None and support is not None and spot < (support - break_buffer))

    trap_signal = False
    if breakout_up and not (ce_doi < 0 and pe_doi > 0):
        trap_signal = True
    if breakout_down and not (pe_doi < 0 and ce_doi > 0):
        trap_signal = True

    return {
        "breakout_up": breakout_up,
        "breakout_down": breakout_down,
        "volume_expansion": volume_expansion,
        "oi_alignment": oi_alignment,
        "trap_signal": trap_signal,
        "pcr": round(pcr, 4),
        "atm_oi_strength": round(atm_oi_strength, 4),
    }
