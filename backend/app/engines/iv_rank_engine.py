from __future__ import annotations
from typing import Any


def compute_iv_rank(
    current_iv: float,
    iv_history: list[float],
) -> dict[str, Any]:
    if not iv_history or len(iv_history) < 5:
        return {
            "iv_rank": None,
            "iv_percentile": None,
            "iv_context": "insufficient_history",
            "selling_favoured": False,
        }

    low = min(iv_history)
    high = max(iv_history)
    iv_range = high - low

    if iv_range < 0.001:
        rank = 50.0
    else:
        rank = ((current_iv - low) / iv_range) * 100

    percentile = sum(1 for v in iv_history if v <= current_iv) / len(iv_history) * 100

    if rank >= 70:
        context = "IV elevated — selling favoured"
        selling_favoured = True
    elif rank <= 30:
        context = "IV depressed — buying favoured"
        selling_favoured = False
    else:
        context = "IV neutral — direction-based decision"
        selling_favoured = False

    return {
        "iv_rank": round(rank, 1),
        "iv_percentile": round(percentile, 1),
        "iv_context": context,
        "selling_favoured": selling_favoured,
        "current_iv": round(current_iv * 100, 2),
        "iv_52w_low": round(low * 100, 2),
        "iv_52w_high": round(high * 100, 2),
    }
