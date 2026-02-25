from typing import Any, Literal


OIAlignment = Literal["bullish", "bearish", "mixed"]


def detect_buildup_type(row: dict[str, Any]) -> str:
    ce_doi = float(row.get("CE_DeltaOI") or 0)
    pe_doi = float(row.get("PE_DeltaOI") or 0)
    if pe_doi > 0 and ce_doi < 0:
        return "Bullish Build-up"
    if ce_doi > 0 and pe_doi < 0:
        return "Bearish Build-up"
    if ce_doi > 0 and pe_doi > 0:
        return "Two-sided Writing"
    if ce_doi < 0 and pe_doi < 0:
        return "Unwinding"
    return "Mixed"


def calculate_oi_strength(features: dict[str, Any]) -> float:
    rows = features["rows"]
    atm_row = features["atm_row"]
    if not rows or not atm_row:
        return 0.0
    atm_abs = abs(atm_row["CE_DeltaOI"]) + abs(atm_row["PE_DeltaOI"])
    avg_abs = sum(abs(r["CE_DeltaOI"]) + abs(r["PE_DeltaOI"]) for r in rows) / max(1, len(rows))
    return min(1.0, atm_abs / max(1.0, avg_abs))


def calculate_concentration_score(rows: list[dict[str, Any]], option_type: Literal["CE", "PE"]) -> float:
    key = "CE_OI" if option_type == "CE" else "PE_OI"
    values = sorted((float(r.get(key) or 0) for r in rows), reverse=True)
    total = sum(values)
    if total <= 0:
        return 0.0
    return round(sum(values[:3]) / total, 4)


def run_oi_analysis(features: dict[str, Any]) -> dict[str, Any]:
    rows = features["rows"]
    atm_row = features["atm_row"]
    if not rows or not atm_row:
        return {"alignment": "mixed", "buildup_type": "Mixed", "oi_strength": 0.0, "concentration": {}}

    ce_doi = float(atm_row["CE_DeltaOI"])
    pe_doi = float(atm_row["PE_DeltaOI"])
    if pe_doi > ce_doi:
        alignment: OIAlignment = "bullish"
    elif ce_doi > pe_doi:
        alignment = "bearish"
    else:
        alignment = "mixed"

    return {
        "alignment": alignment,
        "buildup_type": detect_buildup_type(atm_row),
        "oi_strength": round(calculate_oi_strength(features), 4),
        "concentration": {
            "ce": calculate_concentration_score(rows, "CE"),
            "pe": calculate_concentration_score(rows, "PE"),
        },
    }
