from __future__ import annotations

from typing import Any


def _safe_number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _extract_step(strikes: list[float]) -> float:
    if len(strikes) < 2:
        return 50.0
    ordered = sorted(set(strikes))
    diffs = [ordered[idx + 1] - ordered[idx] for idx in range(len(ordered) - 1)]
    positive_diffs = [diff for diff in diffs if diff > 0]
    return min(positive_diffs) if positive_diffs else 50.0


def _normalize_scores(raw_scores: list[float]) -> list[float]:
    if not raw_scores:
        return []
    min_score = min(raw_scores)
    max_score = max(raw_scores)
    if max_score == min_score:
        return [50.0 for _ in raw_scores]
    scale = max_score - min_score
    return [round(((score - min_score) / scale) * 100.0, 2) for score in raw_scores]


def detect_support_resistance(option_chain: dict[str, Any]) -> dict[str, Any]:
    spot = _safe_number(option_chain.get("spot"))
    rows = option_chain.get("data") or []
    if not rows:
        return {
            "support": None,
            "resistance": None,
            "support_score": 0.0,
            "resistance_score": 0.0,
            "market_bias": "neutral",
            "trap_zone": False,
        }

    strikes = [_safe_number(row.get("strike")) for row in rows]
    strike_step = _extract_step(strikes)
    max_distance = strike_step * 10

    filtered_rows = [
        row for row in rows
        if abs(_safe_number(row.get("strike")) - spot) <= max_distance
    ]
    if not filtered_rows:
        filtered_rows = rows

    ce_raw_scores: list[float] = []
    pe_raw_scores: list[float] = []

    for row in filtered_rows:
        strike = _safe_number(row.get("strike"))
        distance = abs(strike - spot)

        ce = row.get("CE") or {}
        pe = row.get("PE") or {}

        ce_oi = _safe_number(ce.get("oi"))
        ce_oi_change = max(_safe_number(ce.get("oi_change")), 0.0)
        ce_volume = _safe_number(ce.get("volume"))

        pe_oi = _safe_number(pe.get("oi"))
        pe_oi_change = max(_safe_number(pe.get("oi_change")), 0.0)
        pe_volume = _safe_number(pe.get("volume"))

        ce_raw_scores.append((ce_oi * 0.45) + (ce_oi_change * 0.30) + (ce_volume * 0.15) - (distance * 0.10))
        pe_raw_scores.append((pe_oi * 0.45) + (pe_oi_change * 0.30) + (pe_volume * 0.15) - (distance * 0.10))

    ce_scores = _normalize_scores(ce_raw_scores)
    pe_scores = _normalize_scores(pe_raw_scores)

    best_ce_index = max(range(len(filtered_rows)), key=lambda idx: ce_scores[idx])
    best_pe_index = max(range(len(filtered_rows)), key=lambda idx: pe_scores[idx])

    resistance = int(_safe_number(filtered_rows[best_ce_index].get("strike")))
    support = int(_safe_number(filtered_rows[best_pe_index].get("strike")))
    resistance_score = ce_scores[best_ce_index]
    support_score = pe_scores[best_pe_index]

    if support_score > resistance_score + 10:
        market_bias = "bullish"
    elif resistance_score > support_score + 10:
        market_bias = "bearish"
    else:
        market_bias = "neutral"

    trap_zone = (
        spot > 0
        and abs(resistance - support) < (spot * 0.012)
        and support_score > 70
        and resistance_score > 70
    )

    return {
        "support": support,
        "resistance": resistance,
        "support_score": round(support_score, 2),
        "resistance_score": round(resistance_score, 2),
        "market_bias": market_bias,
        "trap_zone": trap_zone,
    }
