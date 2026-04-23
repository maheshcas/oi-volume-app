"""
Local analytics router — dev-only, localhost-restricted.
Prefix: /api/v2/local

Endpoints:
  GET /performance/summary
  GET /performance/timeline
  GET /performance/conditional
  GET /signals/raw
  POST /debug/recompute-outcomes/{date}
  POST /debug/backfill-outcomes
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.services.signal_outcome_tracker import (
    backfill_all_outcomes,
    compute_outcomes_for_date,
    run_eod_outcome_computation,
    write_outcomes,
)

router = APIRouter(prefix="/api/v2/local")

IST = timezone(timedelta(hours=5, minutes=30))
_OUTCOMES_DIR = Path(__file__).resolve().parents[4] / "logs" / "outcomes"

# ── Localhost guard ──────────────────────────────────────────────────────────

def require_local(request: Request) -> None:
    host = (request.client.host if request.client else "") or ""
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise HTTPException(status_code=403, detail="Local access only")


# ── Simple in-memory cache ───────────────────────────────────────────────────

_cache: dict[str, tuple[float, Any]] = {}
_CACHE_TTL = 3600.0  # 1 hour


def _cache_get(key: str) -> Any | None:
    entry = _cache.get(key)
    if entry and (time.time() - entry[0]) < _CACHE_TTL:
        return entry[1]
    return None


def _cache_set(key: str, value: Any) -> None:
    _cache[key] = (time.time(), value)


def invalidate_outcomes_cache() -> None:
    keys = [k for k in _cache if "outcomes" in k]
    for k in keys:
        _cache.pop(k, None)


# ── Data loader ──────────────────────────────────────────────────────────────

def _ist_today() -> datetime:
    return datetime.now(IST)


def _date_range(from_str: str, to_str: str) -> list[str]:
    try:
        start = datetime.strptime(from_str, "%Y-%m-%d")
        end = datetime.strptime(to_str, "%Y-%m-%d")
    except ValueError:
        return []
    dates = []
    cur = start
    while cur <= end:
        dates.append(cur.strftime("%Y%m%d"))
        cur += timedelta(days=1)
    return dates


def _load_outcomes(from_str: str, to_str: str, symbol: str, signal_type: str | None = None) -> list[dict]:
    cache_key = f"outcomes:{from_str}:{to_str}:{symbol}:{signal_type}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    records: list[dict] = []
    for date_str in _date_range(from_str, to_str):
        path = _OUTCOMES_DIR / f"signal_outcomes_{date_str}.jsonl"
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if str(rec.get("symbol", "")).upper() != symbol.upper():
                    continue
                if signal_type and str(rec.get("signal_type", "")).upper() != signal_type.upper():
                    continue
                records.append(rec)

    _cache_set(cache_key, records)
    return records


def _default_from() -> str:
    return (_ist_today() - timedelta(days=30)).strftime("%Y-%m-%d")


def _default_to() -> str:
    return _ist_today().strftime("%Y-%m-%d")


def _win_rate(wins: int, big_wins: int, losses: int) -> float:
    denom = wins + big_wins + losses
    return round((wins + big_wins) / denom, 4) if denom > 0 else 0.0


# ── /performance/summary ─────────────────────────────────────────────────────

@router.get("/performance/summary")
def performance_summary(
    request: Request,
    from_date: str = Query(default=None, alias="from"),
    to_date: str = Query(default=None, alias="to"),
    symbol: str = Query(default="NIFTY"),
    signal_type: Optional[str] = Query(default=None),
    _: None = Depends(require_local),
) -> dict:
    from_date = from_date or _default_from()
    to_date = to_date or _default_to()
    records = _load_outcomes(from_date, to_date, symbol, signal_type)

    wins = sum(1 for r in records if r.get("outcome") == "WIN")
    big_wins = sum(1 for r in records if r.get("outcome") == "BIG_WIN")
    losses = sum(1 for r in records if r.get("outcome") == "LOSS")
    expired = sum(1 for r in records if r.get("outcome") == "EXPIRED")

    resolved = [r for r in records if r.get("outcome") in ("WIN", "BIG_WIN", "LOSS")]
    rr_realized_vals = [float(r["rr_t1"]) for r in resolved if r.get("rr_t1")]
    rr_realized_vals_actual = [
        abs(float(r["pnl_pts"]) / abs(float(r["entry_underlying"]) - float(r["stop_underlying"])))
        for r in resolved
        if r.get("pnl_pts") is not None
        and r.get("entry_underlying") is not None
        and r.get("stop_underlying") is not None
        and abs(float(r["entry_underlying"]) - float(r["stop_underlying"])) > 0
    ]

    # Signals per day
    date_set: set[str] = set()
    for r in records:
        fired = r.get("fired_at", "")[:10]
        if fired:
            date_set.add(fired)
    days = len(date_set) or 1

    # By signal type
    by_type: dict[str, dict] = {}
    for r in records:
        st = str(r.get("signal_type", "UNKNOWN"))
        if st not in by_type:
            by_type[st] = {"signal_type": st, "n": 0, "wins": 0, "big_wins": 0, "losses": 0, "rr_vals": []}
        by_type[st]["n"] += 1
        if r.get("outcome") == "WIN":
            by_type[st]["wins"] += 1
        elif r.get("outcome") == "BIG_WIN":
            by_type[st]["big_wins"] += 1
        elif r.get("outcome") == "LOSS":
            by_type[st]["losses"] += 1
        if r.get("rr_t1"):
            by_type[st]["rr_vals"].append(float(r["rr_t1"]))

    by_type_out = []
    for v in sorted(by_type.values(), key=lambda x: -x["n"]):
        w = v["wins"] + v["big_wins"]
        wr = _win_rate(v["wins"], v["big_wins"], v["losses"])
        avg_rr = round(mean(v["rr_vals"]), 2) if v["rr_vals"] else None
        by_type_out.append({
            "signal_type": v["signal_type"],
            "n": v["n"],
            "wins": w,
            "win_rate": wr,
            "avg_rr": avg_rr,
        })

    total = len(records)
    wr_overall = _win_rate(wins, big_wins, losses)
    return {
        "from": from_date,
        "to": to_date,
        "symbol": symbol,
        "total_signals": total,
        "wins": wins,
        "losses": losses,
        "big_wins": big_wins,
        "expired": expired,
        "win_rate": wr_overall,
        "avg_rr_realized": round(mean(rr_realized_vals_actual), 2) if rr_realized_vals_actual else None,
        "avg_rr_predicted": round(mean(rr_realized_vals), 2) if rr_realized_vals else None,
        "signals_per_day": round(total / days, 1),
        "net_edge": round(wr_overall - 0.5, 4),
        "by_signal_type": by_type_out,
    }


# ── /performance/timeline ────────────────────────────────────────────────────

@router.get("/performance/timeline")
def performance_timeline(
    request: Request,
    from_date: str = Query(default=None, alias="from"),
    to_date: str = Query(default=None, alias="to"),
    symbol: str = Query(default="NIFTY"),
    signal_type: Optional[str] = Query(default=None),
    bucket: str = Query(default="day"),
    _: None = Depends(require_local),
) -> dict:
    from_date = from_date or _default_from()
    to_date = to_date or _default_to()
    records = _load_outcomes(from_date, to_date, symbol, signal_type)

    # Group by day
    by_day: dict[str, dict] = {}
    for r in records:
        day = str(r.get("fired_at", ""))[:10]
        if not day:
            continue
        if day not in by_day:
            by_day[day] = {"date": day, "n": 0, "wins": 0, "big_wins": 0, "losses": 0}
        by_day[day]["n"] += 1
        out = r.get("outcome")
        if out == "WIN":
            by_day[day]["wins"] += 1
        elif out == "BIG_WIN":
            by_day[day]["big_wins"] += 1
        elif out == "LOSS":
            by_day[day]["losses"] += 1

    series = []
    for day in sorted(by_day.keys()):
        v = by_day[day]
        wr = _win_rate(v["wins"], v["big_wins"], v["losses"])
        series.append({"date": day, "n": v["n"], "wins": v["wins"] + v["big_wins"], "win_rate": wr})

    # 7-day rolling average
    rolling: list[dict] = []
    for i in range(6, len(series)):
        window = series[i - 6 : i + 1]
        total_wins = sum(w["wins"] for w in window)
        total_n = sum(w["n"] for w in window)
        wr = round(total_wins / total_n, 4) if total_n > 0 else 0.0
        rolling.append({"date": series[i]["date"], "win_rate": wr})

    return {"bucket": bucket, "series": series, "rolling_7day_avg": rolling}


# ── /performance/conditional ─────────────────────────────────────────────────

def _conditional_bucket(records: list[dict], field: str, buckets: list[tuple[str, float, float]]) -> list[dict]:
    result = []
    for label, lo, hi in buckets:
        group = [
            r for r in records
            if r.get(field) is not None and lo <= float(r[field]) < hi
        ]
        wins = sum(1 for r in group if r.get("outcome") in ("WIN", "BIG_WIN"))
        losses = sum(1 for r in group if r.get("outcome") == "LOSS")
        wr = _win_rate(wins, 0, losses)
        result.append({"bucket": label, "n": len(group), "wins": wins, "win_rate": wr})
    return result


def _regime_bucket(records: list[dict]) -> list[dict]:
    regimes: dict[str, dict] = {}
    for r in records:
        reg = str(r.get("regime_at_fire") or "Unknown").strip() or "Unknown"
        if reg not in regimes:
            regimes[reg] = {"bucket": reg, "n": 0, "wins": 0, "losses": 0}
        regimes[reg]["n"] += 1
        out = r.get("outcome")
        if out in ("WIN", "BIG_WIN"):
            regimes[reg]["wins"] += 1
        elif out == "LOSS":
            regimes[reg]["losses"] += 1
    result = []
    for v in sorted(regimes.values(), key=lambda x: -x["n"]):
        wr = _win_rate(v["wins"], 0, v["losses"])
        result.append({"bucket": v["bucket"], "n": v["n"], "wins": v["wins"], "win_rate": wr})
    return result


@router.get("/performance/conditional")
def performance_conditional(
    request: Request,
    from_date: str = Query(default=None, alias="from"),
    to_date: str = Query(default=None, alias="to"),
    symbol: str = Query(default="NIFTY"),
    _: None = Depends(require_local),
) -> dict:
    from_date = from_date or _default_from()
    to_date = to_date or _default_to()
    records = _load_outcomes(from_date, to_date, symbol)

    return {
        "by_trap": _conditional_bucket(records, "trap_at_fire", [
            ("low (<35)", 0, 35),
            ("mid (35–55)", 35, 55),
            ("high (>55)", 55, 101),
        ]),
        "by_iv_rank": _conditional_bucket(records, "iv_rank_at_fire", [
            ("low (<30)", 0, 30),
            ("mid (30–70)", 30, 70),
            ("high (>70)", 70, 101),
        ]),
        "by_readiness": _conditional_bucket(records, "readiness_at_fire", [
            ("low (<60)", 0, 60),
            ("mid (60–75)", 60, 75),
            ("high (>75)", 75, 101),
        ]),
        "by_regime": _regime_bucket(records),
    }


# ── /signals/raw ─────────────────────────────────────────────────────────────

@router.get("/signals/raw")
def signals_raw(
    request: Request,
    from_date: str = Query(default=None, alias="from"),
    to_date: str = Query(default=None, alias="to"),
    symbol: str = Query(default="NIFTY"),
    signal_type: Optional[str] = Query(default=None),
    outcome: Optional[str] = Query(default=None),
    min_rr: Optional[float] = Query(default=None),
    limit: int = Query(default=100),
    offset: int = Query(default=0),
    _: None = Depends(require_local),
) -> dict:
    from_date = from_date or _default_from()
    to_date = to_date or _default_to()
    records = _load_outcomes(from_date, to_date, symbol, signal_type)

    if outcome:
        records = [r for r in records if str(r.get("outcome", "")).upper() == outcome.upper()]
    if min_rr is not None:
        records = [r for r in records if r.get("rr_t1") is not None and float(r["rr_t1"]) >= min_rr]

    records.sort(key=lambda r: r.get("fired_at", ""), reverse=True)
    total = len(records)
    page = records[offset: offset + limit]
    return {"total": total, "offset": offset, "limit": limit, "records": page}


# ── Debug endpoints ───────────────────────────────────────────────────────────

@router.post("/debug/recompute-outcomes/{date}")
def recompute_outcomes(
    date: str,
    request: Request,
    symbol: str = Query(default="NIFTY"),
    _: None = Depends(require_local),
) -> dict:
    # Expect YYYY-MM-DD; convert to YYYYMMDD
    date_str = date.replace("-", "")
    try:
        outcomes = compute_outcomes_for_date(date_str, symbol=symbol)
        path = write_outcomes(date_str, outcomes) if outcomes else None
        invalidate_outcomes_cache()
        return {"status": "ok", "date": date_str, "count": len(outcomes), "path": path}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/debug/backfill-outcomes")
def debug_backfill(
    request: Request,
    symbol: str = Query(default="NIFTY"),
    _: None = Depends(require_local),
) -> dict:
    try:
        result = backfill_all_outcomes(symbol=symbol)
        invalidate_outcomes_cache()
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
