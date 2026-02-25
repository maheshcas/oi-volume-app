from typing import Any, Literal


def _score_row(row: dict[str, Any], option_type: Literal["CE", "PE"], max_vals: dict[str, float]) -> float:
    if option_type == "CE":
        oi = row["CE_OI"]
        doi = max(0.0, row["CE_DeltaOI"])
        vol = row["CE_Volume"]
        oi_max, doi_max, vol_max = max_vals["ce_oi"], max_vals["ce_doi"], max_vals["ce_vol"]
    else:
        oi = row["PE_OI"]
        doi = max(0.0, row["PE_DeltaOI"])
        vol = row["PE_Volume"]
        oi_max, doi_max, vol_max = max_vals["pe_oi"], max_vals["pe_doi"], max_vals["pe_vol"]

    score = (0.5 * oi / max(1.0, oi_max)) + (0.3 * doi / max(1.0, doi_max)) + (0.2 * vol / max(1.0, vol_max))
    return round(score * 100, 2)


def identify_strongest_ce_resistance(rows: list[dict[str, Any]]) -> dict[str, Any]:
    max_vals = {
        "ce_oi": max((r["CE_OI"] for r in rows), default=1.0),
        "ce_doi": max((max(0.0, r["CE_DeltaOI"]) for r in rows), default=1.0),
        "ce_vol": max((r["CE_Volume"] for r in rows), default=1.0),
        "pe_oi": 1.0,
        "pe_doi": 1.0,
        "pe_vol": 1.0,
    }
    scored = [{"strike": r["strike"], "score": _score_row(r, "CE", max_vals)} for r in rows]
    best = max(scored, key=lambda x: x["score"], default={"strike": None, "score": 0})
    return {"strike": best["strike"], "score": best["score"], "levels": sorted(scored, key=lambda x: x["score"], reverse=True)[:5]}


def identify_strongest_pe_support(rows: list[dict[str, Any]]) -> dict[str, Any]:
    max_vals = {
        "pe_oi": max((r["PE_OI"] for r in rows), default=1.0),
        "pe_doi": max((max(0.0, r["PE_DeltaOI"]) for r in rows), default=1.0),
        "pe_vol": max((r["PE_Volume"] for r in rows), default=1.0),
        "ce_oi": 1.0,
        "ce_doi": 1.0,
        "ce_vol": 1.0,
    }
    scored = [{"strike": r["strike"], "score": _score_row(r, "PE", max_vals)} for r in rows]
    best = max(scored, key=lambda x: x["score"], default={"strike": None, "score": 0})
    return {"strike": best["strike"], "score": best["score"], "levels": sorted(scored, key=lambda x: x["score"], reverse=True)[:5]}


def run_sr_engine(features: dict[str, Any]) -> dict[str, Any]:
    rows = features["rows"]
    if not rows:
        return {"resistance": {"strike": None, "score": 0}, "support": {"strike": None, "score": 0}}
    return {
        "resistance": identify_strongest_ce_resistance(rows),
        "support": identify_strongest_pe_support(rows),
    }
