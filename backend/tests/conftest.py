from __future__ import annotations

import pytest


@pytest.fixture
def mock_snapshot() -> dict:
    return {
        "spot": 25300,
        "support": 25250,
        "resistance": 25400,
        "alignment_ratio": 0.65,
        "confidence": 0.72,
        "volatility_state": "Stable",
        "expected_move": 120,
    }
