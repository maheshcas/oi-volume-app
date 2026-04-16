from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.infrastructure.feeds.nse_client import fetch_index_history

logger = logging.getLogger("optionlens.daily_context")

IST = timezone(timedelta(hours=5, minutes=30))
LOOKBACK_DAYS = max(60, int(os.getenv("OPTIONLENS_DAILY_CONTEXT_LOOKBACK_DAYS", "90")))
# parents[3]: persistence/ -> infrastructure/ -> app/ -> backend root
DAILY_CONTEXT_DIR = Path(__file__).resolve().parents[3] / "data" / "daily_context"

SYMBOL_TO_INDEX_NAMES: dict[str, tuple[str, ...]] = {
    "NIFTY": ("NIFTY 50",),
    "BANKNIFTY": ("NIFTY BANK",),
    "FINNIFTY": ("NIFTY FINANCIAL SERVICES",),
    # NSE historical endpoint naming may vary for Sensex. Try known aliases.
    "SENSEX": ("BSE SENSEX", "S&P BSE SENSEX", "SENSEX"),
}

_LOCK = threading.Lock()
_MEMORY_CACHE: dict[str, dict[str, Any]] = {}


def _to_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _file_path(symbol: str) -> Path:
    safe_symbol = "".join(ch for ch in symbol.upper() if ch.isalnum() or ch in {"_", "-"})
    return DAILY_CONTEXT_DIR / f"{safe_symbol}_daily_context.json"


def _current_ist_date(now_utc: datetime | None = None) -> datetime.date:
    current_utc = now_utc or datetime.now(timezone.utc)
    return current_utc.astimezone(IST).date()


def _rolling_window(now_utc: datetime | None = None) -> tuple[str, str]:
    current_utc = now_utc or datetime.now(timezone.utc)
    current_ist = current_utc.astimezone(IST)
    from_dt = current_ist - timedelta(days=LOOKBACK_DAYS)
    return from_dt.strftime("%d-%m-%Y"), current_ist.strftime("%d-%m-%Y")


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    raw_date = str(row.get("EOD_TIMESTAMP") or "").strip()
    parsed_date = datetime.strptime(raw_date, "%d-%b-%Y").date()
    return {
        "date": parsed_date.isoformat(),
        "open": _to_float(row.get("EOD_OPEN_INDEX_VAL")),
        "high": _to_float(row.get("EOD_HIGH_INDEX_VAL")),
        "low": _to_float(row.get("EOD_LOW_INDEX_VAL")),
        "close": _to_float(row.get("EOD_CLOSE_INDEX_VAL")),
        "turnover_cr": _to_float(row.get("HIT_TURN_OVER")),
        "volume": _to_int(row.get("HIT_TRADED_QTY")),
    }


def _select_previous_day(rows: list[dict[str, Any]], now_utc: datetime | None = None) -> dict[str, Any] | None:
    if not rows:
        return None
    today_ist = _current_ist_date(now_utc)
    previous_rows = [row for row in rows if datetime.strptime(str(row["date"]), "%Y-%m-%d").date() < today_ist]
    return previous_rows[-1] if previous_rows else rows[-1]


def _compute_trend_bias(rows: list[dict[str, Any]], previous_day: dict[str, Any] | None) -> str:
    if not rows or not previous_day:
        return "Neutral"
    first_close = _to_float(rows[0].get("close"))
    last_close = _to_float(previous_day.get("close"))
    if first_close is None or last_close is None or first_close <= 0:
        return "Neutral"
    change_pct = ((last_close - first_close) / first_close) * 100.0
    if change_pct >= 1.0:
        return "Bullish"
    if change_pct <= -1.0:
        return "Bearish"
    return "Neutral"


def _build_payload(symbol: str, index_name: str, rows: list[dict[str, Any]], now_utc: datetime | None = None) -> dict[str, Any]:
    previous_day = _select_previous_day(rows, now_utc=now_utc)
    highs = [float(v) for v in (row.get("high") for row in rows) if isinstance(v, (int, float))]
    lows = [float(v) for v in (row.get("low") for row in rows) if isinstance(v, (int, float))]
    closes = [float(v) for v in (row.get("close") for row in rows) if isinstance(v, (int, float))]
    volumes = [int(v) for v in (row.get("volume") for row in rows) if isinstance(v, int)]
    turnover_values = [float(v) for v in (row.get("turnover_cr") for row in rows) if isinstance(v, (int, float))]
    first_close = closes[0] if closes else None
    last_close = float(previous_day.get("close")) if previous_day and isinstance(previous_day.get("close"), (int, float)) else None
    close_change_pct = None
    if first_close and last_close and first_close > 0:
        close_change_pct = round(((last_close - first_close) / first_close) * 100.0, 2)

    return {
        "symbol": symbol.upper(),
        "index_name": index_name,
        "refresh_date": _current_ist_date(now_utc).isoformat(),
        "lookback_days": LOOKBACK_DAYS,
        "records_count": len(rows),
        "window": {
            "from_date": rows[0]["date"] if rows else None,
            "to_date": rows[-1]["date"] if rows else None,
        },
        "previous_day": previous_day,
        "levels": {
            "previous_day_open": previous_day.get("open") if previous_day else None,
            "previous_day_high": previous_day.get("high") if previous_day else None,
            "previous_day_low": previous_day.get("low") if previous_day else None,
            "previous_day_close": previous_day.get("close") if previous_day else None,
        },
        "rolling_3m": {
            "high": round(max(highs), 2) if highs else None,
            "low": round(min(lows), 2) if lows else None,
            "close_change_pct": close_change_pct,
            "average_volume": int(sum(volumes) / len(volumes)) if volumes else None,
            "average_turnover_cr": round(sum(turnover_values) / len(turnover_values), 2) if turnover_values else None,
            "trend_bias": _compute_trend_bias(rows, previous_day),
        },
        "source": "live",
    }


def _load_from_disk(symbol: str) -> dict[str, Any] | None:
    path = _file_path(symbol)
    try:
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else None
    except Exception as exc:
        logger.debug("Daily context load failed for %s: %s", symbol, exc)
        return None


def _load_existing_rows(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    rows = payload.get("rows")
    if not isinstance(rows, list):
        return []
    normalized_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        date_text = str(row.get("date") or "").strip()
        if not date_text:
            continue
        normalized_rows.append(
            {
                "date": date_text,
                "open": _to_float(row.get("open")),
                "high": _to_float(row.get("high")),
                "low": _to_float(row.get("low")),
                "close": _to_float(row.get("close")),
                "turnover_cr": _to_float(row.get("turnover_cr")),
                "volume": _to_int(row.get("volume")),
            }
        )
    return sorted(normalized_rows, key=lambda row: row["date"])


def _latest_saved_date(rows: list[dict[str, Any]]) -> datetime.date | None:
    if not rows:
        return None
    try:
        return max(datetime.strptime(str(row["date"]), "%Y-%m-%d").date() for row in rows if row.get("date"))
    except Exception:
        return None


def _merge_deduplicate_rows(existing_rows: list[dict[str, Any]], new_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for row in existing_rows + new_rows:
        if not isinstance(row, dict):
            continue
        date_text = str(row.get("date") or "").strip()
        if not date_text:
            continue
        merged[date_text] = {
            "date": date_text,
            "open": _to_float(row.get("open")),
            "high": _to_float(row.get("high")),
            "low": _to_float(row.get("low")),
            "close": _to_float(row.get("close")),
            "turnover_cr": _to_float(row.get("turnover_cr")),
            "volume": _to_int(row.get("volume")),
        }
    return sorted(merged.values(), key=lambda row: row["date"])


def _persist_to_disk(symbol: str, payload: dict[str, Any]) -> None:
    path = _file_path(symbol)
    try:
        DAILY_CONTEXT_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")
    except Exception as exc:
        logger.debug("Daily context persist failed for %s: %s", symbol, exc)


def get_daily_context(symbol: str, now_utc: datetime | None = None) -> dict[str, Any]:
    """
    Fetch daily index history at most once per IST day and expose compact previous-day context.
    This is intentionally read-only context for OptionLens and must not drive intraday SPC logic.
    """
    symbol_key = str(symbol or "").strip().upper()
    index_names = SYMBOL_TO_INDEX_NAMES.get(symbol_key)
    if not index_names:
        return {}

    refresh_date = _current_ist_date(now_utc).isoformat()
    disk_payload: dict[str, Any] | None = None

    with _LOCK:
        memory_payload = _MEMORY_CACHE.get(symbol_key)
        if isinstance(memory_payload, dict) and memory_payload.get("refresh_date") == refresh_date:
            return dict(memory_payload)

        disk_payload = _load_from_disk(symbol_key)
        if isinstance(disk_payload, dict) and disk_payload.get("refresh_date") == refresh_date:
            cached_context = disk_payload.get("context") if isinstance(disk_payload.get("context"), dict) else disk_payload
            _MEMORY_CACHE[symbol_key] = cached_context
            return dict(cached_context)

    existing_rows = _load_existing_rows(disk_payload)
    latest_date = _latest_saved_date(existing_rows)
    current_ist = _current_ist_date(now_utc)
    if latest_date is None:
        from_date, to_date = _rolling_window(now_utc)
    else:
        from_dt = latest_date + timedelta(days=1)
        if from_dt > current_ist:
            cached_context = (
                disk_payload.get("context")
                if isinstance(disk_payload, dict) and isinstance(disk_payload.get("context"), dict)
                else disk_payload
            )
            if isinstance(cached_context, dict):
                cached_context = dict(cached_context)
                cached_context["refresh_date"] = refresh_date
                cached_context["source"] = "cache"
                with _LOCK:
                    _MEMORY_CACHE[symbol_key] = cached_context
                _persist_to_disk(symbol_key, {"context": cached_context, "rows": existing_rows})
                return cached_context
            return {}
        from_date = from_dt.strftime("%d-%m-%Y")
        to_date = current_ist.strftime("%d-%m-%Y")

    try:
        selected_index_name: str | None = None
        new_rows: list[dict[str, Any]] = []
        for index_name in index_names:
            raw = fetch_index_history(index_type=index_name, from_date=from_date, to_date=to_date)
            raw_rows = raw.get("data", []) if isinstance(raw, dict) else []
            candidate_rows = [
                _normalize_row(row)
                for row in raw_rows
                if isinstance(row, dict) and row.get("EOD_TIMESTAMP")
            ]
            if candidate_rows:
                selected_index_name = index_name
                new_rows = candidate_rows
                break
            if selected_index_name is None:
                selected_index_name = index_name
        rows = _merge_deduplicate_rows(existing_rows, new_rows)
        payload = _build_payload(
            symbol=symbol_key,
            index_name=selected_index_name or index_names[0],
            rows=rows,
            now_utc=now_utc,
        )
        with _LOCK:
            _MEMORY_CACHE[symbol_key] = payload
        _persist_to_disk(symbol_key, {"context": payload, "rows": rows})
        return dict(payload)
    except Exception as exc:
        logger.debug("Daily context fetch failed for %s: %s", symbol_key, exc)
        fallback = disk_payload if isinstance(disk_payload, dict) else _load_from_disk(symbol_key)
        fallback_context = fallback.get("context") if isinstance(fallback, dict) and isinstance(fallback.get("context"), dict) else fallback
        if isinstance(fallback_context, dict):
            fallback_payload = dict(fallback_context)
            fallback_payload["source"] = "cache"
            with _LOCK:
                _MEMORY_CACHE[symbol_key] = fallback_payload
            return fallback_payload
        return {}
