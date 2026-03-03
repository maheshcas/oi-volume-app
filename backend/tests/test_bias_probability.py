from __future__ import annotations

import pytest

from app.engines.bias_probability_engine import compute_bias_probability


def _build_snapshot(
    *,
    spot: float = 25300,
    prev_close: float = 25200,
    ce_oi: float = 100000,
    pe_oi: float = 120000,
    ce_doi: float = 5000,
    pe_doi: float = 9000,
    ce_vol: float = 200000,
    pe_vol: float = 220000,
    avg_volume: float | None = None,
) -> dict:
    payload = {
        "records": {
            "underlyingValue": spot,
            "previousClose": prev_close,
            "data": [
                {
                    "CE": {
                        "openInterest": ce_oi,
                        "changeinOpenInterest": ce_doi,
                        "totalTradedVolume": ce_vol,
                    },
                    "PE": {
                        "openInterest": pe_oi,
                        "changeinOpenInterest": pe_doi,
                        "totalTradedVolume": pe_vol,
                    },
                }
            ],
        }
    }
    if avg_volume is not None:
        payload["avgVolume"] = avg_volume
    return payload


@pytest.mark.parametrize(
    "name,payload,expected_bias",
    [
        (
            "bullish_dominant",
            _build_snapshot(
                spot=25500,
                prev_close=25200,
                ce_oi=90000,
                pe_oi=150000,
                ce_doi=2000,
                pe_doi=12000,
                ce_vol=180000,
                pe_vol=260000,
            ),
            "Bullish",
        ),
        (
            "bearish_dominant",
            _build_snapshot(
                spot=25000,
                prev_close=25250,
                ce_oi=180000,
                pe_oi=90000,
                ce_doi=15000,
                pe_doi=2000,
                ce_vol=260000,
                pe_vol=170000,
            ),
            "Bearish",
        ),
    ],
)
def test_bias_dominant_scenarios(name: str, payload: dict, expected_bias: str) -> None:
    result = compute_bias_probability(payload)
    assert result["biasLabel"] == expected_bias, name
    assert 0 <= result["bullishProbability"] <= 100
    assert 0 <= result["bearishProbability"] <= 100
    assert pytest.approx(100.0, abs=1e-6) == result["bullishProbability"] + result["bearishProbability"]


def test_neutral_scenario_difference_less_than_5_percent() -> None:
    payload = _build_snapshot(
        spot=25200,
        prev_close=25200,
        ce_oi=120000,
        pe_oi=120000,
        ce_doi=8000,
        pe_doi=8000,
        ce_vol=200000,
        pe_vol=200000,
        avg_volume=450000,  # keeps volume around neutral
    )
    result = compute_bias_probability(payload)
    diff = abs(result["bullishProbability"] - result["bearishProbability"])
    assert diff < 5.0
    assert result["biasLabel"] == "Neutral"


def test_low_volume_participation() -> None:
    payload = _build_snapshot(
        spot=25300,
        prev_close=25280,
        ce_vol=25000,
        pe_vol=25000,
        avg_volume=200000,  # very low realized ratio
    )
    result = compute_bias_probability(payload)
    vol_score = result["detail"]["volumeParticipationScore"]
    assert 0 <= vol_score <= 20
    assert vol_score <= 10.5


def test_probability_sum_equals_100() -> None:
    payload = _build_snapshot()
    result = compute_bias_probability(payload)
    assert pytest.approx(100.0, abs=1e-6) == result["bullishProbability"] + result["bearishProbability"]
