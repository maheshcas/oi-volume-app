from typing import Any


def detect_fake_breakout(
    breakout: dict[str, Any], oi_alignment: str, atm_participation: float, volume_expansion: bool
) -> tuple[bool, float]:
    breakout_attempt = breakout.get("breakout_up") or breakout.get("breakout_down")
    if not breakout_attempt:
        return False, 0.0

    score = 0.0
    if atm_participation < 0.4:
        score += 45
    if not volume_expansion:
        score += 30
    if breakout.get("breakout_up") and oi_alignment != "bullish":
        score += 25
    if breakout.get("breakout_down") and oi_alignment != "bearish":
        score += 25

    return score >= 60, min(100.0, score)


def run_trap_engine(features: dict[str, Any], breakout: dict[str, Any], oi: dict[str, Any], volume: dict[str, Any]) -> dict[str, Any]:
    is_trap, trap_prob = detect_fake_breakout(
        breakout=breakout,
        oi_alignment=oi.get("alignment", "mixed"),
        atm_participation=float(volume.get("atm_participation") or 0),
        volume_expansion=bool(volume.get("volume_expansion")),
    )
    return {"is_trap": is_trap, "trap_probability_pct": int(round(trap_prob))}
