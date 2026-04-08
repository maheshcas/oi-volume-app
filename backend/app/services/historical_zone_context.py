from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any


HISTORICAL_ZONE_DIR = Path(__file__).resolve().parents[2] / "logs" / "historical_zones"

_SYMBOL_ALIASES: dict[str, tuple[str, ...]] = {
    "NIFTY": ("nifty", "nifty 50"),
    "BANKNIFTY": ("banknifty", "nifty bank"),
    "FINNIFTY": ("finnifty", "nifty fin service", "fin service"),
    "SENSEX": ("sensex", "bse sensex"),
}
_MEMORY_CONTEXT_CACHE: dict[str, dict[str, Any]] = {}


def _symbol_matches_source(symbol: str, source_text: str | None) -> bool:
    text = str(source_text or "").strip().lower()
    if not text:
        return False
    aliases = _SYMBOL_ALIASES.get(symbol.upper(), ())
    if not aliases:
        return True
    return any(alias in text for alias in aliases)


def _safe_zone_entry(zone: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(zone, dict):
        return None
    return {
        "zone_low": zone.get("zone_low"),
        "zone_high": zone.get("zone_high"),
        "center": zone.get("center"),
        "role": zone.get("role"),
        "score": zone.get("score"),
        "touches": zone.get("touches"),
        "first_date": zone.get("first_date"),
        "last_date": zone.get("last_date"),
    }


def _build_context_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    meta = payload.get("meta", {}) if isinstance(payload.get("meta"), dict) else {}
    analysis = payload.get("analysis", {}) if isinstance(payload.get("analysis"), dict) else {}
    full_window = analysis.get("retracement_full_window", [])
    recent_window = analysis.get("retracement_recent_window", [])
    top_full = full_window[0] if isinstance(full_window, list) and full_window else None
    top_recent = recent_window[0] if isinstance(recent_window, list) and recent_window else None

    return {
        "available": bool(top_full or top_recent),
        "generated_at_utc": meta.get("generated_at_utc"),
        "source_file": meta.get("source_file"),
        "candles_count": meta.get("candles_count"),
        "dominant_full_window": _safe_zone_entry(top_full),
        "dominant_recent_window": _safe_zone_entry(top_recent),
    }


def set_cached_historical_zone_context(symbol: str, context: dict[str, Any] | None) -> None:
    symbol_upper = str(symbol or "").strip().upper()
    if not symbol_upper:
        return
    if not isinstance(context, dict):
        _MEMORY_CONTEXT_CACHE.pop(symbol_upper, None)
        return
    _MEMORY_CONTEXT_CACHE[symbol_upper] = deepcopy(context)


def get_cached_historical_zone_context(symbol: str) -> dict[str, Any] | None:
    symbol_upper = str(symbol or "").strip().upper()
    if not symbol_upper:
        return None
    cached = _MEMORY_CONTEXT_CACHE.get(symbol_upper)
    return deepcopy(cached) if isinstance(cached, dict) else None


def build_historical_zone_context_from_payload(payload: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    return _build_context_from_payload(payload)


def load_latest_historical_zone_context(symbol: str) -> dict[str, Any] | None:
    symbol_upper = str(symbol or "").strip().upper()
    if not symbol_upper:
        return None

    cached = get_cached_historical_zone_context(symbol_upper)
    if isinstance(cached, dict):
        return cached

    if not HISTORICAL_ZONE_DIR.exists():
        return None

    files = sorted(HISTORICAL_ZONE_DIR.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    for path in files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue

        if not isinstance(payload, dict):
            continue
        meta = payload.get("meta", {}) if isinstance(payload.get("meta"), dict) else {}

        meta_symbol = str(meta.get("symbol") or "").strip().upper()
        if meta_symbol:
            if meta_symbol != symbol_upper:
                continue
            context = _build_context_from_payload(payload)
            set_cached_historical_zone_context(symbol_upper, context)
            return context

        # Legacy fallback: only for older files that may not include meta.symbol.
        source_file = meta.get("source_file")
        if not _symbol_matches_source(symbol_upper, source_file):
            continue
        context = _build_context_from_payload(payload)
        set_cached_historical_zone_context(symbol_upper, context)
        return context
    return None
