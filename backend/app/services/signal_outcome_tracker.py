"""
Signal outcome tracker — resolves signal win/loss outcomes by walking forward
through stability logs after each signal fires.

Reads:
  backend/logs/signals/signals_{YYYYMMDD}.jsonl   ← signal fire records
  backend/logs/stability/stability_{YYYYMMDD}.jsonl ← per-cycle spot snapshots

Writes:
  backend/logs/outcomes/signal_outcomes_{YYYYMMDD}.jsonl

Entry-point for EOD: run_eod_outcome_computation()
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("optionlens.signal_outcomes")

IST = timezone(timedelta(hours=5, minutes=30))
_LOGS_DIR = Path(__file__).resolve().parents[3] / "logs"
_SIGNALS_DIR = _LOGS_DIR / "signals"
_STABILITY_DIR = _LOGS_DIR / "stability"
_OUTCOMES_DIR = _LOGS_DIR / "outcomes"

MARKET_CLOSE_HOUR = 15
MARKET_CLOSE_MINUTE = 30

_VALID_OUTCOMES = {"WIN", "LOSS", "BIG_WIN", "EXPIRED", "INCOMPLETE"}

SELL_SIGNAL_PREFIXES = ("SELL_", "REJECTION_AT_RESISTANCE", "SELL_STRADDLE")
STRADDLE_SIGNALS = ("SELL_STRADDLE", "BUY_STRADDLE", "STRADDLE")


def _ist_now() -> datetime:
    return datetime.now(IST)


def _ist_date_str(dt: datetime) -> str:
    return dt.astimezone(IST).strftime("%Y%m%d")


def _parse_ts(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    s = str(value).strip()
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
    ):
        try:
            dt = datetime.strptime(s.replace("Z", "+00:00"), fmt)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return None


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    records: list[dict] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return records


def _make_signal_id_fallback(rec: dict) -> str:
    raw = f"{rec.get('signal_type','')}|{rec.get('fired_at','')}|{round(float(rec.get('entry_underlying') or 0))}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _is_sell(signal_type: str) -> bool:
    upper = signal_type.upper()
    return any(upper.startswith(p.upper()) or upper == p.upper() for p in SELL_SIGNAL_PREFIXES)


def _is_straddle(signal_type: str) -> bool:
    upper = signal_type.upper()
    return any(upper == p.upper() for p in STRADDLE_SIGNALS)


def _session_close_for(fired_dt: datetime) -> datetime:
    """Return 15:30 IST on the same trading day as fired_dt."""
    ist = fired_dt.astimezone(IST)
    return ist.replace(hour=MARKET_CLOSE_HOUR, minute=MARKET_CLOSE_MINUTE, second=0, microsecond=0)


def compute_outcomes_for_date(date_str: str, symbol: str = "NIFTY") -> list[dict]:
    """
    Resolve outcomes for all signals fired on `date_str` (YYYYMMDD) for `symbol`.
    Returns list of outcome records.
    """
    signals_path = _SIGNALS_DIR / f"signals_{date_str}.jsonl"
    stability_path = _STABILITY_DIR / f"stability_{date_str}.jsonl"

    if not signals_path.exists():
        logger.warning("No signals file for %s on %s — skipping", symbol, date_str)
        return []
    if not stability_path.exists():
        logger.warning("No stability file for %s on %s — cannot compute outcomes", symbol, date_str)
        return []

    # Load and filter signals for this symbol
    all_signals = _read_jsonl(signals_path)
    signals = [r for r in all_signals if str(r.get("symbol", "")).upper() == symbol.upper()]
    if not signals:
        return []

    # Deduplicate signals by signal_id
    seen_ids: set[str] = set()
    deduped: list[dict] = []
    for s in signals:
        sid = str(s.get("signal_id") or _make_signal_id_fallback(s))
        if sid not in seen_ids:
            seen_ids.add(sid)
            s["signal_id"] = sid
            deduped.append(s)
    signals = deduped

    # Load stability snapshots for this symbol, sorted by time
    all_stability = _read_jsonl(stability_path)
    stability = [
        r for r in all_stability
        if str(r.get("symbol", "")).upper() == symbol.upper()
    ]
    stability.sort(key=lambda r: r.get("_epoch", 0) or 0)

    outcomes: list[dict] = []

    for sig in signals:
        entry_underlying = sig.get("entry_underlying")
        stop_underlying = sig.get("stop_underlying")
        target_1 = sig.get("target_1")
        target_2 = sig.get("target_2")
        rr_t1 = sig.get("rr_t1")
        signal_type = str(sig.get("signal_type", "")).upper()
        fired_at_raw = sig.get("fired_at")

        # Skip incomplete signals
        if entry_underlying is None or stop_underlying is None or target_1 is None:
            outcomes.append({
                **sig,
                "outcome": "INCOMPLETE",
                "outcome_at": None,
                "time_to_outcome_seconds": None,
                "final_spot": None,
                "pnl_pts": None,
                "pnl_pct": None,
            })
            continue

        fired_dt = _parse_ts(fired_at_raw)
        if fired_dt is None:
            outcomes.append({**sig, "outcome": "INCOMPLETE", "outcome_at": None,
                              "time_to_outcome_seconds": None, "final_spot": None,
                              "pnl_pts": None, "pnl_pct": None})
            continue

        session_close = _session_close_for(fired_dt)
        is_sell = _is_sell(signal_type)
        is_straddle = _is_straddle(signal_type)

        # Walk forward through stability snapshots after signal fire (±2 min tolerance for entry)
        outcome: str | None = None
        outcome_at: datetime | None = None
        final_spot: float | None = None
        last_spot: float | None = None

        for snap in stability:
            snap_ts = _parse_ts(snap.get("_ts"))
            if snap_ts is None:
                continue
            if snap_ts < fired_dt - timedelta(seconds=120):
                continue
            if snap_ts > session_close:
                break

            raw_spot = snap.get("spot_price")
            if raw_spot is None:
                continue
            spot = float(raw_spot)
            last_spot = spot

            if is_straddle:
                # Win if |spot - entry| >= atm premium (entry_underlying used as straddle reference)
                # We approximate win as spot moving more than (target_1 - entry_underlying) in either dir
                move = abs(spot - float(entry_underlying))
                win_threshold = abs(float(target_1) - float(entry_underlying))
                stop_threshold = abs(float(stop_underlying) - float(entry_underlying))
                if win_threshold > 0 and move >= win_threshold:
                    outcome = "WIN"
                    outcome_at = snap_ts
                    final_spot = spot
                    break
                if stop_threshold > 0 and move <= stop_threshold and snap_ts >= session_close - timedelta(minutes=5):
                    # Straddle decay: if we're close to close and no move, it's a loss
                    outcome = "LOSS"
                    outcome_at = snap_ts
                    final_spot = spot
                    break
            elif is_sell:
                # SELL CE: win if spot stays below T1 (resistance/T1), loss if spot breaks above stop
                # We flip: T1 is the resistance ceiling (favorable = spot below), stop is above entry
                if spot >= float(stop_underlying):
                    outcome = "LOSS"
                    outcome_at = snap_ts
                    final_spot = spot
                    break
                if spot <= float(target_1):
                    outcome = "WIN"
                    outcome_at = snap_ts
                    final_spot = spot
                    break
                if target_2 is not None and spot <= float(target_2):
                    outcome = "BIG_WIN"
                    outcome_at = snap_ts
                    final_spot = spot
                    break
            else:
                # BUY: win if spot reaches T1 above entry, loss if reaches stop below
                if spot <= float(stop_underlying):
                    outcome = "LOSS"
                    outcome_at = snap_ts
                    final_spot = spot
                    break
                if target_2 is not None and spot >= float(target_2):
                    outcome = "BIG_WIN"
                    outcome_at = snap_ts
                    final_spot = spot
                    break
                if spot >= float(target_1):
                    outcome = "WIN"
                    outcome_at = snap_ts
                    final_spot = spot
                    break

        if outcome is None:
            outcome = "EXPIRED"
            outcome_at = session_close
            final_spot = last_spot

        entry_f = float(entry_underlying)
        stop_f = float(stop_underlying)
        t1_f = float(target_1)
        final_f = float(final_spot) if final_spot is not None else entry_f

        if is_sell:
            pnl_pts = entry_f - final_f
        else:
            pnl_pts = final_f - entry_f

        pnl_pct = (pnl_pts / entry_f * 100) if entry_f > 0 else None
        seconds_to_outcome = (
            (outcome_at - fired_dt).total_seconds()
            if outcome_at and fired_dt else None
        )

        outcomes.append({
            "signal_id": sig["signal_id"],
            "signal_type": signal_type,
            "fired_at": fired_at_iso(fired_dt),
            "symbol": symbol,
            "expiry": sig.get("expiry"),
            "bias": sig.get("bias"),
            "entry_underlying": entry_f,
            "stop_underlying": stop_f,
            "target_1": t1_f,
            "target_2": target_2,
            "rr_t1": rr_t1,
            "outcome": outcome,
            "outcome_at": fired_at_iso(outcome_at) if outcome_at else None,
            "time_to_outcome_seconds": round(seconds_to_outcome) if seconds_to_outcome is not None else None,
            "final_spot": round(final_f, 1),
            "pnl_pts": round(pnl_pts, 1),
            "pnl_pct": round(pnl_pct, 3) if pnl_pct is not None else None,
            "trap_at_fire": sig.get("trap_at_fire"),
            "iv_rank_at_fire": sig.get("iv_rank_at_fire"),
            "regime_at_fire": sig.get("regime_at_fire"),
            "readiness_at_fire": sig.get("readiness_at_fire"),
        })

    assert all(o.get("outcome") in _VALID_OUTCOMES for o in outcomes), \
        "Outcome invariant violated — unexpected outcome value"

    return outcomes


def fired_at_iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.isoformat()


def write_outcomes(date_str: str, outcomes: list[dict]) -> str:
    """Write outcomes to signal_outcomes_{date_str}.jsonl. Returns path."""
    _OUTCOMES_DIR.mkdir(parents=True, exist_ok=True)
    path = _OUTCOMES_DIR / f"signal_outcomes_{date_str}.jsonl"
    with path.open("w", encoding="utf-8") as fh:
        for rec in outcomes:
            fh.write(json.dumps(rec, ensure_ascii=True, default=str) + "\n")
    logger.info("Wrote %d outcomes to %s", len(outcomes), path)
    return str(path)


def backfill_all_outcomes(symbol: str = "NIFTY") -> dict[str, Any]:
    """
    Scan signals/ for all signals_*.jsonl files. For each date without a companion
    signal_outcomes_*.jsonl, compute and write outcomes.
    """
    if not _SIGNALS_DIR.exists():
        return {"days_processed": 0, "signals_resolved": 0, "errors": []}

    days_processed = 0
    signals_resolved = 0
    errors: list[str] = []

    for signals_file in sorted(_SIGNALS_DIR.glob("signals_*.jsonl")):
        date_str = signals_file.stem.replace("signals_", "")
        outcomes_file = _OUTCOMES_DIR / f"signal_outcomes_{date_str}.jsonl"
        if outcomes_file.exists():
            logger.debug("Outcomes already exist for %s — skipping", date_str)
            continue
        try:
            outcomes = compute_outcomes_for_date(date_str, symbol=symbol)
            if outcomes:
                write_outcomes(date_str, outcomes)
                signals_resolved += len(outcomes)
            days_processed += 1
        except Exception as exc:
            msg = f"{date_str}: {exc}"
            logger.warning("Backfill error: %s", msg)
            errors.append(msg)

    return {
        "days_processed": days_processed,
        "signals_resolved": signals_resolved,
        "errors": errors,
    }


def run_eod_outcome_computation(symbol: str = "NIFTY") -> dict[str, Any]:
    """
    EOD trigger: compute outcomes for today in IST.
    Designed to be called from background_updater at ~15:35 IST.
    """
    today_str = _ist_now().strftime("%Y%m%d")
    try:
        outcomes = compute_outcomes_for_date(today_str, symbol=symbol)
        if outcomes:
            path = write_outcomes(today_str, outcomes)
            return {"status": "ok", "date": today_str, "count": len(outcomes), "path": path}
        return {"status": "no_signals", "date": today_str, "count": 0}
    except Exception as exc:
        logger.warning("EOD outcome computation failed: %s", exc)
        return {"status": "error", "date": today_str, "error": str(exc)}
