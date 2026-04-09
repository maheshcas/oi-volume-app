from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.engines.historical_zone_engine import analyze_historical_sr_zones, normalize_daily_candles
from app.services.historical_zone_context import (
    build_historical_zone_context_from_payload,
    get_cached_historical_zone_context,
    set_cached_historical_zone_context,
)
from app.services.nse_client import fetch_index_history

logger = logging.getLogger("optionlens.historical_zone_scheduler")

IST = timezone(timedelta(hours=5, minutes=30))

ENABLE_HISTORICAL_ZONE_DAILY = os.getenv("OPTIONLENS_ENABLE_HISTORICAL_ZONE_DAILY", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
HISTORICAL_ZONE_DAILY_HOUR_IST = max(0, min(23, int(os.getenv("OPTIONLENS_HISTORICAL_ZONE_DAILY_HOUR_IST", "9"))))
HISTORICAL_ZONE_DAILY_MINUTE_IST = max(
    0, min(59, int(os.getenv("OPTIONLENS_HISTORICAL_ZONE_DAILY_MINUTE_IST", "0")))
)
HISTORICAL_ZONE_PREMARKET_CUTOFF_HOUR_IST = max(
    0, min(23, int(os.getenv("OPTIONLENS_HISTORICAL_ZONE_PREMARKET_CUTOFF_HOUR_IST", "9")))
)
HISTORICAL_ZONE_PREMARKET_CUTOFF_MINUTE_IST = max(
    0, min(59, int(os.getenv("OPTIONLENS_HISTORICAL_ZONE_PREMARKET_CUTOFF_MINUTE_IST", "15")))
)
HISTORICAL_ZONE_LOOKBACK_DAYS = max(60, int(os.getenv("OPTIONLENS_HISTORICAL_ZONE_LOOKBACK_DAYS", "90")))
HISTORICAL_ZONE_RECENT_WINDOW = max(5, int(os.getenv("OPTIONLENS_HISTORICAL_ZONE_RECENT_WINDOW", "12")))
HISTORICAL_ZONE_KEEP_PER_SYMBOL = max(1, int(os.getenv("OPTIONLENS_HISTORICAL_ZONE_KEEP_PER_SYMBOL", "30")))
HISTORICAL_ZONE_PIVOT_LOOKBACK = max(2, int(os.getenv("OPTIONLENS_HISTORICAL_ZONE_PIVOT_LOOKBACK", "10")))
HISTORICAL_ZONE_WIDTH_MULTIPLIER = max(0.1, float(os.getenv("OPTIONLENS_HISTORICAL_ZONE_WIDTH_MULTIPLIER", "2")))
HISTORICAL_ZONE_MIN_TESTS = max(1, int(os.getenv("OPTIONLENS_HISTORICAL_ZONE_MIN_TESTS", "2")))
HISTORICAL_ZONE_MAX_ZONES = max(1, int(os.getenv("OPTIONLENS_HISTORICAL_ZONE_MAX_ZONES", "10")))
HISTORICAL_ZONE_MAX_HEIGHT_MULTIPLIER = max(
    1.0, float(os.getenv("OPTIONLENS_HISTORICAL_ZONE_MAX_HEIGHT_MULTIPLIER", "5"))
)
HISTORICAL_ZONE_MIN_SCORE_GAP = max(1.0, float(os.getenv("OPTIONLENS_HISTORICAL_ZONE_MIN_SCORE_GAP", "1.5")))
HISTORICAL_ZONE_OUTPUT_DIR = Path(
    os.getenv(
        "OPTIONLENS_HISTORICAL_ZONE_OUTPUT_DIR",
        str(Path(__file__).resolve().parents[2] / "logs" / "historical_zones"),
    )
)

_last_run_date_by_symbol: dict[str, str] = {}
_last_run_result_by_symbol: dict[str, dict[str, Any]] = {}

_NSE_SYMBOL_TO_INDEX_NAME: dict[str, str] = {
    "NIFTY": "NIFTY 50",
    "BANKNIFTY": "NIFTY BANK",
    "FINNIFTY": "NIFTY FINANCIAL SERVICES",
}


def _iso(dt: datetime | None) -> str | None:
    return dt.astimezone(timezone.utc).isoformat() if dt else None


def _next_due_ist(now_utc: datetime) -> datetime:
    current_ist = now_utc.astimezone(IST)
    due_today = current_ist.replace(
        hour=HISTORICAL_ZONE_DAILY_HOUR_IST,
        minute=HISTORICAL_ZONE_DAILY_MINUTE_IST,
        second=0,
        microsecond=0,
    )
    if current_ist <= due_today and current_ist.weekday() < 5:
        return due_today

    next_day = current_ist + timedelta(days=1)
    while next_day.weekday() >= 5:
        next_day += timedelta(days=1)
    return next_day.replace(
        hour=HISTORICAL_ZONE_DAILY_HOUR_IST,
        minute=HISTORICAL_ZONE_DAILY_MINUTE_IST,
        second=0,
        microsecond=0,
    )


def _safe_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _cleanup_old_symbol_snapshots(symbol: str, max_keep: int = HISTORICAL_ZONE_KEEP_PER_SYMBOL) -> None:
    try:
        prefix = f"{symbol.upper()}_historical_zones_"
        files = sorted(
            [path for path in HISTORICAL_ZONE_OUTPUT_DIR.glob(f"{prefix}*.json") if path.is_file()],
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for old in files[max_keep:]:
            old.unlink(missing_ok=True)
    except Exception as exc:
        logger.warning("Historical zone retention cleanup failed for %s: %s", symbol, exc)


def _load_snapshot_payload(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def _cache_context_from_payload(symbol: str, payload: dict[str, Any] | None) -> None:
    if not isinstance(payload, dict):
        return
    context = build_historical_zone_context_from_payload(payload)
    if isinstance(context, dict):
        set_cached_historical_zone_context(symbol, context)


def _latest_symbol_snapshot(symbol: str) -> Path | None:
    prefix = f"{symbol.upper()}_historical_zones_"
    files = sorted(
        [path for path in HISTORICAL_ZONE_OUTPUT_DIR.glob(f"{prefix}*.json") if path.is_file()],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return files[0] if files else None


def _is_pre_market_compute_window(now_utc: datetime) -> tuple[bool, str]:
    current_ist = now_utc.astimezone(IST)
    if current_ist.weekday() >= 5:
        return False, "weekend"

    due_minutes = (HISTORICAL_ZONE_DAILY_HOUR_IST * 60) + HISTORICAL_ZONE_DAILY_MINUTE_IST
    cutoff_minutes = (HISTORICAL_ZONE_PREMARKET_CUTOFF_HOUR_IST * 60) + HISTORICAL_ZONE_PREMARKET_CUTOFF_MINUTE_IST
    current_minutes = (current_ist.hour * 60) + current_ist.minute
    if current_minutes < due_minutes:
        return False, "before_schedule"
    if current_minutes >= cutoff_minutes:
        return False, "market_hours_no_recompute"

    return True, "pre_market_due"


def run_historical_zone_daily_if_due(symbol: str, now_utc: datetime | None = None) -> dict[str, Any]:
    symbol_key = str(symbol or "").strip().upper()
    now = now_utc or datetime.now(timezone.utc)

    def _mark(result: dict[str, Any]) -> dict[str, Any]:
        enriched = dict(result)
        enriched.setdefault("symbol", symbol_key)
        enriched.setdefault("checked_at_utc", _iso(now))
        _last_run_result_by_symbol[symbol_key] = dict(enriched)
        return enriched

    if not symbol_key:
        return _mark({"status": "skipped", "reason": "empty_symbol"})

    if not ENABLE_HISTORICAL_ZONE_DAILY:
        return _mark({"status": "disabled"})

    index_name = _NSE_SYMBOL_TO_INDEX_NAME.get(symbol_key)
    if not index_name:
        return _mark({"status": "skipped", "reason": "unsupported_symbol"})

    session_date = now.astimezone(IST).date().isoformat()
    cached = get_cached_historical_zone_context(symbol_key)
    if isinstance(cached, dict):
        return _mark({"status": "cached", "reason": "memory_cache"})

    if _last_run_date_by_symbol.get(symbol_key) == session_date:
        return _mark({"status": "skipped", "reason": "already_ran_today"})

    file_name = f"{symbol_key}_historical_zones_{session_date}.json"
    output_path = HISTORICAL_ZONE_OUTPUT_DIR / file_name
    if output_path.exists():
        payload = _load_snapshot_payload(output_path)
        _cache_context_from_payload(symbol_key, payload)
        _last_run_date_by_symbol[symbol_key] = session_date
        return _mark({
            "status": "cached",
            "reason": "today_snapshot_loaded",
            "path": str(output_path),
        })

    latest_path = _latest_symbol_snapshot(symbol_key)
    if latest_path and latest_path.exists():
        payload = _load_snapshot_payload(latest_path)
        _cache_context_from_payload(symbol_key, payload)

    due, due_reason = _is_pre_market_compute_window(now)
    if not due:
        return _mark({"status": "skipped", "reason": due_reason, "path": str(latest_path) if latest_path else None})

    current_ist = now.astimezone(IST)
    from_dt = current_ist - timedelta(days=HISTORICAL_ZONE_LOOKBACK_DAYS)
    from_date = from_dt.strftime("%d-%m-%Y")
    to_date = current_ist.strftime("%d-%m-%Y")

    raw = fetch_index_history(index_type=index_name, from_date=from_date, to_date=to_date)
    rows = raw.get("data", []) if isinstance(raw, dict) else []
    candles = normalize_daily_candles(rows if isinstance(rows, list) else [])
    if not candles:
        return _mark({"status": "skipped", "reason": "no_candles"})

    analysis = analyze_historical_sr_zones(
        candles,
        recent_window=HISTORICAL_ZONE_RECENT_WINDOW,
        pivot_lookback=HISTORICAL_ZONE_PIVOT_LOOKBACK,
        zone_width_multiplier=HISTORICAL_ZONE_WIDTH_MULTIPLIER,
        min_tests=HISTORICAL_ZONE_MIN_TESTS,
        max_zones=HISTORICAL_ZONE_MAX_ZONES,
        max_height_multiplier=HISTORICAL_ZONE_MAX_HEIGHT_MULTIPLIER,
        min_score_gap=HISTORICAL_ZONE_MIN_SCORE_GAP,
    )
    payload = {
        "meta": {
            "symbol": symbol_key,
            "index_name": index_name,
            "source": "nse_daily_history",
            "source_window": {"from": from_date, "to": to_date},
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "candles_count": len(candles),
            "lookback_days": HISTORICAL_ZONE_LOOKBACK_DAYS,
            "recent_window": HISTORICAL_ZONE_RECENT_WINDOW,
            "calculation": {
                "pivot_lookback": HISTORICAL_ZONE_PIVOT_LOOKBACK,
                "zone_width_multiplier": HISTORICAL_ZONE_WIDTH_MULTIPLIER,
                "min_tests": HISTORICAL_ZONE_MIN_TESTS,
                "max_zones": HISTORICAL_ZONE_MAX_ZONES,
                "max_height_multiplier": HISTORICAL_ZONE_MAX_HEIGHT_MULTIPLIER,
                "min_score_gap": HISTORICAL_ZONE_MIN_SCORE_GAP,
            },
        },
        "analysis": analysis,
    }

    HISTORICAL_ZONE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    _cleanup_old_symbol_snapshots(symbol_key)
    _last_run_date_by_symbol[symbol_key] = session_date

    return _mark({
        "status": "written",
        "path": str(output_path),
        "candles_count": len(candles),
        "retracement_full_count": _safe_int(len(analysis.get("retracement_full_window", []))),
        "retracement_recent_count": _safe_int(len(analysis.get("retracement_recent_window", []))),
    })


def get_historical_zone_scheduler_status(
    symbols: list[str] | None = None,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    now = now_utc or datetime.now(timezone.utc)
    target_symbols = [str(s).strip().upper() for s in (symbols or sorted(_NSE_SYMBOL_TO_INDEX_NAME.keys())) if str(s).strip()]
    symbol_status: dict[str, Any] = {}

    for symbol in target_symbols:
        last_result = _last_run_result_by_symbol.get(symbol, {})
        symbol_status[symbol] = {
            "supported": symbol in _NSE_SYMBOL_TO_INDEX_NAME,
            "last_run_date_ist": _last_run_date_by_symbol.get(symbol),
            "last_result": last_result or None,
        }

    next_due_ist = _next_due_ist(now)
    return {
        "enabled": ENABLE_HISTORICAL_ZONE_DAILY,
        "schedule_ist": f"{HISTORICAL_ZONE_DAILY_HOUR_IST:02d}:{HISTORICAL_ZONE_DAILY_MINUTE_IST:02d}",
        "pre_market_cutoff_ist": f"{HISTORICAL_ZONE_PREMARKET_CUTOFF_HOUR_IST:02d}:{HISTORICAL_ZONE_PREMARKET_CUTOFF_MINUTE_IST:02d}",
        "lookback_days": HISTORICAL_ZONE_LOOKBACK_DAYS,
        "recent_window": HISTORICAL_ZONE_RECENT_WINDOW,
        "keep_per_symbol": HISTORICAL_ZONE_KEEP_PER_SYMBOL,
        "calculation": {
            "pivot_lookback": HISTORICAL_ZONE_PIVOT_LOOKBACK,
            "zone_width_multiplier": HISTORICAL_ZONE_WIDTH_MULTIPLIER,
            "min_tests": HISTORICAL_ZONE_MIN_TESTS,
            "max_zones": HISTORICAL_ZONE_MAX_ZONES,
            "max_height_multiplier": HISTORICAL_ZONE_MAX_HEIGHT_MULTIPLIER,
            "min_score_gap": HISTORICAL_ZONE_MIN_SCORE_GAP,
        },
        "output_dir": str(HISTORICAL_ZONE_OUTPUT_DIR),
        "checked_at_utc": _iso(now),
        "next_due_at_ist": next_due_ist.isoformat(),
        "symbols": symbol_status,
    }
