from __future__ import annotations

from typing import Any, Dict, List, Literal


BiasLabel = Literal["Bullish", "Bearish", "Neutral"]


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _sign(x: float, eps: float = 1e-9) -> int:
    if x > eps:
        return 1
    if x < -eps:
        return -1
    return 0


def compute_bias_probability(
    option_chain_json: dict,
    price_threshold_pct: float = 0.5,
    high_volume_ratio: float = 1.2,
) -> dict[str, Any]:
    """
    Retail bias model (single authority):
    - oiDirectionalScore: 0..30
    - volumeParticipationScore: 0..25
    - priceMomentumScore: 0..25
    - putCallImbalanceScore: 0..20
    """
    records: Dict[str, Any] = option_chain_json.get("records", {}) or {}
    rows: List[Dict[str, Any]] = records.get("data", []) or []

    if not rows:
        return {
            "bullishProbability": 50.0,
            "bearishProbability": 50.0,
            "biasLabel": "Neutral",
            "confidence": 15.0,
            "detail": {
                "priceMomentumScore": 12.5,
                "oiDirectionalScore": 15.0,
                "volumeParticipationScore": 12.5,
                "putCallImbalanceScore": 10.0,
                "combinedScore": 50.0,
                "reason": "No option-chain rows",
            },
        }

    ce_oi = pe_oi = 0.0
    ce_doi = pe_doi = 0.0
    ce_vol = pe_vol = 0.0

    for row in rows:
        ce = row.get("CE", {}) or {}
        pe = row.get("PE", {}) or {}
        ce_oi += float(ce.get("openInterest", 0) or 0)
        pe_oi += float(pe.get("openInterest", 0) or 0)
        ce_doi += float(ce.get("changeinOpenInterest", 0) or 0)
        pe_doi += float(pe.get("changeinOpenInterest", 0) or 0)
        ce_vol += float(ce.get("totalTradedVolume", 0) or 0)
        pe_vol += float(pe.get("totalTradedVolume", 0) or 0)

    total_vol = ce_vol + pe_vol
    spot = float(records.get("underlyingValue", option_chain_json.get("underlyingValue", 0)) or 0)
    prev_spot = (
        option_chain_json.get("underlyingPrevClose")
        or option_chain_json.get("prevClose")
        or option_chain_json.get("previousClose")
        or records.get("underlyingPrevClose")
        or records.get("prevClose")
        or records.get("previousClose")
    )

    if prev_spot and float(prev_spot) != 0:
        price_change_pct = ((spot - float(prev_spot)) / float(prev_spot)) * 100.0
        z_price = _clamp(price_change_pct / max(price_threshold_pct * 4.0, 1e-9), -1.0, 1.0)
        price_momentum_score = 12.5 + (z_price * 12.5)
    else:
        price_change_pct = 0.0
        price_momentum_score = 12.5
    price_momentum_score = _clamp(price_momentum_score, 0.0, 25.0)

    oi_delta = pe_doi - ce_doi
    oi_norm = oi_delta / (abs(pe_doi) + abs(ce_doi) + 1e-9)
    oi_directional_score = _clamp(15.0 + (oi_norm * 15.0), 0.0, 30.0)

    avg_volume_input = float(option_chain_json.get("avgVolume", 0) or 0)
    if avg_volume_input > 0:
        baseline_total = avg_volume_input * len(rows)
    else:
        baseline_total = total_vol

    volume_ratio = total_vol / max(baseline_total, 1e-9)
    direction_hint = _sign(price_change_pct) + _sign(oi_norm)
    direction_hint = 1 if direction_hint > 0 else -1 if direction_hint < 0 else 0
    if volume_ratio >= 1.0:
        # Above-average volume: boost score in the direction of the bias signal.
        intensity = _clamp((volume_ratio - 1.0) / max(high_volume_ratio - 1.0, 1e-9), 0.0, 1.0)
        volume_participation_score = _clamp(12.5 + (direction_hint * intensity * 12.5), 0.0, 25.0)
    else:
        # Below-average volume: dampen conviction proportionally toward 0.
        volume_participation_score = _clamp(12.5 * volume_ratio, 0.0, 25.0)

    pcr = pe_oi / max(ce_oi, 1e-9)
    pcr_bias = _clamp((1.0 - pcr) / 0.5, -1.0, 1.0)
    put_call_imbalance_score = _clamp(10.0 + (pcr_bias * 10.0), 0.0, 20.0)

    combined_score = _clamp(
        price_momentum_score + oi_directional_score + volume_participation_score + put_call_imbalance_score,
        0.0,
        100.0,
    )
    bullish_probability = round(combined_score, 2)
    bearish_probability = round(100.0 - combined_score, 2)

    if bullish_probability >= 52.5:
        bias_label: BiasLabel = "Bullish"
    elif bullish_probability <= 47.5:
        bias_label = "Bearish"
    else:
        bias_label = "Neutral"

    signal_dirs = [_sign(price_change_pct), _sign(oi_norm), _sign(pcr_bias)]
    active = [s for s in signal_dirs if s != 0]
    model_dir = 1 if bullish_probability > 50 else -1 if bullish_probability < 50 else 0
    if model_dir == 0 or not active:
        agreement_ratio = 0.5
    else:
        agreement_ratio = sum(1 for s in active if s == model_dir) / len(active)

    spread = abs(bullish_probability - bearish_probability)
    confidence = round(_clamp(spread, 20.0, 90.0), 2)

    return {
        "bullishProbability": bullish_probability,
        "bearishProbability": bearish_probability,
        "biasLabel": bias_label,
        "confidence": confidence,
        "bias": bias_label,
        "probability_bull": bullish_probability,
        "probability_bear": bearish_probability,
        "detail": {
            "priceMomentumScore": round(price_momentum_score, 2),
            "oiDirectionalScore": round(oi_directional_score, 2),
            "volumeParticipationScore": round(volume_participation_score, 2),
            "putCallImbalanceScore": round(put_call_imbalance_score, 2),
            "combinedScore": round(combined_score, 2),
            "priceChangePct": round(price_change_pct, 4),
            "oiDelta": round(oi_delta, 2),
            "volumeRatio": round(volume_ratio, 4),
            "pcr": round(pcr, 4),
            "agreementRatio": round(agreement_ratio, 4),
            "spread": round(spread, 2),
        },
    }
