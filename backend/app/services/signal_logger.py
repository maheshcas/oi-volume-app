"""
Signal logger — writes a signal_YYYYMMDD.jsonl record each time the engine fires
a non-WAIT directional signal. De-duplicates by (key, signal_type) so a signal
that persists across many cycles is only counted once per distinct fire event.

Called from background_updater._process_symbol() after the cycle log is built.
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("optionlens.signal_logger")

IST = timezone(timedelta(hours=5, minutes=30))
_LOGS_DIR = Path(__file__).resolve().parents[3] / "logs"
_SIGNALS_DIR = _LOGS_DIR / "signals"

# In-memory state: last logged signal_type per stream key.
# When directional_signal changes (or goes back to WAIT), we fire/clear.
_last_signal_type: dict[str, str | None] = {}


def _signals_path(date_str: str) -> Path:
    _SIGNALS_DIR.mkdir(parents=True, exist_ok=True)
    return _SIGNALS_DIR / f"signals_{date_str}.jsonl"


def _parse_zone_midpoint(zone_str: str | None) -> float | None:
    """Parse '24,323 - 24,377' → 24350.0"""
    if not zone_str:
        return None
    cleaned = str(zone_str).replace(",", "")
    parts = cleaned.split("-")
    # Handle negative numbers: "- 24,323 - 24,377" or just two values
    nums = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        try:
            nums.append(float(p))
        except ValueError:
            pass
    if len(nums) >= 2:
        return round((nums[-2] + nums[-1]) / 2, 1)
    if len(nums) == 1:
        return nums[0]
    return None


def _make_signal_id(signal_type: str, fired_at: str, entry: float | None) -> str:
    raw = f"{signal_type}|{fired_at}|{round(entry or 0)}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _ist_date_str(ts: datetime) -> str:
    ist = ts.astimezone(IST)
    return ist.strftime("%Y%m%d")


WAIT_SIGNALS = {"WAIT", "WAIT_NO_SETUP", "", None}


def maybe_log_signal(
    *,
    key: str,
    symbol: str,
    expiry: str,
    timestamp: str | datetime | None,
    spot: float | None,
    directional_signal: str | None,
    entry_zone: str | None,
    stop_zone: str | None,
    target_zone: str | None,
    support_level: float | None,
    resistance_level: float | None,
    trap_probability: float,
    iv_rank: float | None,
    regime: str | None,
    readiness: float | None,
    directional_rr: float | None,
    bias: str | None,
) -> bool:
    """
    Call once per cycle. Returns True if a new signal was logged.
    Fires when directional_signal transitions from WAIT → active or active → different active.
    """
    signal = str(directional_signal or "").strip().upper() or "WAIT"
    prev = _last_signal_type.get(key)

    # No change — nothing to log
    if signal == (prev or "WAIT"):
        if signal in WAIT_SIGNALS:
            return False
        # Same signal continuing — don't re-log
        return False

    # Update state
    _last_signal_type[key] = signal if signal not in WAIT_SIGNALS else None

    if signal in WAIT_SIGNALS:
        # Signal cleared; no log entry needed
        return False

    # Parse timestamp
    if isinstance(timestamp, str):
        try:
            fired_dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError:
            fired_dt = datetime.now(timezone.utc)
    elif isinstance(timestamp, datetime):
        fired_dt = timestamp if timestamp.tzinfo else timestamp.replace(tzinfo=timezone.utc)
    else:
        fired_dt = datetime.now(timezone.utc)

    fired_at_iso = fired_dt.isoformat()
    date_str = _ist_date_str(fired_dt)

    entry_underlying = _parse_zone_midpoint(entry_zone) or spot
    stop_underlying = _parse_zone_midpoint(stop_zone)
    target_1 = _parse_zone_midpoint(target_zone)
    # Second half of target zone as T2 proxy (use resistance/support as fallback)
    target_zone_str = str(target_zone or "").replace(",", "")
    parts = [p.strip() for p in target_zone_str.split("-") if p.strip()]
    nums = []
    for p in parts:
        try:
            nums.append(float(p))
        except ValueError:
            pass
    target_2: float | None = None
    if len(nums) >= 2:
        hi = max(nums[-2], nums[-1])
        target_2 = hi if hi != target_1 else None

    rr_t1 = float(directional_rr) if directional_rr is not None and directional_rr > 0 else None

    signal_id = _make_signal_id(signal, fired_at_iso, entry_underlying)

    record: dict[str, Any] = {
        "signal_id": signal_id,
        "fired_at": fired_at_iso,
        "symbol": symbol,
        "expiry": expiry,
        "signal_type": signal,
        "bias": bias,
        "entry_underlying": entry_underlying,
        "stop_underlying": stop_underlying,
        "target_1": target_1,
        "target_2": target_2,
        "rr_t1": rr_t1,
        "support_at_fire": support_level,
        "resistance_at_fire": resistance_level,
        "trap_at_fire": round(float(trap_probability or 0)),
        "iv_rank_at_fire": float(iv_rank) if iv_rank is not None else None,
        "regime_at_fire": str(regime or ""),
        "readiness_at_fire": round(float(readiness or 0), 1),
    }

    path = _signals_path(date_str)
    try:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=True, default=str) + "\n")
        logger.info("Signal logged: %s %s @ %.1f (id=%s)", symbol, signal, entry_underlying or 0, signal_id)
        return True
    except Exception as exc:
        logger.warning("Failed to write signal log: %s", exc)
        return False
