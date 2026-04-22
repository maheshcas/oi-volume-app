from __future__ import annotations

import asyncio
import json
import logging
import logging.handlers
import os
import re
import time
from copy import deepcopy
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.core.cache import cache, make_cache_key
from app.engines.breakout_engine import run_breakout_engine
from app.engines.breakout_probability_engine import compute_breakout_probability
from app.engines.auto_exit_suggestion_engine import generate_auto_exit_suggestion
from app.engines.adaptive_calibration import load_adaptive_weights, update_end_of_day_calibration
from app.engines.adaptive_weighting_engine import compute_adaptive_weights
from app.engines.bias_stability_engine import compute_bias_stability
from app.engines.decision_engine import run_decision_engine_v3
from app.engines.conflict_resolution_engine import run_conflict_resolver
from app.engines.expiry_mode_engine import run_expiry_adaptive_mode
from app.engines.exhaustion_trap_combo_engine import detect_exhaustion_trap_combo
from app.engines.early_reversal_probability_engine import compute_early_reversal_probability
from app.engines.oi_analyzer import run_oi_analysis
from app.engines.momentum_exhaustion_engine import detect_momentum_exhaustion
from app.engines.intraday_playbook_engine import generate_intraday_playbook
from app.engines.liquidity_map_engine import build_liquidity_map
from app.engines.insight_engine import generate_market_insight
from app.engines.preprocessing import build_feature_frame, normalize_chain
from app.engines.regime_engine import run_regime_engine
from app.engines.session_phase_engine import compute_session_phase
from app.engines.regime_shift_engine import detect_regime_shift
from app.engines.signal_priority_engine import prioritize_signals
from app.engines.sr_engine import run_sr_engine
from app.engines.target_engine import run_target_engine
from app.engines.trade_plan_engine import generate_trade_plan
from app.engines.material_breach_engine import detect_material_breach
from app.engines.wall_break_engine import detect_wall_break
from app.engines.trap_engine import adjust_trap_by_confidence, run_trap_engine
from app.engines.volume_analyzer import run_volume_analysis
from app.engines.greeks_engine import compute_chain_greeks
from app.engines.iv_rank_engine import compute_iv_rank
from app.engines.strike_selector_engine import generate_strike_guidance
from app.engines.strike_intelligence_engine import compute_strike_intelligence
from app.engines.entry_target_engine import compute_entry_target
from app.engines.historical_zone_engine import get_intraday_zones
from app.services.decision_engine import build_decision_input, master_decision_engine
from app.infrastructure.persistence.daily_context import get_daily_context
from app.services.intraday_performance_tracker import tracker
from app.infrastructure.feeds.bse_fetcher import get_sensex_option_chain
from app.infrastructure.feeds.bse_adapter import (
    fetch_sensex_option_chain_async,
    fetch_sensex_contract_info_async,
)
from app.infrastructure.feeds.nse_client import fetch_index_data, fetch_option_chain, fetch_option_chain_contract_info
from app.services.parser import build_oi_volume_summary, build_target_projection

logger = logging.getLogger("optionlens.background_updater")

REFRESH_SECONDS = int(os.getenv("OPTIONLENS_REFRESH_SECONDS", "15"))
STALE_AFTER_SECONDS = int(os.getenv("OPTIONLENS_STALE_AFTER_SECONDS", "60"))
SYMBOLS = [s.strip().upper() for s in os.getenv("OPTIONLENS_SYMBOLS", "NIFTY,BANKNIFTY,FINNIFTY").split(",") if s.strip()]
BSE_SYMBOLS: frozenset[str] = frozenset({"SENSEX"})
INSTRUMENT_TYPE = os.getenv("OPTIONLENS_INSTRUMENT_TYPE", "Indices")
MAX_EXPIRIES_PER_SYMBOL = max(1, int(os.getenv("OPTIONLENS_PREFETCH_EXPIRIES", "3")))
ATR_ROLLING_WINDOW = max(5, int(os.getenv("OPTIONLENS_ATR_ROLLING_WINDOW", "40")))
ATR_MIN_SAMPLES = max(3, int(os.getenv("OPTIONLENS_ATR_MIN_SAMPLES", "5")))
ATR_MIN_SAMPLES = min(ATR_MIN_SAMPLES, ATR_ROLLING_WINDOW)
ADAPTIVE_RECALC_MINUTES = max(30, int(os.getenv("OPTIONLENS_ADAPTIVE_RECALC_MINUTES", "30")))
_DEFAULT_CYCLE_LOG_PATH = Path(__file__).resolve().parents[3] / "logs" / "optionlens_cycle_log.jsonl"
CYCLE_LOG_PATH = Path(os.getenv("OPTIONLENS_CYCLE_LOG_PATH", str(_DEFAULT_CYCLE_LOG_PATH)))
ENABLE_CYCLE_LOG = os.getenv("OPTIONLENS_ENABLE_CYCLE_LOG", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
_DEFAULT_EVENT_LOG_PATH = Path(__file__).resolve().parents[3] / "logs" / "optionlens_market_events.txt"
EVENT_LOG_PATH = Path(os.getenv("OPTIONLENS_EVENT_LOG_PATH", str(_DEFAULT_EVENT_LOG_PATH)))
_DEFAULT_EVENT_STREAM_PATH = Path(__file__).resolve().parents[3] / "logs" / "optionlens_market_events.jsonl"
EVENT_STREAM_PATH = Path(os.getenv("OPTIONLENS_EVENT_STREAM_PATH", str(_DEFAULT_EVENT_STREAM_PATH)))
ENABLE_EVENT_LOG = os.getenv("OPTIONLENS_ENABLE_EVENT_LOG", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
ENABLE_HZC = os.getenv("OPTIONLENS_ENABLE_HZC", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
STATE_SNAPSHOT_DIR = Path(__file__).resolve().parents[3] / "logs" / "state_snapshots"
LOG_ROTATION_MAX_BYTES = max(1024, int(os.getenv("OPTIONLENS_LOG_ROTATION_MAX_BYTES", str(10 * 1024 * 1024))))
LOG_ROTATION_BACKUP_COUNT = max(0, int(os.getenv("OPTIONLENS_LOG_ROTATION_BACKUP_COUNT", "2")))
MAX_STATE_SNAPSHOTS_PER_SERIES = max(1, int(os.getenv("OPTIONLENS_MAX_STATE_SNAPSHOTS_PER_SERIES", "10")))
IST = timezone(timedelta(hours=5, minutes=30))

# ── Scheduled cache-clear windows (IST) ─────────────────────────────
# Each entry: (hour, minute) in IST at which the cache is auto-flushed.
# Market open flush clears stale overnight data.
# Mid-session flush prevents long-running drift.
# Close flush triggers EOD calibration and marks session end.
_SCHEDULED_FLUSH_WINDOWS_IST: list[tuple[int, int]] = [
    (9, 15),
    (12, 0),
    (15, 30),
]

# Track which windows have already fired today to prevent repeat flushes.
_flushed_windows: set[tuple[int, int]] = set()
_flushed_windows_date: datetime | None = None
_last_seeded_flush_ist: datetime | None = None
_cycle_count_since_flush: int = 0
_alignment_bootstrap_logged: set[str] = set()

REGIME_MIN_HOLD_CYCLES = 3
REGIME_SWITCH_CONFIRM_CYCLES = 2
RANGE_REGIME_CANONICAL_LABEL = "Range Play"
NON_COMMITTABLE_REGIMES: frozenset[str] = frozenset(
    {"Balanced / Wait", "Balanced Structure", "Standby", "Transition Phase"}
)
RANGE_LOCK_TRAP_MIN = 55
RANGE_LOCK_READINESS_MAX = 45
NO_EDGE_TRAP_MIN = 55
NO_EDGE_READINESS_CENTER = 50
NO_EDGE_READINESS_BAND = 10
TRAP_HYSTERESIS_DEADBAND = 3.0
TRAP_SMOOTH_PREV_WEIGHT = 0.7
TRAP_SMOOTH_NEW_WEIGHT = 0.3
TRAP_STABLE_MID_MIN = 55.0
TRAP_STABLE_MID_MAX = 65.0
REVERSAL_DECAY = 0.65
REVERSAL_DECAY_CYCLES = 2
PINNING_SCENARIO_MULTIPLIER = 0.50
PINNING_TRAP_MODIFIER_POINTS = 5.0
READINESS_TRANSITION_FLAP_MAX_DROP = 8.0
READINESS_TRANSITION_FLAP_FLOOR = 36.0
RESPONSE_WARNING_THROTTLE_SECONDS = max(30, int(os.getenv("OPTIONLENS_RESPONSE_WARNING_THROTTLE_SECONDS", "300")))

REGIME_FAMILY_MAP: dict[str, str] = {
    "Range Play": "RANGE",
    "Balanced / Wait": "RANGE",
    "Balanced Structure": "RANGE",
    "Range Day": "RANGE",
    "Transition Phase": "TRANSITION",
    "Transition": "TRANSITION",
    "Opening Drive": "TREND",
    "Trend Expansion": "TREND",
    "Trend Day": "TREND",
    "Breakout Setup": "BREAKOUT",
    "Breakdown Setup": "BREAKOUT",
    "Breakdown Day": "BREAKOUT",
    "Trap Day": "TRAP",
}

# ---------------------------------------------------------------------------
# Module-level mutable state — SINGLE WORKER ONLY
# All of the dicts below are mutated exclusively by the background_update_loop
# asyncio task and are never written from multiple threads or processes.
# This architecture only supports a single Uvicorn worker (--workers 1).
# Running multiple workers will silently fork this state, causing history
# divergence between processes. Enforce single-worker in your start command
# and do NOT use gunicorn multi-worker or multiple Uvicorn instances without
# migrating this state to a shared store (e.g. Redis).
# ---------------------------------------------------------------------------

# Rolling ATR history per symbol+expiry to stabilize confidence.
_atr_history: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=ATR_ROLLING_WINDOW))
_IV_BASELINES: dict[str, list[float]] = {
    "NIFTY":     [0.10, 0.11, 0.12, 0.13, 0.14, 0.15, 0.16, 0.18],
    "BANKNIFTY": [0.12, 0.13, 0.14, 0.15, 0.16, 0.17, 0.18, 0.20],
    "FINNIFTY":  [0.11, 0.12, 0.13, 0.14, 0.15, 0.16, 0.17, 0.19],
    "SENSEX":    [0.11, 0.12, 0.13, 0.14, 0.15, 0.16, 0.17, 0.18],
}
_iv_history: dict[str, deque[float]] = defaultdict(
    lambda: deque(maxlen=90),
    {k: deque(v, maxlen=90) for k, v in _IV_BASELINES.items()}
)
_calibrated_weights: dict[str, float] = load_adaptive_weights()
_last_calibrated_session: set[str] = set()
_last_cycle_log_minute: dict[str, str] = {}
_last_market_event_minute: dict[str, str] = {}
_recent_market_event_occurrences: dict[str, deque[datetime]] = defaultdict(lambda: deque())
_last_market_event_emitted: dict[str, tuple[str, datetime]] = {}
_last_response_warning_emitted: dict[str, tuple[str, datetime]] = {}
_rotating_loggers: dict[str, logging.Logger] = {}


def _utc_iso(dt: datetime | None) -> str | None:
    if not dt:
        return None
    return dt.astimezone(timezone.utc).isoformat()


async def _clear_runtime_cache() -> None:
    async with cache._lock:  # noqa: SLF001 - updater maintenance path
        cache.option_chain_data = {}
        cache.summary_data = {}
        cache.stale_data = True


def _build_seeded_sr_anchors(state: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(state, dict):
        return {}

    resistance = _safe_float(
        state.get("current_resistance")
        or state.get("resistance_level")
        or state.get("previous_resistance")
    )
    support = _safe_float(
        state.get("current_support")
        or state.get("support_level")
        or state.get("previous_support")
    )
    if resistance is None or support is None:
        return {}

    seeded_levels = dict(state.get("levels") or {})
    seeded_support = dict(seeded_levels.get("support") or {})
    seeded_resistance = dict(seeded_levels.get("resistance") or {})
    seeded_support["immediate"] = support
    seeded_support["major"] = support
    seeded_resistance["immediate"] = resistance
    seeded_resistance["major"] = resistance
    seeded_levels["support"] = seeded_support
    seeded_levels["resistance"] = seeded_resistance

    return {
        "support_level": support,
        "resistance_level": resistance,
        "current_support": support,
        "current_resistance": resistance,
        "previous_support": support,
        "previous_resistance": resistance,
        "levels": seeded_levels,
    }


async def _seeded_runtime_flush() -> int:
    preserved_states: dict[str, dict[str, Any]] = {}
    async with cache._lock:  # noqa: SLF001 - updater maintenance path
        for key, state in (cache.previous_states or {}).items():
            seeded = _build_seeded_sr_anchors(state)
            if seeded:
                merged_state = dict(state or {})
                merged_state.update(seeded)
                preserved_states[key] = merged_state

        cache.option_chain_data = {}
        cache.summary_data = {}
        cache.stale_data = True

        for key, state in preserved_states.items():
            cache.previous_states[key] = deepcopy(state)

    for key, state in preserved_states.items():
        if key.startswith("STATE::"):
            _persist_state_snapshot("STATE", key.removeprefix("STATE::"), state)

    return len(preserved_states)


async def _check_scheduled_flush(now_ist: datetime) -> bool:
    """
    Check if current IST time matches a scheduled flush window.
    Returns True if a flush was triggered.
    Fires within a ±30 second tolerance window to survive slow cycles.
    Resets the fired-set at midnight so windows fire again each trading day.
    """
    global _flushed_windows, _flushed_windows_date, _last_seeded_flush_ist, _cycle_count_since_flush

    today = now_ist.date()
    if _flushed_windows_date != today:
        _flushed_windows = set()
        _flushed_windows_date = now_ist

    hh, mm, ss = now_ist.hour, now_ist.minute, now_ist.second
    current_total = hh * 3600 + mm * 60 + ss

    for target_h, target_m in _SCHEDULED_FLUSH_WINDOWS_IST:
        window_key = (target_h, target_m)
        if window_key in _flushed_windows:
            continue

        target_total = target_h * 3600 + target_m * 60
        if abs(current_total - target_total) <= 30:
            preserved_count = await _seeded_runtime_flush()
            _flushed_windows.add(window_key)
            _last_seeded_flush_ist = now_ist
            _cycle_count_since_flush = 0
            logger.info(
                "Seeded flush fired at %02d:%02d IST (window %02d:%02d) - preserved %d S/R anchors",
                hh,
                mm,
                target_h,
                target_m,
                preserved_count,
            )
            if window_key == (15, 30):
                try:
                    updated = update_end_of_day_calibration(session_date=today)
                    _calibrated_weights.update(updated)
                    logger.info("EOD calibration triggered by scheduled flush at 15:30 IST")
                except Exception as exc:
                    logger.warning("EOD calibration failed: %s", exc)
            return True

    return False


_cache_key = make_cache_key


def _state_snapshot_path(kind: str, key: str) -> Path:
    safe_key = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(key))
    return STATE_SNAPSHOT_DIR / f"{kind}_{safe_key}.json"


def _snapshot_family_glob(kind: str, key: str) -> str:
    safe_key = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(key))
    family_key = safe_key.rsplit("_", 1)[0] if "_" in safe_key else safe_key
    return f"{kind}_{family_key}_*.json"


def _cleanup_old_snapshots(kind: str, key: str, max_keep: int = MAX_STATE_SNAPSHOTS_PER_SERIES) -> None:
    try:
        files = sorted(
            STATE_SNAPSHOT_DIR.glob(_snapshot_family_glob(kind, key)),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for old in files[max_keep:]:
            old.unlink(missing_ok=True)
    except Exception as exc:
        logger.warning("State snapshot cleanup failed [%s][%s]: %s", kind, key, exc)


def _get_rotating_logger(path: Path) -> logging.Logger:
    cache_key = str(path.resolve())
    existing = _rotating_loggers.get(cache_key)
    if existing is not None:
        return existing

    path.parent.mkdir(parents=True, exist_ok=True)
    logger_name = f"optionlens.rotating.{len(_rotating_loggers)}"
    rotating_logger = logging.getLogger(logger_name)
    rotating_logger.setLevel(logging.INFO)
    rotating_logger.propagate = False
    rotating_logger.handlers.clear()
    handler = logging.handlers.RotatingFileHandler(
        path,
        maxBytes=LOG_ROTATION_MAX_BYTES,
        backupCount=LOG_ROTATION_BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(message)s"))
    rotating_logger.addHandler(handler)
    _rotating_loggers[cache_key] = rotating_logger
    return rotating_logger


def _append_rotating_line(path: Path, line: str) -> None:
    rotating_logger = _get_rotating_logger(path)
    rotating_logger.info(line)


def _load_persisted_state(kind: str, key: str) -> dict[str, Any]:
    path = _state_snapshot_path(kind, key)
    try:
        if not path.exists():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception as exc:
        logger.warning("State snapshot load failed [%s][%s]: %s", kind, key, exc)
        return {}


def _persist_state_snapshot(kind: str, key: str, state: dict[str, Any]) -> None:
    path = _state_snapshot_path(kind, key)
    try:
        STATE_SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, ensure_ascii=True, default=str), encoding="utf-8")
        _cleanup_old_snapshots(kind, key)
    except Exception as exc:
        logger.warning("State snapshot persist failed [%s][%s]: %s", kind, key, exc)


def _parse_timestamp_utc(text: str | None) -> datetime:
    if not text:
        return datetime.now(timezone.utc)
    for fmt in ("%d-%b-%Y %H:%M:%S", "%d-%b-%Y %H:%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            parsed = datetime.strptime(text, fmt)
            if fmt.startswith("%d-%b-%Y"):
                parsed = parsed.replace(tzinfo=IST)
                return parsed.astimezone(timezone.utc)
            return parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return datetime.now(timezone.utc)


_SESSION_PHASE_ORDER: dict[str, int] = {
    "Transition": 0,
    "Opening Drive": 1,
    "Structure Formation": 2,
    "Compression Phase": 3,
    "Position Build Phase": 4,
    "Expansion Window": 5,
}


def _current_ist_trading_session_key(now_utc: datetime | None = None) -> str | None:
    """
    Use the wall-clock IST trading day, not fetched market timestamps, for SPC/session resets.
    This prevents stale API/meta timestamps from leaking a previous day's SPC memory forward.
    Reset becomes eligible only from 09:00 IST on Monday-Friday.
    """
    current_utc = now_utc or datetime.now(timezone.utc)
    current_ist = current_utc.astimezone(IST)
    if current_ist.weekday() >= 5:
        return None
    if (current_ist.hour, current_ist.minute) < (9, 0):
        return None
    return current_ist.date().isoformat()


def _session_phase_session_key() -> str | None:
    return _current_ist_trading_session_key()


def _reset_state_for_new_session(
    previous_state: dict[str, Any] | None,
    *,
    timestamp: datetime | None,
) -> dict[str, Any] | None:
    if not isinstance(previous_state, dict):
        return previous_state
    session_key = _session_phase_session_key()
    prev_session_key = str(previous_state.get("session_date") or "").strip() or None
    if not session_key or prev_session_key == session_key:
        return previous_state

    reset_state = dict(previous_state)
    prev_levels = previous_state.get("levels", {}) if isinstance(previous_state, dict) else {}
    prev_support_obj = prev_levels.get("support", {}) if isinstance(prev_levels, dict) else {}
    prev_resistance_obj = prev_levels.get("resistance", {}) if isinstance(prev_levels, dict) else {}
    closing_support = _safe_float(previous_state.get("support_level"))
    if closing_support is None:
        closing_support = _safe_float(prev_support_obj.get("immediate"))
    closing_resistance = _safe_float(previous_state.get("resistance_level"))
    if closing_resistance is None:
        closing_resistance = _safe_float(prev_resistance_obj.get("immediate"))

    reset_state["support_level"] = closing_support
    reset_state["resistance_level"] = closing_resistance
    reset_state["previous_support"] = closing_support
    reset_state["previous_resistance"] = closing_resistance
    reset_state["current_support"] = closing_support
    reset_state["current_resistance"] = closing_resistance
    reset_state["absorption_reference_level"] = closing_support
    # Negative cycle means "carry yesterday's closing anchor for the first live cycle only".
    reset_state["support_shift_cycle"] = -1
    reset_state["sr_first_cycle_after_reset"] = True
    reset_state["session_phase"] = "Transition"
    reset_state["session_phase_confidence"] = 0.45
    reset_state["session_phase_session_key"] = session_key
    reset_state["session_date"] = session_key
    reset_state["signal_history"] = []
    reset_state["regime_hold_cycles"] = 0
    reset_state["regime_candidate"] = None
    reset_state["regime_candidate_streak"] = 0
    reset_state["regime_family"] = None
    reset_state["range_locked"] = False
    reset_state["no_edge"] = False
    reset_levels = dict(reset_state.get("levels") or {})
    reset_support_levels = dict(reset_levels.get("support") or {})
    reset_resistance_levels = dict(reset_levels.get("resistance") or {})
    reset_support_levels["immediate"] = closing_support
    reset_support_levels["major"] = closing_support
    reset_resistance_levels["immediate"] = closing_resistance
    reset_resistance_levels["major"] = closing_resistance
    reset_levels["support"] = reset_support_levels
    reset_levels["resistance"] = reset_resistance_levels
    reset_state["levels"] = reset_levels
    logger.debug(
        "Session reset anchor seeded: session=%s previous_support=%s previous_resistance=%s",
        session_key,
        closing_support,
        closing_resistance,
    )
    return reset_state


def _stabilize_session_phase(
    *,
    current_phase: str | None,
    current_confidence: float | int | None,
    timestamp: datetime | None,
    previous_state: dict[str, Any] | None,
) -> dict[str, Any]:
    phase = str(current_phase or "Transition")
    confidence = max(0.0, min(0.99, float(current_confidence or 0.0)))
    session_key = _session_phase_session_key()

    prev = previous_state or {}
    prev_phase = str(prev.get("session_phase") or "").strip()
    prev_confidence = max(0.0, min(0.99, float(prev.get("session_phase_confidence", 0.0) or 0.0)))
    prev_session_key = str(prev.get("session_phase_session_key") or "").strip() or None

    if session_key and prev_phase and prev_session_key == session_key:
        current_rank = _SESSION_PHASE_ORDER.get(phase, 0)
        prev_rank = _SESSION_PHASE_ORDER.get(prev_phase, 0)
        if prev_rank > current_rank:
            return {
                "session_phase": prev_phase,
                "confidence": round(max(prev_confidence, confidence), 2),
                "session_key": session_key,
            }

    return {
        "session_phase": phase,
        "confidence": round(confidence, 2),
        "session_key": session_key,
    }


def _append_cycle_log(entry: dict[str, Any]) -> None:
    if not ENABLE_CYCLE_LOG:
        return
    try:
        _append_rotating_line(CYCLE_LOG_PATH, json.dumps(entry, ensure_ascii=True, default=str))
    except Exception as exc:
        logger.warning("Cycle log append failed: %s", exc)


def _should_log_cycle(key: str) -> bool:
    if not ENABLE_CYCLE_LOG:
        return False
    minute_bucket = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M")
    previous = _last_cycle_log_minute.get(key)
    if previous == minute_bucket:
        return False
    _last_cycle_log_minute[key] = minute_bucket
    return True


def _is_market_hours(dt: datetime | None) -> bool:
    if not ENABLE_EVENT_LOG or dt is None:
        return False
    local_dt = dt.astimezone(IST)
    if local_dt.weekday() >= 5:
        return False
    minutes = (local_dt.hour * 60) + local_dt.minute
    return 555 <= minutes <= 930  # 09:15 to 15:30 IST


def _append_market_event(*, timestamp: datetime | None, event: str, symbol: str, expiry: str | None) -> None:
    if not _is_market_hours(timestamp):
        return
    event_text = str(event or "").strip()
    if not event_text:
        return
    ts = (timestamp or datetime.now(timezone.utc)).astimezone(IST)
    minute_bucket = ts.strftime("%Y-%m-%d %H:%M")
    dedupe_key = f"{symbol}|{expiry or 'AUTO'}|{event_text}"
    if _last_market_event_minute.get(dedupe_key) == minute_bucket:
        return
    _last_market_event_minute[dedupe_key] = minute_bucket
    try:
        label = f"{symbol} {expiry}".strip() if expiry else symbol
        if not EVENT_LOG_PATH.exists() or EVENT_LOG_PATH.stat().st_size == 0:
            _append_rotating_line(EVENT_LOG_PATH, "Time      Event")
            _append_rotating_line(EVENT_LOG_PATH, "--------------------------------")
        _append_rotating_line(EVENT_LOG_PATH, f"{ts.strftime('%H:%M')}     [{label}] {event_text}")
    except Exception as exc:
        logger.warning("Market event log append failed: %s", exc)


def _event_family(event_type: str) -> str:
    normalized = str(event_type or "").strip().lower()
    if normalized in {"oi spike", "position building", "institutional positioning"}:
        return "oi_activity"
    if normalized in {"range compression", "volatility squeeze"}:
        return "compression"
    return normalized.replace(" ", "_")


def _event_priority(event_type: str) -> int:
    normalized = str(event_type or "").strip().lower()
    priority_map = {
        "oi spike": 1,
        "position building": 2,
        "institutional positioning": 3,
        "range compression": 1,
        "volatility squeeze": 2,
        "support break": 2,
        "resistance break": 2,
        "trend reversal": 2,
    }
    return priority_map.get(normalized, 1)


def _append_market_event_record(event_record: dict[str, Any]) -> None:
    if not ENABLE_EVENT_LOG:
        return
    try:
        _append_rotating_line(EVENT_STREAM_PATH, json.dumps(event_record, ensure_ascii=True, default=str))
    except Exception as exc:
        logger.warning("Market event stream append failed: %s", exc)


def _emit_market_event(
    *,
    timestamp: datetime | None,
    raw_event: str,
    symbol: str,
    expiry: str | None,
) -> None:
    if not _is_market_hours(timestamp):
        return
    ts = (timestamp or datetime.now(timezone.utc)).astimezone(IST)
    symbol_key = f"{symbol}|{expiry or 'AUTO'}"
    occurrence_key = f"{symbol_key}|{raw_event}"
    occurrences = _recent_market_event_occurrences[occurrence_key]
    occurrences.append(ts)
    cutoff_5m = ts - timedelta(minutes=5)
    while occurrences and occurrences[0] < cutoff_5m:
        occurrences.popleft()

    event_type = raw_event
    confidence = 0.55
    supporting_events = 1

    if raw_event == "OI spike":
        count_5m = len(occurrences)
        count_3m = sum(1 for item in occurrences if item >= ts - timedelta(minutes=3))
        if count_5m >= 6:
            event_type = "Institutional Positioning"
            confidence = min(0.95, 0.72 + ((count_5m - 6) * 0.03))
            supporting_events = count_5m
        elif count_3m >= 3:
            event_type = "Position Building"
            confidence = min(0.88, 0.62 + ((count_3m - 3) * 0.05))
            supporting_events = count_3m
        else:
            confidence = min(0.6, 0.45 + ((count_3m - 1) * 0.05))
            supporting_events = count_3m
    elif raw_event == "Range compression":
        count_5m = len(occurrences)
        if count_5m >= 10:
            event_type = "Volatility Squeeze"
            confidence = min(0.9, 0.7 + ((count_5m - 10) * 0.02))
            supporting_events = count_5m
        else:
            confidence = min(0.7, 0.48 + ((count_5m - 1) * 0.03))
            supporting_events = count_5m

    family = _event_family(event_type)
    dedupe_key = f"{symbol_key}|{family}"
    previous_emit = _last_market_event_emitted.get(dedupe_key)
    if previous_emit is not None:
        previous_type, previous_ts = previous_emit
        within_60s = (ts - previous_ts).total_seconds() < 60
        if within_60s and _event_priority(event_type) <= _event_priority(previous_type):
            return
    _last_market_event_emitted[dedupe_key] = (event_type, ts)

    event_record = {
        "time": ts.isoformat(),
        "symbol": symbol,
        "expiry": expiry,
        "event_type": event_type,
        "confidence": round(float(confidence), 2),
        "supporting_events": int(supporting_events),
    }
    _append_market_event(timestamp=timestamp, event=event_type, symbol=symbol, expiry=expiry)
    _append_market_event_record(event_record)


def _recent_event_count(*, symbol: str, expiry: str | None, raw_event: str, minutes: int, timestamp: datetime | None) -> int:
    if timestamp is None:
        return 0
    ts = timestamp.astimezone(IST)
    occurrence_key = f"{symbol}|{expiry or 'AUTO'}|{raw_event}"
    occurrences = _recent_market_event_occurrences.get(occurrence_key)
    if not occurrences:
        return 0
    cutoff = ts - timedelta(minutes=minutes)
    return sum(1 for item in occurrences if item >= cutoff)


def _trim_list(value: Any, max_items: int) -> list[Any]:
    if not isinstance(value, list):
        return []
    if max_items <= 0:
        return []
    return value[:max_items]


def _sanitize_liquidity_map(liquidity_map: Any) -> list[dict[str, Any]]:
    if not isinstance(liquidity_map, list):
        return []
    sanitized_rows: list[dict[str, Any]] = []
    for row in liquidity_map:
        if not isinstance(row, dict):
            continue
        sanitized_rows.append(
            {
                "strike": row.get("strike"),
                "oi_ce": row.get("oi_ce"),
                "oi_pe": row.get("oi_pe"),
                "oi_ce_change": row.get("oi_ce_change"),
                "oi_pe_change": row.get("oi_pe_change"),
                "vol_ce": row.get("vol_ce"),
                "vol_pe": row.get("vol_pe"),
                "liquidity_score": row.get("liquidity_score"),
            }
        )
    return sanitized_rows


def _sanitize_public_market_state(market_state: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(market_state, dict):
        return {}

    allowed_keys: set[str] = {
        "volatility_state",
        "bias",
        "probability_bull",
        "probability_bear",
        "confidence",
        "clarity",
        "execution_risk",
        "state",
        "projection",
        "conflict_market_state",
        "conflict_flags",
        "primary_bias",
        "micro_bias",
        "session_phase",
        "session_phase_confidence",
        "trap_risk",
        "trap_state",
        "support",
        "resistance",
        "previous_support",
        "current_support",
        "previous_resistance",
        "current_resistance",
        "absorption_reference_level",
        "support_shift_cycle",
        "support_transition_active",
        "support_transition_badge",
        "resistance_transition_badge",
        "absorption_detected",
        "absorption_level",
        "absorption_message",
        "support_zone_pressure",
        "support_zone_state",
        "resistance_zone_pressure",
        "resistance_zone_state",
        "target1",
        "target2",
        "entry_zone",
        "stop_zone",
        "target_zone",
        "execution_mode",
        "delta_band",
        "delta_strike_guidance",
        "avoid_buying_premium",
        "summary_line",
        "decision_explanation",
        "resolved_reason",
        "blocking_reason",
        "winning_engine",
        "decision_confidence",
        "sr_breach_state",
        "alignment_score",
        "alignment_ratio",
        "pressure_state",
        "directional_pressure_score",
        "dps_adjusted",
        "oi_scenario",
        "dps_scenario_multiplier",
        "spc_state",
        "move_quality",
        "spc_decision",
        "pinning_active",
        "pinning_trap_modifier_points",
        "trade_action",
        "trade_readiness",
        "readiness_state",
        "readiness_active",
        "trade_readiness_v2",
        "readiness_state_v2",
        "readiness_active_v2",
        "readiness_structure_quality",
        "readiness_directional_alignment",
        "readiness_execution_quality",
        "readiness_risk_friction",
        "readiness_cap_reason",
        "readiness_floor_reason",
        "market_state",
        "range_locked",
        "no_edge",
        "committed_regime",
        "detected_regime",
        "candidate_regime",
        "candidate_regime_count",
        "momentum_override_score",
        "momentum_override_explanation",
        "breakout_candidate",
        "breakout_probability",
        "market_structure_score",
        "structure_state",
        "structural_state",
        "structure_bias",
        "daily_context",
        "previous_day_open",
        "previous_day_high",
        "previous_day_low",
        "previous_day_close",
        "daily_trend_bias",
        "day_trend",
        "long_trend",
        "readiness_regime_used",
        "readiness_regime_family_used",
        "readiness_range_like_session",
        "iv_rank",
        "iv_context",
        "selling_favoured",
        "strike_guidance",
        "strike_intelligence",
        "entry_target",
        "trade_side",
        "trade_side_reason",
        "entry_signal",
        "entry_signal_reason",
        "entry_signal_strength",
        "recommended_strike",
        "recommended_option",
        "recommended_action",
        "delta_target_min",
        "delta_target_max",
        "position_size_fraction",
        "stop_description",
        "target_description",
        "max_pain_strike",
        "price_magnet_strike",
        "price_magnet_combined",
        "magnet_pull_direction",
        "magnet_distance_pts",
        "secondary_magnet",
        "between_magnets",
        "magnet_character",
        "compression_zone",
        "max_pain_pull",
        "iv_skew",
        "atm_straddle_premium",
        "straddle_trend",
        "pe_wall_strike",
        "ce_wall_strike",
        "ce_wall_holding",
        "pe_wall_holding",
        "volume_spike_strikes",
        "directional_signal",
        "directional_reason",
        "directional_bias",
        "directional_size",
        "directional_strike",
        "directional_rr",
        "sr_first_cycle_after_reset",
        "sr_cold_start_guard_applied",
        "sr_previous_support_anchor_used",
        "sr_previous_support_anchor_source",
        "sr_previous_resistance_anchor_used",
        "sr_previous_resistance_anchor_source",
        "sr_support_buffer_blocked",
        "sr_resistance_buffer_blocked",
        "sr_anchor_age_seconds",
        "seeded_flush_last_fired_at",
        "cycle_count_since_flush",
        "regime",
        "drift",
        "adaptive_mode",
        "adaptive_weights",
        "directional_force",
        "reversal_risk",
        "reversal_decay_cycles",
    }
    if ENABLE_HZC:
        allowed_keys.update(
            {
                "historical_context_available",
                "historical_context_updated_at",
            }
        )

    sanitized = {key: market_state.get(key) for key in allowed_keys if key in market_state}
    sanitized["signal_history"] = _trim_list(market_state.get("signal_history"), 24)
    return sanitized


def _sanitize_public_signals(signals: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(signals, dict):
        return {}

    sanitized: dict[str, Any] = {}

    breakout = signals.get("breakout") if isinstance(signals.get("breakout"), dict) else {}
    sanitized["breakout"] = {
        "breakout_up": breakout.get("breakout_up"),
        "breakout_down": breakout.get("breakout_down"),
        "breakout_strength": breakout.get("breakout_strength"),
        "breakout_candidate": breakout.get("breakout_candidate"),
    }

    trap = signals.get("trap") if isinstance(signals.get("trap"), dict) else {}
    sanitized["trap"] = {
        "trap_probability": trap.get("trap_probability"),
        "trap_probability_pct": trap.get("trap_probability_pct"),
        "trap_type": trap.get("trap_type"),
        "trap_direction": trap.get("trap_direction"),
        "trap_affected_level": trap.get("trap_affected_level"),
        "show_affected_level": trap.get("show_affected_level"),
        "trap_state": trap.get("trap_state"),
        "trap_reason": trap.get("trap_reason"),
        "support_reason": trap.get("support_reason"),
        "oi_trap_signal": trap.get("oi_trap_signal"),
        "oi_trap_confidence": trap.get("oi_trap_confidence"),
        "oi_trap_reason": trap.get("oi_trap_reason"),
        "breach_level": trap.get("breach_level"),
        "breach_oi_confirming": trap.get("breach_oi_confirming"),
        "oi_price_divergence": trap.get("oi_price_divergence"),
    }

    material_breach = (
        signals.get("material_breach") if isinstance(signals.get("material_breach"), dict) else {}
    )
    sanitized["material_breach"] = {
        "material_breach_confirmed": material_breach.get("material_breach_confirmed"),
        "confirmation_type": material_breach.get("confirmation_type"),
        "support_broken": material_breach.get("support_broken"),
        "resistance_broken": material_breach.get("resistance_broken"),
        "absorption_conflict": material_breach.get("absorption_conflict"),
        "absorption_wins": material_breach.get("absorption_wins"),
    }

    support_absorption = (
        signals.get("support_absorption") if isinstance(signals.get("support_absorption"), dict) else {}
    )
    sanitized["support_absorption"] = {
        "absorption_detected": support_absorption.get("absorption_detected"),
        "level": support_absorption.get("level"),
        "message": support_absorption.get("message"),
    }

    sr = signals.get("sr") if isinstance(signals.get("sr"), dict) else {}
    sanitized["sr"] = {
        "support_range": sr.get("support_range"),
        "resistance_range": sr.get("resistance_range"),
        "support_center": sr.get("support_center"),
        "resistance_center": sr.get("resistance_center"),
    }

    oi = signals.get("oi") if isinstance(signals.get("oi"), dict) else {}
    sanitized["oi"] = {"oi_velocity_score": oi.get("oi_velocity_score")}

    alignment_filter = (
        signals.get("alignment_filter") if isinstance(signals.get("alignment_filter"), dict) else {}
    )
    sanitized["alignment_filter"] = {
        "alignment_score": alignment_filter.get("alignment_score"),
        "price_momentum": alignment_filter.get("price_momentum"),
        "oi_shift_score": alignment_filter.get("oi_shift_score"),
        "volume_expansion_score": alignment_filter.get("volume_expansion_score"),
        "breakout_suppressed": alignment_filter.get("breakout_suppressed"),
    }

    momentum_exhaustion = (
        signals.get("momentum_exhaustion") if isinstance(signals.get("momentum_exhaustion"), dict) else {}
    )
    sanitized["momentum_exhaustion"] = {
        "momentum_exhaustion": momentum_exhaustion.get("momentum_exhaustion"),
        "exhaustion_type": momentum_exhaustion.get("exhaustion_type"),
    }

    auto_exit = signals.get("auto_exit") if isinstance(signals.get("auto_exit"), dict) else {}
    sanitized["auto_exit"] = {
        "exit_signal": auto_exit.get("exit_signal"),
        "exit_reason": auto_exit.get("exit_reason"),
    }

    expiry_adaptive = (
        signals.get("expiry_adaptive") if isinstance(signals.get("expiry_adaptive"), dict) else {}
    )
    sanitized["expiry_adaptive"] = {
        "expiry_mode": expiry_adaptive.get("expiry_mode"),
        "expiry_multiplier": expiry_adaptive.get("expiry_multiplier"),
        "adjustedMove": expiry_adaptive.get("adjustedMove"),
    }
    intraday_zones = (
        signals.get("intraday_zones") if isinstance(signals.get("intraday_zones"), dict) else {}
    )
    sanitized["intraday_zones"] = {
        "zones": _trim_list(intraday_zones.get("zones"), 12),
        "nearest_intraday_zone": intraday_zones.get("nearest_intraday_zone"),
        "opening_range_broken": intraday_zones.get("opening_range_broken"),
        "opening_range_width": intraday_zones.get("opening_range_width"),
        "session_range_width": intraday_zones.get("session_range_width"),
    }
    sanitized["chain_greeks"] = _trim_list(signals.get("chain_greeks"), 20)
    sanitized["liquidity_map"] = _sanitize_liquidity_map(signals.get("liquidity_map"))

    sanitized["breakout_candidate"] = signals.get("breakout_candidate")
    sanitized["sr_breach_state"] = signals.get("sr_breach_state")
    sanitized["alerts"] = _trim_list(signals.get("alerts"), 12)
    sanitized["prioritized_signals"] = _trim_list(signals.get("prioritized_signals"), 8)
    return sanitized


def _sanitize_public_levels(levels: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(levels, dict):
        return {}

    def _compact_level(block: Any) -> dict[str, Any]:
        if not isinstance(block, dict):
            return {}
        return {
            "strike": block.get("strike"),
            "immediate": block.get("immediate"),
            "major": block.get("major"),
            "range": block.get("range"),
            "zone_pressure": block.get("zone_pressure"),
            "zone_state": block.get("zone_state"),
            "score": block.get("score"),
        }

    support = _compact_level(levels.get("support"))
    resistance = _compact_level(levels.get("resistance"))
    return {
        "support": support,
        "resistance": resistance,
        "support_strike": levels.get("support_strike", support.get("strike")),
        "resistance_strike": levels.get("resistance_strike", resistance.get("strike")),
        "target_1": levels.get("target_1"),
        "target_2": levels.get("target_2"),
        "acceleration_zone": levels.get("acceleration_zone"),
    }


def _sanitize_public_v2_payload(v2_payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(v2_payload, dict):
        return {}

    sanitized: dict[str, Any] = {
        "is_complete": bool(v2_payload.get("is_complete", True)),
        "meta": v2_payload.get("meta", {}),
        "warnings": _trim_list(v2_payload.get("warnings"), 48),
        "market_insight": _trim_list(v2_payload.get("market_insight"), 20),
        "institutional_structure": v2_payload.get("institutional_structure"),
        "previous_support": v2_payload.get("previous_support"),
        "current_support": v2_payload.get("current_support"),
        "previous_resistance": v2_payload.get("previous_resistance"),
        "current_resistance": v2_payload.get("current_resistance"),
        "absorption_reference_level": v2_payload.get("absorption_reference_level"),
        "decision_engine": v2_payload.get("decision_engine", {}),
        "market_state": _sanitize_public_market_state(v2_payload.get("market_state", {})),
        "levels": _sanitize_public_levels(v2_payload.get("levels", {})),
        "signals": _sanitize_public_signals(v2_payload.get("signals", {})),
        "trade_plan": v2_payload.get("trade_plan", {}),
        "intraday_playbook": v2_payload.get("intraday_playbook", {}),
        "daily_context": v2_payload.get("daily_context"),
        "performance": v2_payload.get("performance"),
    }
    return sanitized


def _parse_minute_bucket(bucket: Any) -> datetime | None:
    text = str(bucket or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M"):
        try:
            parsed = datetime.strptime(text, fmt)
            if fmt == "%Y-%m-%d %H:%M":
                return parsed.replace(tzinfo=IST).astimezone(timezone.utc)
            return parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    try:
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def _prune_runtime_maps() -> None:
    now_utc = datetime.now(timezone.utc)
    cutoff_utc = now_utc - timedelta(hours=2)
    cutoff_ist = now_utc.astimezone(IST) - timedelta(hours=2)

    for key, bucket in list(_last_cycle_log_minute.items()):
        parsed = _parse_minute_bucket(bucket)
        if parsed is None or parsed < cutoff_utc:
            _last_cycle_log_minute.pop(key, None)

    for key, bucket in list(_last_market_event_minute.items()):
        parsed = _parse_minute_bucket(bucket)
        if parsed is None or parsed < cutoff_utc:
            _last_market_event_minute.pop(key, None)

    for key, payload in list(_last_market_event_emitted.items()):
        if not isinstance(payload, tuple) or len(payload) != 2:
            _last_market_event_emitted.pop(key, None)
            continue
        event_type, emitted_ts = payload
        if not isinstance(emitted_ts, datetime):
            _last_market_event_emitted.pop(key, None)
            continue
        emitted_utc = emitted_ts.astimezone(timezone.utc) if emitted_ts.tzinfo else emitted_ts.replace(tzinfo=IST).astimezone(timezone.utc)
        if emitted_utc < cutoff_utc:
            _last_market_event_emitted.pop(key, None)
            continue
        _last_market_event_emitted[key] = (event_type, emitted_ts)

    for key, occurrences in list(_recent_market_event_occurrences.items()):
        if not isinstance(occurrences, deque):
            _recent_market_event_occurrences.pop(key, None)
            continue
        while occurrences and occurrences[0] < cutoff_ist:
            occurrences.popleft()
        while len(occurrences) > 512:
            occurrences.popleft()
        if not occurrences:
            _recent_market_event_occurrences.pop(key, None)

    for key, payload in list(_last_response_warning_emitted.items()):
        if not isinstance(payload, tuple) or len(payload) != 2:
            _last_response_warning_emitted.pop(key, None)
            continue
        _, emitted_ts = payload
        if not isinstance(emitted_ts, datetime):
            _last_response_warning_emitted.pop(key, None)
            continue
        emitted_utc = emitted_ts.astimezone(timezone.utc) if emitted_ts.tzinfo else emitted_ts.replace(tzinfo=timezone.utc)
        if emitted_utc < cutoff_utc:
            _last_response_warning_emitted.pop(key, None)


def _should_emit_response_warning(
    *,
    symbol: str,
    expiry: str | None,
    warnings: list[str],
    timestamp: datetime | None,
) -> bool:
    warning_signature = ",".join(str(item) for item in (warnings or []) if item)
    if not warning_signature:
        return False
    key = f"{symbol}::{expiry or 'AUTO'}"
    now = (timestamp or datetime.now(timezone.utc)).astimezone(timezone.utc)
    prior = _last_response_warning_emitted.get(key)
    if prior:
        previous_signature, previous_ts = prior
        if previous_signature == warning_signature and (now - previous_ts).total_seconds() < RESPONSE_WARNING_THROTTLE_SECONDS:
            return False
    _last_response_warning_emitted[key] = (warning_signature, now)
    return True


def _detect_support_absorption(
    *,
    spot: float | None,
    support: float | None,
    strike_gap: float | None,
    pe_oi_change_pct: float | None,
    volume_expansion_score: float,
    breakout_strength: float,
    trap_probability: float,
) -> dict[str, Any]:
    spot_value = _safe_float(spot)
    support_value = _safe_float(support)
    strike_step = max(1.0, float(strike_gap or 50.0))
    absorption_offset = strike_step * 0.4
    pe_change = float(pe_oi_change_pct or 0.0)
    volume_score = float(volume_expansion_score or 0.0)
    breakout_score = float(breakout_strength or 0.0)
    trap_prob = float(trap_probability or 0.0)

    # Proximity check: price must still be near (or below) support — hard prerequisite.
    near_support = (
        spot_value is not None
        and support_value is not None
        and spot_value < (support_value + absorption_offset)
    )
    if not near_support:
        return {
            "absorption_detected": False,
            "absorption_score": 0.0,
            "level": support_value,
            "offset": round(absorption_offset, 2),
            "message": None,
        }

    # Weighted scoring replaces the hard AND gate.
    # Each signal contributes a partial score; any two strong signals can fire.
    pe_score = min(1.0, max(0.0, pe_change / 20.0))           # 10%→0.5, 20%→1.0
    vol_score = min(1.0, max(0.0, (volume_score - 0.4) / 0.6)) # 0.4→0, 1.0→1.0
    no_breakout_score = min(1.0, max(0.0, 1.0 - breakout_score / 0.5))  # <0.25→high
    trap_score = min(1.0, max(0.0, (trap_prob - 40.0) / 40.0))  # 40→0, 80→1.0

    absorption_score = (
        (pe_score * 0.35)
        + (vol_score * 0.25)
        + (no_breakout_score * 0.20)
        + (trap_score * 0.20)
    )

    # Trigger at 0.45 (replaces requiring all four conditions).
    absorption_detected = absorption_score >= 0.45

    return {
        "absorption_detected": absorption_detected,
        "absorption_score": round(absorption_score, 4),
        "level": support_value,
        "offset": round(absorption_offset, 2),
        "message": "Support absorption detected — breakdown likely fake" if absorption_detected else None,
    }


def _resolve_absorption_reference_level(
    *,
    spot: float | None,
    current_support: float | None,
    current_resistance: float | None,
    current_timestamp_utc: datetime | None,
    previous_state: dict[str, Any] | None,
) -> dict[str, Any]:
    prev = previous_state or {}
    prev_current_support = _safe_float(prev.get("current_support"))
    prev_previous_support = _safe_float(prev.get("previous_support"))
    prev_current_resistance = _safe_float(prev.get("current_resistance"))
    prev_previous_resistance = _safe_float(prev.get("previous_resistance"))
    prev_shift_cycle = int(prev.get("support_shift_cycle", 0) or 0)
    prev_anchor_started_raw = str(prev.get("sr_anchor_started_at_utc") or "").strip()
    prev_anchor_started_utc: datetime | None = None
    if prev_anchor_started_raw:
        try:
            parsed = datetime.fromisoformat(prev_anchor_started_raw)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            prev_anchor_started_utc = parsed.astimezone(timezone.utc)
        except ValueError:
            prev_anchor_started_utc = None
    now_utc = current_timestamp_utc or datetime.now(timezone.utc)

    current_support_value = _safe_float(current_support)
    current_resistance_value = _safe_float(current_resistance)
    support_shift_detected = bool(
        current_support_value is not None
        and prev_current_support is not None
        and abs(current_support_value - prev_current_support) > 1e-6
    )

    if support_shift_detected:
        previous_support = prev_current_support
        support_shift_cycle = 1
    else:
        previous_support = prev_previous_support if prev_previous_support is not None else prev_current_support
        support_shift_cycle = prev_shift_cycle

        if previous_support is not None and current_support_value is not None and previous_support != current_support_value:
            if prev_shift_cycle == 1:
                support_shift_cycle = 2
            else:
                support_shift_cycle = 0
        elif prev_shift_cycle < 0:
            previous_support = prev_previous_support if prev_previous_support is not None else prev_current_support
            support_shift_cycle = 0
        else:
            support_shift_cycle = 0

    resistance_shift_detected = (
        current_resistance_value is not None
        and prev_current_resistance is not None
        and abs(current_resistance_value - prev_current_resistance) > 1e-6
    )
    if resistance_shift_detected:
        previous_resistance = prev_current_resistance
    else:
        # Keep prior-session resistance memory alive at session open even when the
        # reset seeded current_resistance == previous_resistance. Dropping it to
        # None here blanks prev-R visuals and deprives breach confirmation of its
        # opening structural anchor.
        previous_resistance = (
            prev_previous_resistance
            if prev_previous_resistance is not None
            else prev_current_resistance
        )

    if support_shift_detected or resistance_shift_detected or prev_anchor_started_utc is None:
        anchor_started_utc = now_utc
    else:
        anchor_started_utc = prev_anchor_started_utc
    sr_anchor_age_seconds = max(0, int((now_utc - anchor_started_utc).total_seconds()))

    resolved = {
        "previous_support": previous_support,
        "current_support": current_support_value,
        "previous_resistance": previous_resistance,
        "current_resistance": current_resistance_value,
        # Absorption should be computed against the active committed support.
        # Keep transition telemetry separately via previous_support/support_shift_cycle.
        "absorption_reference_level": current_support_value,
        "support_shift_cycle": int(support_shift_cycle),
        "sr_anchor_started_at_utc": _utc_iso(anchor_started_utc),
        "sr_anchor_age_seconds": sr_anchor_age_seconds,
    }
    logger.debug(
        "Support reference resolved: previous_support=%s current_support=%s previous_resistance=%s current_resistance=%s shift_cycle=%s",
        resolved.get("previous_support"),
        resolved.get("current_support"),
        resolved.get("previous_resistance"),
        resolved.get("current_resistance"),
        resolved.get("support_shift_cycle"),
    )
    return resolved


def _is_support_transition_active(support_shift_cycle: Any) -> bool:
    cycle = int(support_shift_cycle or 0)
    return cycle == 1


def _canonicalize_trap_reference(
    *,
    trap: dict[str, Any],
    spot: float | None,
    support_level: float | None,
    resistance_level: float | None,
    breakout_up: bool,
    breakout_down: bool,
) -> tuple[float | None, str]:
    spot_value = _safe_float(spot)
    support_value = _safe_float(support_level)
    resistance_value = _safe_float(resistance_level)
    raw_direction = str(trap.get("trap_direction") or "").strip().lower()
    raw_type = str(trap.get("trap_type") or "").strip().lower()

    if (
        spot_value is not None
        and support_value is not None
        and resistance_value is not None
        and resistance_value > support_value
    ):
        dist_to_support = max(0.0, spot_value - support_value)
        dist_to_resistance = max(0.0, resistance_value - spot_value)
        if dist_to_support < dist_to_resistance:
            return support_value, "upside"
        return resistance_value, "downside"

    if raw_direction == "downside" and resistance_value is not None:
        return resistance_value, "downside"
    if raw_direction == "upside" and support_value is not None:
        return support_value, "upside"

    if breakout_up and resistance_value is not None:
        return resistance_value, "upside"
    if breakout_down and support_value is not None:
        return support_value, "downside"
    if ("breakdown" in raw_type or "support" in raw_type) and support_value is not None:
        return support_value, "downside"
    if ("breakout" in raw_type or "resistance" in raw_type) and resistance_value is not None:
        return resistance_value, "upside"

    return None, ""


def _infer_session_phase(timestamp_text: str | None) -> str:
    if not timestamp_text:
        return "Transition"
    import re

    match = re.search(r"(\d{1,2}):(\d{2})", str(timestamp_text))
    if not match:
        return "Transition"
    hh = int(match.group(1))
    mm = int(match.group(2))
    minutes = (hh * 60) + mm
    if 9 * 60 + 15 <= minutes < 10 * 60 + 30:
        return "Opening"
    if 10 * 60 + 30 <= minutes < 13 * 60 + 30:
        return "Midday"
    if 14 * 60 + 30 <= minutes <= 15 * 60 + 30:
        return "PowerHour"
    return "Transition"


def _derive_breakout_strength(
    *,
    spot: float | None,
    support: float | None,
    resistance: float | None,
    breakout: dict[str, Any],
) -> float:
    if spot is None:
        return 0.0
    threshold = float(breakout.get("threshold_points", 0.0) or 0.0)
    threshold = max(1.0, threshold)
    if breakout.get("breakout_up") and resistance is not None:
        return max(0.0, min(1.0, (float(spot) - float(resistance)) / threshold))
    if breakout.get("breakout_down") and support is not None:
        return max(0.0, min(1.0, (float(support) - float(spot)) / threshold))
    return 0.0


def _compute_alignment_score(
    *,
    spot: float | None,
    previous_spot: float | None,
    oi_shift_score: float,
    volume_expansion_score: float,
) -> dict[str, float]:
    price_momentum = 0.0
    if spot is not None and previous_spot is not None and previous_spot > 0:
        pct_change = abs((float(spot) - float(previous_spot)) / float(previous_spot)) * 100.0
        # 0.5% move maps to full momentum score.
        price_momentum = max(0.0, min(1.0, pct_change / 0.5))
    alignment_score = (0.4 * price_momentum) + (0.35 * oi_shift_score) + (0.25 * volume_expansion_score)
    alignment_score = max(0.0, min(1.0, alignment_score))
    return {"alignment_score": round(alignment_score, 4), "price_momentum": round(price_momentum, 4)}


def _compute_market_structure_score(
    *,
    alignment_score: float,
    breakout_strength: float,
    oi_velocity_score: float,
    clarity: float,
    trap_probability: float,
) -> dict[str, Any]:
    clarity_norm = max(0.0, min(1.0, float(clarity) / 100.0))
    trap_norm = max(0.0, min(1.0, float(trap_probability) / 100.0))
    raw = (
        (0.30 * max(0.0, min(1.0, float(alignment_score))))
        + (0.25 * max(0.0, min(1.0, float(breakout_strength))))
        + (0.20 * max(0.0, min(1.0, float(oi_velocity_score))))
        + (0.15 * clarity_norm)
        - (0.20 * trap_norm)
    )
    mss = max(0.0, min(100.0, raw * 100.0))
    if mss > 80:
        structure = "Strong Expansion"
    elif mss > 65:
        structure = "Trend Developing"
    elif mss > 50:
        structure = "Balanced"
    elif mss > 35:
        structure = "Weak Structure"
    else:
        structure = "High Trap Risk"
    return {"market_structure_score": round(mss, 2), "structure_state": structure}


def _compute_directional_pressure_score(
    *,
    directional_force: dict[str, Any],
    alignment_score: float,
    market_structure_score: float,
    oi_bias: float,
    oi_velocity_score: float,
    volume_expansion_score: float,
    ce_rvr: float | None = None,
    pe_rvr: float | None = None,
    oi_buildup_type: str | None = None,
    trap_probability: float,
    spot: float | None = None,
    support: float | None = None,
    resistance: float | None = None,
    day_high: float | None = None,
    day_low: float | None = None,
    previous_alignment_score: float | None = None,
    previous_directional_dominance: str | None = None,
) -> dict[str, Any]:
    bull_force = max(0.0, min(1.0, float(directional_force.get("bull", 0.0) or 0.0) / 100.0))
    bear_force = max(0.0, min(1.0, float(directional_force.get("bear", 0.0) or 0.0) / 100.0))
    alignment = float(alignment_score or 0.0)
    oi_bias_value = float(oi_bias or 0.0)
    oi_velocity = max(0.0, min(1.0, float(oi_velocity_score or 0.0)))
    volume_expansion = max(0.0, min(1.0, float(volume_expansion_score or 0.0)))
    # Directional volume:
    # - bullish confirmation from PE-side participation
    # - bearish confirmation from CE-side participation
    bull_volume = (
        max(0.0, min(1.0, float(pe_rvr or 0.0)))
        if isinstance(pe_rvr, (int, float))
        else volume_expansion
    )
    bear_volume = (
        max(0.0, min(1.0, float(ce_rvr or 0.0)))
        if isinstance(ce_rvr, (int, float))
        else volume_expansion
    )
    mss_component = max(0.0, min(10.0, float(market_structure_score or 0.0) / 10.0))
    trap_penalty = max(0.0, min(1.0, float(trap_probability or 0.0) / 100.0)) * 0.2

    bull_score = (
        (bull_force * 0.35)
        + (max(0.0, alignment) * 0.25)
        + (max(0.0, oi_bias_value) * 0.15)
        + (bull_volume * 0.10)
        + (mss_component * 0.10)
    )
    bear_score = (
        (bear_force * 0.35)
        + (max(0.0, -alignment) * 0.25)
        + (max(0.0, -oi_bias_value) * 0.15)
        + (bear_volume * 0.10)
        + (mss_component * 0.10)
    )

    dps = bull_score - bear_score

    # OI scenario quality modifier:
    # Short-covering and long-unwinding moves are treated as weaker directional
    # pressure than equivalent price-only movement.
    buildup_text = str(oi_buildup_type or "").strip().lower()
    oi_building = oi_velocity > 0.55
    oi_unwinding = oi_velocity < 0.25
    price_up = dps > 0.1
    price_down = dps < -0.1
    session_high = _safe_float(day_high)
    session_low = _safe_float(day_low)
    session_range_pct = 0.0
    if session_high is not None and session_low not in (None, 0) and session_high > session_low:
        session_range_pct = ((float(session_high) - float(session_low)) / float(session_low)) * 100.0
    above_resistance = float(spot or 0.0) > float(resistance or 0.0) if resistance else False
    below_support = float(spot or 0.0) < float(support or 0.0) if support else False
    structural_break = above_resistance or below_support
    if buildup_text == "two-sided writing":
        scenario = "PINNING"
        if structural_break:
            scenario_multiplier = 0.75
        elif session_range_pct > 1.5:
            scenario_multiplier = 0.75
        elif session_range_pct > 1.0:
            scenario_multiplier = 0.65
        else:
            scenario_multiplier = PINNING_SCENARIO_MULTIPLIER
    elif price_up and oi_building:
        scenario = "LONG_BUILDUP"
        scenario_multiplier = 1.0
    elif price_up and oi_unwinding:
        scenario = "SHORT_COVERING"
        scenario_multiplier = 0.65
    elif price_down and oi_building:
        scenario = "SHORT_BUILDUP"
        scenario_multiplier = 1.0
    elif price_down and oi_unwinding:
        scenario = "LONG_UNWINDING"
        scenario_multiplier = 0.65
    else:
        scenario = "NEUTRAL"
        scenario_multiplier = 1.0

    dps_scenario_adjusted = dps * scenario_multiplier
    dps_adjusted = dps_scenario_adjusted * (1.0 - trap_penalty)
    current_alignment_sign = 1 if alignment > 0 else -1 if alignment < 0 else 0
    previous_alignment_value = float(previous_alignment_score or 0.0)
    previous_alignment_sign = 1 if previous_alignment_value > 0 else -1 if previous_alignment_value < 0 else 0
    current_directional_dominance = "bullish" if bull_force > bear_force else "bearish" if bear_force > bull_force else "neutral"
    previous_dominance = str(previous_directional_dominance or "neutral").strip().lower()
    reversal_detected = (
        (previous_alignment_sign != 0 and current_alignment_sign != 0 and previous_alignment_sign != current_alignment_sign)
        or (previous_dominance in {"bullish", "bearish"} and current_directional_dominance != previous_dominance)
    )
    if reversal_detected:
        dps *= REVERSAL_DECAY
        dps_adjusted *= REVERSAL_DECAY

    pressure_state, trade_action, explanation = _pressure_labels_from_dps_adjusted(dps_adjusted)

    return {
        "directional_pressure_score": round(dps, 4),
        "dps_scenario_adjusted": round(dps_scenario_adjusted, 4),
        "dps_adjusted": round(dps_adjusted, 4),
        "oi_scenario": scenario,
        "session_range_pct": round(float(session_range_pct), 4),
        "oi_scenario_multiplier": round(float(scenario_multiplier), 4),
        "pinning_active": scenario == "PINNING",
        "pressure_state": pressure_state,
        "trade_action": trade_action,
        "pressure_explanation": explanation,
        "directional_dominance": current_directional_dominance,
        "dps_decay_applied": reversal_detected,
    }


def _pressure_labels_from_dps_adjusted(dps_adjusted: float) -> tuple[str, str, str]:
    adjusted = float(dps_adjusted or 0.0)
    if adjusted > 0.5:
        pressure_state = "Strong Bull Pressure"
    elif adjusted > 0.35:
        pressure_state = "Mild Bull Pressure"
    elif adjusted < -0.5:
        pressure_state = "Strong Bear Pressure"
    elif adjusted < -0.35:
        pressure_state = "Mild Bear Pressure"
    else:
        pressure_state = "Balanced Pressure"

    if adjusted > 0.35:
        trade_action = "LONG BIAS"
        explanation = "Upside pressure building across OI and alignment."
    elif adjusted < -0.35:
        trade_action = "SHORT BIAS"
        explanation = "Downside pressure increasing across writer activity."
    else:
        trade_action = "WAIT"
        explanation = "Directional pressure remains balanced."
    return pressure_state, trade_action, explanation


def _resolve_spc_state(
    *,
    spot: float | None,
    support_level: float | None,
    resistance_level: float | None,
    support_broken: bool,
    resistance_broken: bool,
    material_breach_confirmed: bool,
    near_threshold_points: float = 30.0,
) -> str:
    if (
        spot is None
        or support_level is None
        or resistance_level is None
        or resistance_level <= support_level
    ):
        return "WITHIN_STRUCTURE"

    if material_breach_confirmed and (support_broken ^ resistance_broken):
        return "CONFIRMED_EXPANSION"
    if resistance_broken and not support_broken:
        return "BREAKOUT_ATTEMPT"
    if support_broken and not resistance_broken:
        return "BREAKDOWN_ATTEMPT"

    threshold = max(1.0, float(near_threshold_points or 30.0))
    dist_to_support = float(spot) - float(support_level)
    dist_to_resistance = float(resistance_level) - float(spot)

    if dist_to_support >= 0 and dist_to_support <= threshold:
        return "SUPPORT_DEFENSE"
    if dist_to_resistance >= 0 and dist_to_resistance <= threshold:
        return "RESISTANCE_PRESSURE"
    return "WITHIN_STRUCTURE"


def _resolve_move_quality(
    *,
    spc_state: str,
    trap_probability: float,
    absorption_detected: bool,
    material_breach_confirmed: bool,
    support_transition_active: bool,
    resistance_transition_active: bool,
) -> str:
    trap_value = max(0.0, min(100.0, float(trap_probability or 0.0)))
    structural_transition = bool(support_transition_active or resistance_transition_active)

    if absorption_detected:
        return "FAKE"

    if spc_state == "CONFIRMED_EXPANSION":
        if material_breach_confirmed and trap_value < 60.0 and not structural_transition:
            return "TRUSTED"
        if trap_value >= 70.0:
            return "FAKE"
        return "SUSPECT"

    if spc_state in {"BREAKOUT_ATTEMPT", "BREAKDOWN_ATTEMPT"}:
        if trap_value >= 70.0:
            return "FAKE"
        if structural_transition or trap_value >= 55.0 or not material_breach_confirmed:
            return "SUSPECT"
        return "TRUSTED"

    if spc_state in {"SUPPORT_DEFENSE", "RESISTANCE_PRESSURE"}:
        if trap_value >= 72.0:
            return "FAKE"
        if structural_transition or trap_value >= 58.0:
            return "SUSPECT"
        return "TRUSTED"

    return "SUSPECT"


def _derive_spc_decision(
    *,
    spc_state: str,
    move_quality: str,
    trade_readiness: float,
    readiness_active: bool,
) -> str:
    readiness = max(0.0, min(100.0, float(trade_readiness or 0.0)))

    if spc_state == "WITHIN_STRUCTURE":
        return "WAIT"
    if move_quality == "FAKE":
        return "DISTRUST"

    if spc_state == "CONFIRMED_EXPANSION":
        if move_quality == "TRUSTED" and readiness_active and readiness >= 60.0:
            return "ACT"
        if move_quality == "SUSPECT" and readiness_active and readiness >= 68.0:
            return "ACT"
        return "WAIT"

    if spc_state in {"BREAKOUT_ATTEMPT", "BREAKDOWN_ATTEMPT"}:
        if move_quality == "TRUSTED" and readiness_active and readiness >= 58.0:
            return "ACT"
        if move_quality == "SUSPECT":
            return "WAIT"
        return "DISTRUST"

    if spc_state == "SUPPORT_DEFENSE":
        if move_quality != "FAKE" and readiness_active and readiness >= 55.0:
            return "ACT"
        return "WAIT"

    if spc_state == "RESISTANCE_PRESSURE":
        if move_quality == "TRUSTED" and readiness_active and readiness >= 58.0:
            return "ACT"
        return "WAIT"

    return "WAIT"


def _map_spc_decision_to_trade_action(
    *,
    spc_decision: str,
    spc_state: str,
    support_broken: bool,
    resistance_broken: bool,
    dps_adjusted: float,
    fallback_trade_action: str,
) -> str:
    if spc_decision != "ACT":
        return "WAIT"

    if spc_state in {"SUPPORT_DEFENSE", "BREAKOUT_ATTEMPT"}:
        return "LONG BIAS"
    if spc_state in {"RESISTANCE_PRESSURE", "BREAKDOWN_ATTEMPT"}:
        return "SHORT BIAS"
    if spc_state == "CONFIRMED_EXPANSION":
        if resistance_broken and not support_broken:
            return "LONG BIAS"
        if support_broken and not resistance_broken:
            return "SHORT BIAS"

    dps_value = float(dps_adjusted or 0.0)
    if dps_value > 0.35:
        return "LONG BIAS"
    if dps_value < -0.35:
        return "SHORT BIAS"
    fallback = str(fallback_trade_action or "WAIT").upper()
    if fallback in {"LONG BIAS", "SHORT BIAS"}:
        return fallback
    return "WAIT"


def _compute_trade_readiness(
    *,
    clarity: float,
    alignment_score: float,
    trap_probability: float,
    execution_risk: float,
    breakout_suppressed: bool,
    breakout_candidate: bool,
    breakout_probability: float = 0.0,
    skip_trap_deduction: bool = False,
) -> dict[str, Any]:
    clarity_value = max(0.0, min(100.0, float(clarity or 0.0)))
    alignment_component = max(0.0, min(100.0, abs(float(alignment_score or 0.0)) * 100.0))
    risk_component = (1.0 - max(0.0, min(1.0, float(execution_risk or 0.0) / 100.0))) * 100.0
    base_score = (
        (clarity_value * 0.35)
        + (alignment_component * 0.25)
        + (risk_component * 0.15)
    )
    trap_value = max(0.0, min(100.0, float(trap_probability or 0.0)))
    # Keep trap impact light around the neutral 55 baseline and scale only the excess risk.
    trap_deduction = (
        0.0
        if (skip_trap_deduction or breakout_suppressed or breakout_candidate)
        else min(10.0, max(0.0, trap_value - 55.0) * 0.25)
    )
    readiness = base_score - trap_deduction
    readiness += max(0.0, min(100.0, float(breakout_probability or 0.0))) * 0.10
    readiness = max(0.0, min(100.0, readiness))
    if readiness >= 70.0:
        readiness_state = "High"
    elif readiness >= 40.0:
        readiness_state = "Moderate"
    else:
        readiness_state = "Low"
    return {
        "trade_readiness": round(readiness, 2),
        "readiness_state": readiness_state,
    }


def _clamp_score_0_100(value: float) -> float:
    return max(0.0, min(100.0, float(value or 0.0)))


READINESS_V2_PILLAR_ALPHA = 0.28
READINESS_V2_FINAL_ALPHA = 0.35
READINESS_V2_DEADBAND = 2.0
READINESS_V2_PILLAR_UP_STEP = 5.0
READINESS_V2_PILLAR_DOWN_STEP = 8.0
READINESS_V2_FINAL_UP_STEP = 5.0
READINESS_V2_FINAL_DOWN_STEP = 10.0
READINESS_ACTIVE_ON_THRESHOLD = 62.0
READINESS_ACTIVE_OFF_THRESHOLD = 52.0


def _is_invalid_readiness_sr_geometry(
    support: float | None,
    resistance: float | None,
) -> bool:
    support_value = _safe_float(support)
    resistance_value = _safe_float(resistance)
    return (
        support_value is None
        or resistance_value is None
        or resistance_value <= support_value
    )


def _smooth_readiness_value(
    new_value: float,
    prev_value: float | None,
    *,
    alpha: float,
    deadband: float,
    up_max_step: float,
    down_max_step: float,
) -> tuple[float, bool]:
    new_score = _clamp_score_0_100(new_value)
    prev_score = _safe_float(prev_value)
    if prev_score is None:
        return new_score, False
    if abs(new_score - prev_score) < deadband:
        return prev_score, False

    smoothed = (prev_score * (1.0 - alpha)) + (new_score * alpha)
    upper_bound = prev_score + max(0.0, float(up_max_step or 0.0))
    lower_bound = prev_score - max(0.0, float(down_max_step or 0.0))
    smoothed = min(upper_bound, max(lower_bound, smoothed))
    return _clamp_score_0_100(smoothed), True


def _score_readiness_structure_quality(
    *,
    committed_regime: str,
    regime_hold_cycles: int,
    support_transition_badge: bool,
    resistance_transition_badge: bool,
    support_shift_cycle: int,
    candidate_regime_count: int,
    structural_state: str,
    material_breach_confirmed: bool,
    support_unchanged: bool,
    resistance_unchanged: bool,
) -> float:
    score = 50.0
    if regime_hold_cycles >= 3:
        score += 20.0
    if support_unchanged and resistance_unchanged:
        score += 15.0
    if structural_state in {"STABLE"}:
        score += 10.0
    if material_breach_confirmed:
        score += 10.0
    if support_transition_badge:
        score -= 20.0
    if resistance_transition_badge:
        score -= 15.0
    if support_shift_cycle > 0:
        score -= 10.0
    if candidate_regime_count > 0:
        score -= 15.0
    if structural_state in {"TRANSITION", "ABSORPTION", "TRAP_RISK"}:
        score -= 15.0
    if _regime_family(committed_regime) == "RANGE" and structural_state == "STABLE":
        score += 5.0
    return _clamp_score_0_100(score)


def _is_readiness_range_like_session(
    *,
    committed_regime: str,
    stabilized_regime_family: str | None,
    range_locked: bool,
    no_edge: bool,
) -> bool:
    return bool(
        str(stabilized_regime_family or "").strip().upper() == "RANGE"
        or _regime_family(committed_regime) == "RANGE"
        or range_locked
        or no_edge
    )


def _score_readiness_directional_alignment(
    *,
    bias: str,
    breakout_probability_up: float,
    breakout_probability_down: float,
    support_zone_pressure: float,
    resistance_zone_pressure: float,
    winning_engine: str,
    conflict_market_state: str,
) -> float:
    score = 50.0
    bias_text = str(bias or "Neutral").strip().lower()
    prob_up = _clamp_score_0_100(breakout_probability_up)
    prob_down = _clamp_score_0_100(breakout_probability_down)
    prob_gap = prob_up - prob_down

    if bias_text == "bullish":
        score += 20.0
        if prob_gap >= 8.0:
            score += 15.0
        if float(support_zone_pressure or 0.0) >= 60.0:
            score += 10.0
    elif bias_text == "bearish":
        score += 20.0
        if prob_gap <= -8.0:
            score += 15.0
        if float(resistance_zone_pressure or 0.0) >= 60.0:
            score += 10.0

    if winning_engine in {"material_breach_engine", "promotion_guard"} and bias_text in {"bullish", "bearish"}:
        score += 10.0
    if str(conflict_market_state or "").strip().lower() in {"range conflict", "balanced", "compression", "no_edge"}:
        score -= 20.0
    if winning_engine == "trap_engine" and bias_text in {"bullish", "bearish"}:
        score -= 15.0
    if bias_text in {"bullish", "bearish"} and abs(prob_gap) < 8.0:
        score -= 10.0
    if bias_text == "bullish" and float(resistance_zone_pressure or 0.0) > float(support_zone_pressure or 0.0) + 10.0:
        score -= 10.0
    if bias_text == "bearish" and float(support_zone_pressure or 0.0) > float(resistance_zone_pressure or 0.0) + 10.0:
        score -= 10.0
    return _clamp_score_0_100(score)


def _score_readiness_execution_quality(
    *,
    spot: float | None,
    support: float | None,
    resistance: float | None,
    bias: str,
    session_phase: str,
    structural_state: str,
    material_breach_confirmed: bool,
) -> float:
    score = 45.0
    spot_value = _safe_float(spot)
    support_value = _safe_float(support)
    resistance_value = _safe_float(resistance)
    bias_text = str(bias or "Neutral").strip().lower()
    phase_text = str(session_phase or "").strip()

    if material_breach_confirmed:
        score += 30.0
    elif structural_state in {"STABLE"}:
        score += 6.0

    if (
        spot_value is not None
        and support_value is not None
        and resistance_value is not None
        and resistance_value > support_value
    ):
        band_width = max(1.0, resistance_value - support_value)
        relative_pos = (spot_value - support_value) / band_width
        dist_support = abs(spot_value - support_value)
        dist_resistance = abs(resistance_value - spot_value)
        near_threshold = band_width * 0.15

        if dist_support <= near_threshold and bias_text in {"bullish", "neutral"}:
            score += 15.0
        if dist_resistance <= near_threshold and bias_text in {"bearish", "neutral"}:
            score += 15.0
        if material_breach_confirmed and (spot_value > resistance_value or spot_value < support_value):
            score += 12.0
        if bias_text == "bullish" and 0.65 <= relative_pos <= 0.90:
            score += 8.0
        if bias_text == "bearish" and 0.10 <= relative_pos <= 0.35:
            score += 8.0
        if 0.40 <= relative_pos <= 0.60:
            score -= 15.0
        if min(dist_support, dist_resistance) > 50.0 and not material_breach_confirmed:
            score -= 12.0
        if (spot_value > resistance_value + (band_width * 0.35)) or (spot_value < support_value - (band_width * 0.35)):
            score -= 10.0

    if phase_text == "Expansion Window":
        score += 10.0
    elif phase_text == "Position Build Phase":
        score += 8.0
    elif phase_text == "Structure Formation":
        score += 5.0
    elif phase_text == "Transition":
        score -= 8.0
    elif phase_text == "Compression Phase":
        score -= 10.0
    elif phase_text == "Opening Drive":
        score -= 12.0

    return _clamp_score_0_100(score)


def _score_readiness_risk_friction(
    *,
    trap_probability: float,
    support_transition_badge: bool,
    resistance_transition_badge: bool,
    blocking_reason: str,
    trap_type: str,
    absorption_wins: bool,
) -> float:
    trap_value = _clamp_score_0_100(trap_probability)
    score = 100.0

    if trap_value > 60.0:
        score -= (15.0 * 0.6) + ((trap_value - 60.0) * 1.0)
    elif trap_value > 45.0:
        score -= (trap_value - 45.0) * 0.6

    if support_transition_badge:
        score -= 18.0
    if resistance_transition_badge:
        score -= 18.0

    blocker = str(blocking_reason or "").strip().upper()
    if blocker == "ABSORPTION_ACTIVE":
        score -= 20.0
    elif blocker == "NO_BREAK_CONFIRMATION":
        score -= 15.0
    elif blocker == "RANGE_CONFLICT":
        score -= 12.0
    elif blocker == "LOW_READINESS":
        score -= 10.0

    trap_type_text = str(trap_type or "").lower()
    if "failure" in trap_type_text:
        score -= 10.0
    if "rejection" in trap_type_text:
        score -= 15.0

    score = _clamp_score_0_100(score)
    if absorption_wins:
        score = max(35.0, score)
    return score


def _readiness_v2_state(score: float) -> str:
    value = float(score or 0.0)
    if value >= 75.0:
        return "High"
    if value >= 58.0:
        return "Moderate"
    if value >= 42.0:
        return "Low"
    return "Not Ready"


def _compute_readiness_v2(
    *,
    previous_state: dict[str, Any] | None,
    committed_regime: str,
    stabilized_regime_family: str | None,
    range_locked: bool,
    regime_hold_cycles: int,
    candidate_regime_count: int,
    support_transition_badge: bool,
    resistance_transition_badge: bool,
    support_shift_cycle: int,
    structural_state: str,
    material_breach_confirmed: bool,
    confirmation_type: str,
    no_edge: bool,
    spot: float | None,
    support_level: float | None,
    resistance_level: float | None,
    bias: str,
    session_phase: str,
    breakout_probability_up: float,
    breakout_probability_down: float,
    support_zone_pressure: float,
    resistance_zone_pressure: float,
    trap_probability: float,
    trap_type: str,
    blocking_reason: str,
    winning_engine: str,
    conflict_market_state: str,
    absorption_wins: bool,
    oi_scenario: str = "",
    session_range_pct: float = 0.0,
) -> dict[str, Any]:
    prev_support = _safe_float((previous_state or {}).get("current_support"))
    prev_resistance = _safe_float((previous_state or {}).get("current_resistance"))
    prev_trade_readiness_v2 = _safe_float(
        (previous_state or {}).get("trade_readiness_v2")
        if _safe_float((previous_state or {}).get("trade_readiness_v2")) is not None
        else (previous_state or {}).get("trade_readiness")
    )
    prev_structure_quality = _safe_float((previous_state or {}).get("readiness_structure_quality"))
    prev_directional_alignment = _safe_float((previous_state or {}).get("readiness_directional_alignment"))
    prev_execution_quality = _safe_float((previous_state or {}).get("readiness_execution_quality"))
    prev_risk_friction = _safe_float((previous_state or {}).get("readiness_risk_friction"))
    support_now = _safe_float(support_level)
    resistance_now = _safe_float(resistance_level)
    support_unchanged = (
        support_now is not None and prev_support is not None and abs(support_now - prev_support) < 1e-6
    )
    resistance_unchanged = (
        resistance_now is not None and prev_resistance is not None and abs(resistance_now - prev_resistance) < 1e-6
    )

    readiness_range_like_session = _is_readiness_range_like_session(
        committed_regime=committed_regime,
        stabilized_regime_family=stabilized_regime_family,
        range_locked=bool(range_locked),
        no_edge=bool(no_edge),
    )
    invalid_sr_geometry = _is_invalid_readiness_sr_geometry(
        support=support_level,
        resistance=resistance_level,
    )
    previous_structural_state = str(
        (previous_state or {}).get("structural_state")
        or (previous_state or {}).get("structural_state_marker")
        or ""
    ).strip().upper()

    structure_quality = _score_readiness_structure_quality(
        committed_regime=committed_regime,
        regime_hold_cycles=int(regime_hold_cycles or 0),
        support_transition_badge=bool(support_transition_badge),
        resistance_transition_badge=bool(resistance_transition_badge),
        support_shift_cycle=int(support_shift_cycle or 0),
        candidate_regime_count=int(candidate_regime_count or 0),
        structural_state=structural_state,
        material_breach_confirmed=bool(material_breach_confirmed),
        support_unchanged=support_unchanged,
        resistance_unchanged=resistance_unchanged,
    )
    directional_alignment = _score_readiness_directional_alignment(
        bias=bias,
        breakout_probability_up=breakout_probability_up,
        breakout_probability_down=breakout_probability_down,
        support_zone_pressure=support_zone_pressure,
        resistance_zone_pressure=resistance_zone_pressure,
        winning_engine=winning_engine,
        conflict_market_state=conflict_market_state,
    )
    execution_quality = _score_readiness_execution_quality(
        spot=spot,
        support=support_level,
        resistance=resistance_level,
        bias=bias,
        session_phase=session_phase,
        structural_state=structural_state,
        material_breach_confirmed=material_breach_confirmed,
    )
    risk_friction = _score_readiness_risk_friction(
        trap_probability=trap_probability,
        support_transition_badge=support_transition_badge,
        resistance_transition_badge=resistance_transition_badge,
        blocking_reason=blocking_reason,
        trap_type=trap_type,
        absorption_wins=absorption_wins,
    )

    if invalid_sr_geometry:
        structure_quality = min(
            structure_quality,
            20.0 if (support_transition_badge or resistance_transition_badge) else 30.0,
        )
        execution_quality = min(execution_quality, 18.0)

    readiness_smoothing_applied = False
    if not material_breach_confirmed:
        structure_quality, structure_smoothed = _smooth_readiness_value(
            structure_quality,
            prev_structure_quality,
            alpha=READINESS_V2_PILLAR_ALPHA,
            deadband=READINESS_V2_DEADBAND,
            up_max_step=READINESS_V2_PILLAR_UP_STEP,
            down_max_step=READINESS_V2_PILLAR_DOWN_STEP,
        )
        directional_alignment, alignment_smoothed = _smooth_readiness_value(
            directional_alignment,
            prev_directional_alignment,
            alpha=READINESS_V2_PILLAR_ALPHA,
            deadband=READINESS_V2_DEADBAND,
            up_max_step=READINESS_V2_PILLAR_UP_STEP,
            down_max_step=READINESS_V2_PILLAR_DOWN_STEP,
        )
        execution_quality, execution_smoothed = _smooth_readiness_value(
            execution_quality,
            prev_execution_quality,
            alpha=READINESS_V2_PILLAR_ALPHA,
            deadband=READINESS_V2_DEADBAND,
            up_max_step=READINESS_V2_PILLAR_UP_STEP,
            down_max_step=READINESS_V2_PILLAR_DOWN_STEP,
        )
        risk_friction, friction_smoothed = _smooth_readiness_value(
            risk_friction,
            prev_risk_friction,
            alpha=READINESS_V2_PILLAR_ALPHA,
            deadband=READINESS_V2_DEADBAND,
            up_max_step=READINESS_V2_PILLAR_UP_STEP,
            down_max_step=READINESS_V2_PILLAR_DOWN_STEP,
        )
        readiness_smoothing_applied = any(
            [structure_smoothed, alignment_smoothed, execution_smoothed, friction_smoothed]
        )

    raw_score = (
        (structure_quality * 0.30)
        + (directional_alignment * 0.30)
        + (execution_quality * 0.25)
        + (risk_friction * 0.15)
    )
    final_score = _clamp_score_0_100(raw_score)
    raw_score_before_caps = final_score
    cap_reason = None
    floor_reason = None

    # Caps
    if support_transition_badge or resistance_transition_badge:
        if final_score > 62.0:
            final_score = 62.0
            cap_reason = "TRANSITION_CAP"
    if str(blocking_reason or "").upper() == "NO_BREAK_CONFIRMATION":
        if final_score > 59.0:
            final_score = 59.0
            cap_reason = "NO_BREACH_CONFIRMATION_CAP"
    if float(trap_probability or 0.0) >= 72.0 and not material_breach_confirmed:
        if final_score > 52.0:
            final_score = 52.0
            cap_reason = "HIGH_TRAP_NO_BREACH_CAP"

    spot_value = _safe_float(spot)
    support_value = _safe_float(support_level)
    resistance_value = _safe_float(resistance_level)
    if (
        readiness_range_like_session
        and spot_value is not None
        and support_value is not None
        and resistance_value is not None
        and resistance_value > support_value
    ):
        relative_pos = (spot_value - support_value) / max(1.0, resistance_value - support_value)
        if 0.40 <= relative_pos <= 0.60:
            if final_score > 48.0:
                final_score = 48.0
                cap_reason = "RANGE_DAY_MID_BAND_CAP"

    if no_edge and final_score > 52.0:
        final_score = 52.0
        cap_reason = "NO_EDGE_CAP"

    # Floors
    if material_breach_confirmed and confirmation_type in {"support_abandonment", "resistance_abandonment"}:
        if final_score < 68.0:
            final_score = 68.0
            floor_reason = "CONFIRMED_BREACH_FLOOR"
    if material_breach_confirmed and float(trap_probability or 0.0) < 55.0:
        if final_score < 72.0:
            final_score = 72.0
            floor_reason = "CONFIRMED_EXPANSION_LOW_TRAP_FLOOR"

    final_score = _clamp_score_0_100(final_score)
    if invalid_sr_geometry and final_score > 38.0:
        final_score = 38.0
        cap_reason = "INVALID_SR_GEOMETRY_CAP"

    readiness_transition_guard_applied = False
    if (
        readiness_range_like_session
        and str(structural_state or "").strip().upper() == "TRANSITION"
        and previous_structural_state not in {"TRANSITION", "ABSORPTION", "TRAP_RISK"}
        and prev_trade_readiness_v2 is not None
        and not material_breach_confirmed
    ):
        transition_floor = max(
            READINESS_TRANSITION_FLAP_FLOOR,
            float(prev_trade_readiness_v2) - READINESS_TRANSITION_FLAP_MAX_DROP,
        )
        if final_score < transition_floor:
            final_score = transition_floor
            cap_reason = "TRANSITION_FLAP_GUARD"
            readiness_transition_guard_applied = True

    if not material_breach_confirmed:
        final_score, final_smoothed = _smooth_readiness_value(
            final_score,
            prev_trade_readiness_v2,
            alpha=READINESS_V2_FINAL_ALPHA,
            deadband=READINESS_V2_DEADBAND,
            up_max_step=READINESS_V2_FINAL_UP_STEP,
            down_max_step=READINESS_V2_FINAL_DOWN_STEP,
        )
        readiness_smoothing_applied = readiness_smoothing_applied or final_smoothed

    readiness_state_v2 = _readiness_v2_state(final_score)
    effective_threshold = READINESS_ACTIVE_ON_THRESHOLD
    oi_scenario_text = str(oi_scenario or "").strip().upper()
    session_range_value = float(session_range_pct or 0.0)
    if oi_scenario_text == "PINNING" and session_range_value > 1.5:
        effective_threshold = 58.0
    elif oi_scenario_text == "PINNING" and session_range_value > 1.0:
        effective_threshold = 60.0
    prev_active_v2 = bool((previous_state or {}).get("readiness_active_v2", False))
    if not prev_active_v2 and final_score >= effective_threshold:
        readiness_active_v2 = True
    elif prev_active_v2 and final_score < READINESS_ACTIVE_OFF_THRESHOLD:
        readiness_active_v2 = False
    else:
        readiness_active_v2 = prev_active_v2

    return {
        "trade_readiness_v2": round(final_score, 2),
        "readiness_state_v2": readiness_state_v2,
        "readiness_active_v2": readiness_active_v2,
        "readiness_structure_quality": round(structure_quality, 2),
        "readiness_directional_alignment": round(directional_alignment, 2),
        "readiness_execution_quality": round(execution_quality, 2),
        "readiness_risk_friction": round(risk_friction, 2),
        "readiness_cap_reason": cap_reason,
        "readiness_floor_reason": floor_reason,
        "readiness_regime_used": str(committed_regime or ""),
        "readiness_regime_family_used": (
            str(stabilized_regime_family or "").strip().upper()
            or _regime_family(committed_regime)
        ),
        "readiness_range_like_session": readiness_range_like_session,
        "readiness_raw_score_v2": round(raw_score_before_caps, 2),
        "readiness_invalid_sr_geometry": bool(invalid_sr_geometry),
        "readiness_smoothing_applied": bool(readiness_smoothing_applied),
        "readiness_transition_guard_applied": bool(readiness_transition_guard_applied),
        "readiness_active_on_threshold_effective": round(float(effective_threshold), 2),
    }


def _derive_resolved_reason(
    *,
    trade_action: str,
    blocking_reason: str,
    material_breach: dict[str, Any] | None,
    support_absorption: dict[str, Any] | None,
    pressure_state: str | None,
    summary_line: str,
) -> str:
    breach = material_breach or {}
    absorption = support_absorption or {}
    if bool(breach.get("material_breach_confirmed")) and bool(breach.get("resistance_broken")):
        return "Breakout confirmed"
    if bool(breach.get("material_breach_confirmed")) and bool(breach.get("support_broken")):
        return "Breakdown confirmed"
    if blocking_reason == "ABSORPTION_ACTIVE" or bool(absorption.get("absorption_detected")):
        return "Support absorption active"
    if blocking_reason in {"SUPPORT_TRANSITION", "RESISTANCE_TRANSITION"}:
        return "Level transition active"
    if blocking_reason == "NO_BREAK_CONFIRMATION":
        return "Breakout not confirmed"
    if blocking_reason == "TRAP_HIGH":
        return "Trap risk elevated"
    if blocking_reason == "RANGE_CONFLICT":
        return "Range conflict"
    if blocking_reason == "LONG_BIAS_GUARD":
        return "Promotion guard active"
    if blocking_reason == "LOW_READINESS":
        return "Readiness below threshold"
    if str(trade_action or "").upper() == "LONG BIAS":
        return "Upside pressure building"
    if str(trade_action or "").upper() == "SHORT BIAS":
        return "Downside pressure building"
    if str(trade_action or "").upper() == "BREAKOUT WATCH":
        return "Upside expansion watch"
    if str(trade_action or "").upper() == "BREAKDOWN WATCH":
        return "Downside expansion watch"
    if str(pressure_state or "").strip():
        return str(pressure_state)
    return summary_line or "Waiting for cleaner move"


def _determine_blocking_reason(
    *,
    trade_action: str,
    readiness_active: bool,
    trade_readiness: float,
    trap_probability: float,
    absorption_detected: bool,
    absorption_wins: bool,
    material_breach: dict[str, Any] | None,
    conflict_market_state: str | None,
    support_transition_badge: bool,
    resistance_transition_badge: bool,
    dps_adjusted: float,
) -> str:
    action_text = str(trade_action or "WAIT").upper()
    breach = material_breach or {}
    if support_transition_badge:
        return "SUPPORT_TRANSITION"
    if resistance_transition_badge:
        return "RESISTANCE_TRANSITION"
    if absorption_wins or (absorption_detected and action_text == "WAIT"):
        return "ABSORPTION_ACTIVE"
    if action_text == "WAIT" and (
        (bool(breach.get("support_broken")) or bool(breach.get("resistance_broken")))
        and not bool(breach.get("material_breach_confirmed"))
    ):
        return "NO_BREAK_CONFIRMATION"
    if action_text == "WAIT" and float(trap_probability or 0.0) >= 70.0:
        return "TRAP_HIGH"
    if str(conflict_market_state or "").strip().lower() in {"compression", "range conflict", "balanced"} and action_text == "WAIT":
        return "RANGE_CONFLICT"
    if action_text == "WAIT" and readiness_active and abs(float(dps_adjusted or 0.0)) > 0.35:
        return "LONG_BIAS_GUARD"
    if action_text == "WAIT" and float(trade_readiness or 0.0) < 57.0:
        return "LOW_READINESS"
    return "NONE"


def _determine_winning_engine(
    *,
    trade_action: str,
    blocking_reason: str,
    material_breach: dict[str, Any] | None,
    absorption_wins: bool,
) -> str:
    breach = material_breach or {}
    if blocking_reason == "TRAP_HIGH":
        return "trap_engine"
    if absorption_wins or blocking_reason == "ABSORPTION_ACTIVE":
        return "absorption_detector"
    if bool(breach.get("material_breach_confirmed")) or blocking_reason == "NO_BREAK_CONFIRMATION":
        return "material_breach_engine"
    if blocking_reason in {"SUPPORT_TRANSITION", "RESISTANCE_TRANSITION"}:
        return "sr_transition_guard"
    if blocking_reason == "LONG_BIAS_GUARD":
        return "promotion_guard"
    if blocking_reason == "LOW_READINESS":
        return "readiness_gate"
    if str(trade_action or "").upper() in {"BREAKOUT WATCH", "BREAKDOWN WATCH"}:
        return "material_breach_engine"
    return "none"


def _compute_decision_confidence(
    *,
    trade_readiness: float,
    trap_probability: float,
    trade_action: str,
    blocking_reason: str,
    support_transition_badge: bool,
    resistance_transition_badge: bool,
    material_breach_confirmed: bool,
) -> int:
    confidence = float(trade_readiness or 0.0)
    confidence -= min(18.0, max(0.0, float(trap_probability or 0.0) - 55.0) * 0.35)
    if support_transition_badge or resistance_transition_badge:
        confidence -= 12.0
    if str(trade_action or "").upper() == "WAIT":
        confidence -= 8.0
    if blocking_reason in {"NO_BREAK_CONFIRMATION", "RANGE_CONFLICT", "LONG_BIAS_GUARD", "ABSORPTION_ACTIVE"}:
        confidence -= 6.0
    if blocking_reason == "TRAP_HIGH":
        confidence -= 10.0
    if material_breach_confirmed:
        confidence += 8.0
    return int(round(max(0.0, min(100.0, confidence))))


def _update_signal_history(
    previous_state: dict[str, Any] | None,
    *,
    timestamp: str,
    trade_action: str,
    resolved_reason: str,
    blocking_reason: str,
    winning_engine: str,
    decision_confidence: int,
) -> list[dict[str, Any]]:
    history_raw = (previous_state or {}).get("signal_history", [])
    history: list[dict[str, Any]] = [item for item in history_raw if isinstance(item, dict)][-10:]
    next_item = {
        "timestamp": timestamp,
        "trade_action": str(trade_action or "WAIT"),
        "resolved_reason": str(resolved_reason or ""),
        "blocking_reason": str(blocking_reason or "NONE"),
        "winning_engine": str(winning_engine or "none"),
        "decision_confidence": int(decision_confidence),
    }
    if history:
        last = history[-1]
        if (
            str(last.get("trade_action") or "") == next_item["trade_action"]
            and str(last.get("resolved_reason") or "") == next_item["resolved_reason"]
            and str(last.get("blocking_reason") or "") == next_item["blocking_reason"]
        ):
            return history
    return (history + [next_item])[-10:]


def _apply_momentum_override(
    *,
    trade_action: str,
    spot: float | None,
    open_price: float | None,
    day_high: float | None,
    day_low: float | None,
    support: float | None,
    resistance: float | None,
    directional_force: dict[str, Any],
    clarity: float,
    volume_expansion_score: float,
    alignment_score: float,
    breakout_candidate: bool,
    material_breach: dict[str, Any] | None,
) -> dict[str, Any]:
    current_action = str(trade_action or "WAIT")
    spot_value = _safe_float(spot)
    open_value = _safe_float(open_price)
    high_value = _safe_float(day_high)
    low_value = _safe_float(day_low)
    support_value = _safe_float(support)
    resistance_value = _safe_float(resistance)
    if (
        current_action != "WAIT"
        or spot_value is None
        or open_value in (None, 0)
        or high_value is None
        or low_value is None
        or high_value <= low_value
    ):
        return {
            "trade_action": current_action,
            "momentum_score": 0.0,
            "momentum_override_explanation": None,
        }

    price_displacement = abs(spot_value - open_value) / open_value
    range_position = max(0.0, min(1.0, (spot_value - low_value) / max(high_value - low_value, 1e-9)))
    directional_strength = max(
        0.0,
        min(1.0, float((directional_force or {}).get("strength", 0.0) or 0.0) / 100.0),
    )
    momentum_score = (price_displacement * 0.4) + (directional_strength * 0.3) + (range_position * 0.3)
    momentum_score = max(0.0, min(1.0, momentum_score))

    override_action = current_action
    explanation = None
    momentum_strong = momentum_score > 0.60
    structural_confirmations = sum(
        [
            bool(breakout_candidate),
            float(volume_expansion_score or 0.0) > 0.5,
            float(alignment_score or 0.0) > 0.6,
            bool((material_breach or {}).get("support_broken") or (material_breach or {}).get("resistance_broken")),
        ]
    )
    if current_action == "WAIT" and momentum_strong and structural_confirmations >= 2 and float(clarity or 0.0) > 60.0:
        override_action = "BREAKOUT WATCH"
        explanation = "Momentum is building with structural confirmation. Breakout watch is active."

    return {
        "trade_action": override_action,
        "momentum_score": round(momentum_score, 4),
        "momentum_override_explanation": explanation,
    }


def _apply_mss_bias_conflict(*, market_structure_score: float, bias: str, state: str, conflict_flags: list[str] | None = None) -> dict[str, Any]:
    score = float(market_structure_score or 0.0)
    bias_text = str(bias or "Neutral")
    flags = list(conflict_flags or [])

    if score <= 3.0:
        structure_bias = "Bearish"
    elif score >= 7.0:
        structure_bias = "Bullish"
    else:
        structure_bias = "Mixed"

    transition_phase = (
        (score <= 3.0 and bias_text == "Bullish")
        or (score >= 7.0 and bias_text == "Bearish")
    )

    if transition_phase:
        resolved_state = "Transition Phase"
    elif 4.0 <= score <= 6.0:
        resolved_state = "Balanced Structure"
    else:
        resolved_state = str(state or "Balanced Structure")
    if transition_phase and "mss_bias_transition_phase" not in flags:
        flags.append("mss_bias_transition_phase")

    logger.debug(
        "MSSConflict[mss=%.2f bias=%s structure_bias=%s transition=%s state=%s]",
        score,
        bias_text,
        structure_bias,
        transition_phase,
        resolved_state,
    )

    return {
        "state": resolved_state,
        "structure_bias": structure_bias,
        "conflict_flags": flags,
        "transition_phase": transition_phase,
    }


def _map_regime_zone(state: str) -> str:
    """
    Collapse regime states into three actionable zones.
    """
    text = str(state or "").strip().lower()
    if "standby" in text or "range play" in text or "range day" in text:
        return "WAIT_ZONE"
    if "balanced" in text:
        return "WATCH_ZONE"
    if "transition" in text or "trend" in text or "breakdown" in text:
        return "TREND_ZONE"
    return "WATCH_ZONE"


def _regime_family(regime: str | None) -> str:
    text = str(regime or "").strip()
    if not text:
        return "RANGE"
    return REGIME_FAMILY_MAP.get(text, "RANGE")


def _canonicalize_regime_label(regime: str | None) -> str:
    text = str(regime or "").strip()
    if _regime_family(text) == "RANGE":
        return RANGE_REGIME_CANONICAL_LABEL
    return text or RANGE_REGIME_CANONICAL_LABEL


def _is_non_committable_regime(regime: str | None) -> bool:
    return str(regime or "").strip() in NON_COMMITTABLE_REGIMES


def _is_range_like_session(
    committed_regime: str | None,
    stabilized_regime_family: str | None,
    range_locked: bool,
    no_edge: bool,
) -> bool:
    return (
        str(stabilized_regime_family or "").strip().upper() == "RANGE"
        or _regime_family(committed_regime) == "RANGE"
        or bool(range_locked)
        or bool(no_edge)
    )


def _derive_committed_regime_label(*, state: str, engine_regime: str) -> str:
    text = str(state or "").strip().lower()
    if "breakdown" in text:
        return "Breakdown Day"
    if "trend" in text:
        return "Trend Day"
    if "transition" in text:
        return "Transition"
    if "balanced" in text:
        return "Balanced Structure"
    if "standby" in text or "range play" in text or "range day" in text:
        return "Range Day"
    return str(engine_regime or "Range Day")


def _readiness_regime_state(*, committed_regime: str, backend_state: str) -> str:
    text = str(committed_regime or "").strip().lower()
    if "range" in text:
        return "Standby"
    if "balanced" in text:
        return "Balanced Structure"
    if "transition" in text:
        return "Transition Phase"
    return str(backend_state or "")


def _is_range_lock_condition(
    trap_probability: float,
    trade_readiness: float,
    breach_confirmed: bool,
    structural_state: str | None,
) -> bool:
    return (
        float(trap_probability or 0.0) >= RANGE_LOCK_TRAP_MIN
        and float(trade_readiness or 0.0) <= RANGE_LOCK_READINESS_MAX
        and not bool(breach_confirmed)
        and str(structural_state or "").strip().upper() not in {"TRANSITION", "ABSORPTION", "TRAP_RISK"}
    )


def _is_no_edge_condition(
    trap_probability: float,
    trade_readiness: float,
    pressure_state: str | None,
    breach_confirmed: bool,
    structural_state: str | None,
) -> bool:
    pressure_text = str(pressure_state or "").strip().lower()
    return (
        abs(float(trade_readiness or 0.0) - NO_EDGE_READINESS_CENTER) <= NO_EDGE_READINESS_BAND
        and float(trap_probability or 0.0) >= NO_EDGE_TRAP_MIN
        and "balanced" in pressure_text
        and not bool(breach_confirmed)
        and str(structural_state or "").strip().upper() not in {"TRANSITION", "ABSORPTION", "TRAP_RISK"}
    )


def _apply_range_lock_and_no_edge(
    raw_candidate_regime: str | None,
    structural_state: str | None,
    trap_probability: float,
    trade_readiness: float,
    breach_confirmed: bool,
    pressure_state: str | None,
    current_regime: str | None,
) -> dict[str, Any]:
    structural_text = str(structural_state or "").strip().upper()
    if structural_text in {"TRANSITION", "ABSORPTION", "TRAP_RISK"}:
        return {
            "candidate_regime": str(raw_candidate_regime or "Range Play"),
            "range_locked": False,
            "no_edge": False,
            "market_state": None,
        }

    range_locked = _is_range_lock_condition(
        trap_probability=trap_probability,
        trade_readiness=trade_readiness,
        breach_confirmed=breach_confirmed,
        structural_state=structural_state,
    )
    no_edge = _is_no_edge_condition(
        trap_probability=trap_probability,
        trade_readiness=trade_readiness,
        pressure_state=pressure_state,
        breach_confirmed=breach_confirmed,
        structural_state=structural_state,
    )
    current_text = str(current_regime or "").strip()
    current_family = _regime_family(current_text)
    preferred_range_regime = current_text if current_family == "RANGE" else "Range Play"

    if no_edge:
        return {
            "candidate_regime": preferred_range_regime,
            "range_locked": True,
            "no_edge": True,
            "market_state": "NO_EDGE",
        }

    if range_locked:
        return {
            "candidate_regime": preferred_range_regime,
            "range_locked": True,
            "no_edge": False,
            "market_state": None,
        }

    return {
        "candidate_regime": str(raw_candidate_regime or "Range Play"),
        "range_locked": False,
        "no_edge": False,
        "market_state": None,
    }


def _derive_spc_structural_state(
    *,
    trap_probability: float,
    support_transition_active: bool,
    resistance_transition_active: bool,
    support_shift_cycle: int,
    absorption_detected: bool,
) -> str:
    if float(trap_probability or 0.0) >= 75.0:
        return "TRAP_RISK"
    if support_transition_active or resistance_transition_active or int(support_shift_cycle or 0) > 0:
        return "TRANSITION"
    if absorption_detected:
        return "ABSORPTION"
    return "STABLE"


def _apply_regime_stabilizer(
    raw_candidate_regime: str | None,
    current_regime: str | None,
    regime_hold_cycles: int,
    regime_candidate: str | None,
    regime_candidate_streak: int,
    structural_state: str | None,
) -> dict[str, Any]:
    raw_input_regime = str(raw_candidate_regime or "").strip()
    raw_regime = _canonicalize_regime_label(raw_candidate_regime or RANGE_REGIME_CANONICAL_LABEL)
    current_text = str(current_regime or "").strip()
    current_regime_text = _canonicalize_regime_label(current_text or raw_regime)
    raw_family = _regime_family(raw_regime)
    current_family = _regime_family(current_regime_text)
    structural_text = str(structural_state or "").strip().upper()
    hold_cycles = int(regime_hold_cycles or 0)
    candidate_text = str(regime_candidate or "").strip() or None
    candidate_streak = int(regime_candidate_streak or 0)

    if structural_text == "TRANSITION":
        return {
            "final_regime": "Transition Phase",
            "final_family": "TRANSITION",
            "regime_hold_cycles": 0,
            "regime_candidate": None,
            "regime_candidate_streak": 0,
        }

    if structural_text in {"ABSORPTION", "TRAP_RISK"}:
        return {
            "final_regime": current_regime_text,
            "final_family": current_family,
            "regime_hold_cycles": hold_cycles + 1,
            "regime_candidate": None,
            "regime_candidate_streak": 0,
        }

    if _is_non_committable_regime(raw_input_regime):
        return {
            "final_regime": current_regime_text,
            "final_family": current_family,
            "regime_hold_cycles": hold_cycles + 1,
            "regime_candidate": None,
            "regime_candidate_streak": 0,
        }

    if raw_family == current_family:
        return {
            "final_regime": current_regime_text,
            "final_family": current_family,
            "regime_hold_cycles": hold_cycles + 1,
            "regime_candidate": None,
            "regime_candidate_streak": 0,
        }

    if hold_cycles < REGIME_MIN_HOLD_CYCLES:
        next_streak = (candidate_streak + 1) if candidate_text == raw_regime else 1
        return {
            "final_regime": current_regime_text,
            "final_family": current_family,
            "regime_hold_cycles": hold_cycles + 1,
            "regime_candidate": raw_regime,
            "regime_candidate_streak": next_streak,
        }

    if candidate_text == raw_regime:
        candidate_streak += 1
    else:
        candidate_text = raw_regime
        candidate_streak = 1

    if candidate_streak >= REGIME_SWITCH_CONFIRM_CYCLES:
        return {
            "final_regime": raw_regime,
            "final_family": raw_family,
            "regime_hold_cycles": 0,
            "regime_candidate": None,
            "regime_candidate_streak": 0,
        }

    return {
        "final_regime": current_regime_text,
        "final_family": current_family,
        "regime_hold_cycles": hold_cycles + 1,
        "regime_candidate": candidate_text,
        "regime_candidate_streak": candidate_streak,
    }


def _apply_committed_regime_hysteresis(
    *,
    detected_regime: str,
    current_committed_regime: str | None,
    candidate_regime: str | None,
    candidate_regime_count: int,
    last_detected_regime: str | None,
) -> tuple[str, str, int]:
    detected = str(detected_regime or "")
    committed = str(current_committed_regime or "")
    candidate = str(candidate_regime or "")
    count = int(candidate_regime_count or 0)
    last_detected = str(last_detected_regime or "")

    if not committed:
        return detected, "", 0
    if _is_non_committable_regime(detected):
        return _canonicalize_regime_label(committed), "", 0
    if detected == committed:
        return committed, "", 0
    if detected != last_detected:
        return committed, "", 0
    if candidate and detected == candidate:
        count += 1
    else:
        candidate = detected
        count = 1
    if count >= 3:
        return detected, "", 0
    return committed, candidate, count


def _validate_response_consistency(
    *,
    rows: list[dict[str, Any]],
    support_level: float | None,
    resistance_level: float | None,
    stable_bias: str,
    market_structure_score: float,
    structural_state: str | None = None,
    market_state_label: str | None = None,
    conflict_market_state: str | None = None,
    trap_state: str | None = None,
    no_edge: bool = False,
    range_locked: bool = False,
) -> list[str]:
    warnings: list[str] = []

    def _find_row(strike_value: float | None) -> dict[str, Any] | None:
        if strike_value is None:
            return None
        for row in rows:
            strike = row.get("strike")
            if strike is None:
                continue
            try:
                if float(strike) == float(strike_value):
                    return row
            except (TypeError, ValueError):
                continue
        return None

    support_row = _find_row(support_level)
    resistance_row = _find_row(resistance_level)

    support_label = str((support_row or {}).get("strike_interpretation_label", "") or "")
    resistance_label = str((resistance_row or {}).get("strike_interpretation_label", "") or "")
    support_strength = str((support_row or {}).get("strike_interpretation_strength", "") or "")
    resistance_strength = str((resistance_row or {}).get("strike_interpretation_strength", "") or "")

    structural_state_normalized = str(structural_state or "").strip().upper()
    market_state_normalized = str(market_state_label or "").strip().upper()
    conflict_market_state_normalized = str(conflict_market_state or "").strip().upper()
    trap_state_normalized = str(trap_state or "").strip().upper()

    guarded_structure = structural_state_normalized in {"TRANSITION", "ABSORPTION", "TRAP_RISK"}
    guarded_no_edge = (
        bool(no_edge)
        or bool(range_locked)
        or market_state_normalized == "NO_EDGE"
        or conflict_market_state_normalized == "NO_EDGE"
    )
    guarded_trap = trap_state_normalized in {"TRAP_RISK", "STABLE_MID"}
    allow_dominance_checks = not (guarded_structure or guarded_no_edge or guarded_trap)

    if allow_dominance_checks and support_row and support_label == "CE Dominant" and support_strength in {"Medium", "High"}:
        warnings.append("Support strike dominance inconsistent")
    if allow_dominance_checks and resistance_row and resistance_label == "PE Dominant" and resistance_strength in {"Medium", "High"}:
        warnings.append("Resistance strike dominance inconsistent")

    if (market_structure_score <= 3.0 and stable_bias == "Bullish") or (
        market_structure_score >= 7.0 and stable_bias == "Bearish"
    ):
        warnings.append("Bias and MSS conflict detected")

    if warnings and "Signal conflict detected" not in warnings:
        warnings.insert(0, "Signal conflict detected")

    return warnings


def _detect_oi_imbalance_trap(
    *,
    rows: list[dict[str, Any]],
    support_level: float | None,
    resistance_level: float | None,
) -> dict[str, Any]:
    def _find_row(strike_value: float | None) -> dict[str, Any] | None:
        if strike_value is None:
            return None
        for row in rows:
            strike = row.get("strike")
            if strike is None:
                continue
            try:
                if float(strike) == float(strike_value):
                    return row
            except (TypeError, ValueError):
                continue
        return None

    resistance_row = _find_row(resistance_level)
    support_row = _find_row(support_level)

    resistance_ce_change = float((resistance_row or {}).get("CE_OIChangePct", 0.0) or 0.0)
    resistance_pe_change = float((resistance_row or {}).get("PE_OIChangePct", 0.0) or 0.0)
    support_pe_change = float((support_row or {}).get("PE_OIChangePct", 0.0) or 0.0)
    support_ce_change = float((support_row or {}).get("CE_OIChangePct", 0.0) or 0.0)

    trap_probability = 0
    trap_reason = None
    support_strength = 0
    support_reason = None

    if resistance_row and resistance_ce_change > 15.0 and resistance_pe_change < 5.0:
        trap_probability = 80
        trap_reason = "Call writers defending resistance."

    if support_row and support_pe_change > 15.0 and support_ce_change < 5.0:
        support_strength = 80
        support_reason = "Put writers strengthening support."

    logger.debug(
        "OIImbalance[%s/%s] resistance_ce=%.2f resistance_pe=%.2f support_pe=%.2f support_ce=%.2f trap_probability=%s support_strength=%s",
        support_level,
        resistance_level,
        resistance_ce_change,
        resistance_pe_change,
        support_pe_change,
        support_ce_change,
        trap_probability,
        support_strength,
    )

    return {
        "trap_probability": int(trap_probability),
        "trap_reason": trap_reason,
        "support_strength": int(support_strength),
        "support_reason": support_reason,
        "resistance_strike": resistance_level,
        "support_strike": support_level,
    }

def _apply_signal_stability_layer(
    *,
    previous_state: dict[str, Any] | None,
    new_bias: str,
    new_projection: str,
    current_mss: float,
    directional_force: float,
    confidence: float,
    clarity: float,
) -> dict[str, Any]:
    prev = previous_state or {}
    previous_bias = str(prev.get("previous_bias") or prev.get("primary_bias") or new_bias)
    previous_projection = str(prev.get("previous_projection") or new_projection)
    previous_mss = float(prev.get("market_structure_score_prev", current_mss) or current_mss)
    previous_force = float(prev.get("force_strength", directional_force) or directional_force)
    previous_bias_counter = int(prev.get("bias_change_counter", 0) or 0)
    previous_projection_counter = int(prev.get("projection_change_counter", 0) or 0)
    previous_bias_cycles = int(prev.get("bias_stability_cycles", 0) or 0)

    if new_bias != previous_bias:
        bias_change_counter = previous_bias_counter + 1
    else:
        bias_change_counter = 0

    if new_projection != previous_projection:
        projection_change_counter = previous_projection_counter + 1
    else:
        projection_change_counter = 0

    stable_bias = new_bias if (new_bias == previous_bias or bias_change_counter >= 3) else previous_bias
    stable_projection = (
        new_projection
        if (new_projection == previous_projection or projection_change_counter >= 2)
        else previous_projection
    )

    # Noise freeze gate for low-conviction cycles.
    if confidence < 20 or clarity < 40:
        stable_bias = previous_bias
        stable_projection = previous_projection

    mss_smoothed = max(0.0, min(100.0, (0.7 * previous_mss) + (0.3 * current_mss)))

    if stable_bias == previous_bias and directional_force > previous_force:
        drift = "Strengthening"
    elif stable_bias == previous_bias and directional_force < previous_force:
        drift = "Weakening"
    else:
        drift = "Stable"

    bias_stability_cycles = previous_bias_cycles + 1 if stable_bias == previous_bias else 0

    return {
        "primary_bias": stable_bias,
        "projection": stable_projection,
        "market_structure_score": round(mss_smoothed, 2),
        "drift": drift,
        "bias_stability_cycles": int(bias_stability_cycles),
        "bias_change_counter": int(bias_change_counter),
        "projection_change_counter": int(projection_change_counter),
        "previous_bias": previous_bias,
        "previous_projection": previous_projection,
        "new_bias": new_bias,
        "new_projection": new_projection,
        "previous_mss": round(previous_mss, 2),
    }


def _trap_level_from_probability(probability: float) -> str:
    if probability > 65:
        return "High"
    if probability > 45:
        return "Moderate"
    return "Low"


def _atr_key(symbol: str, expiry: str | None) -> str:
    return f"{symbol.upper()}::{expiry or 'AUTO'}"


def _update_and_get_avg_atr(symbol: str, expiry: str | None, atr_value: float) -> float | None:
    key = _atr_key(symbol, expiry)
    if atr_value > 0:
        _atr_history[key].append(float(atr_value))

    series = _atr_history.get(key)
    if not series or len(series) < ATR_MIN_SAMPLES:
        return None
    return float(sum(series) / len(series))


async def _fetch_option_chain_async(symbol: str, expiry: str | None, instrument_type: str) -> dict[str, Any]:
    return await asyncio.to_thread(fetch_option_chain, symbol, expiry, instrument_type)


async def _fetch_contract_info_async(symbol: str) -> dict[str, Any]:
    return await asyncio.to_thread(fetch_option_chain_contract_info, symbol)


async def _fetch_index_data_async() -> dict[str, Any]:
    return await asyncio.to_thread(fetch_index_data)


def _parse_expiry_label(expiry: str) -> datetime | None:
    text = str(expiry or "").strip()
    if not text:
        return None
    for fmt in ("%d-%b-%Y", "%d %b %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=IST)
        except ValueError:
            continue
    return None


def _resolve_active_expiries(expiries: list[str]) -> list[str]:
    if not expiries:
        return []

    now_ist = datetime.now(IST)
    market_closed = now_ist.hour > 15 or (now_ist.hour == 15 and now_ist.minute >= 30)
    if not market_closed:
        return expiries

    parsed: list[tuple[str, datetime]] = []
    for item in expiries:
        dt = _parse_expiry_label(item)
        if dt is not None:
            parsed.append((item, dt))
    if not parsed:
        return expiries

    today = now_ist.date()
    parsed.sort(key=lambda item: item[1])
    today_expiry = next((label for label, dt in parsed if dt.date() == today), None)
    if not today_expiry:
        return expiries

    next_future = next((label for label, dt in parsed if dt.date() > today), None)
    if not next_future:
        return expiries

    # After close on expiry day, move active computation to next available expiry.
    return [item for item in expiries if item != today_expiry]


def _resolve_sr_anchor(previous_state: dict[str, Any] | None, side: str) -> tuple[float | None, str | None]:
    """
    Resolve the last known active structural anchor from persisted state.
    Prefer current active top-level fields, then support/resistance level,
    then nested immediate/major fields, then previous_* as last resort.
    """
    state = previous_state or {}
    levels = state.get("levels", {}) if isinstance(state.get("levels"), dict) else {}

    if side == "support":
        support_levels = levels.get("support", {}) if isinstance(levels.get("support"), dict) else {}
        candidates = [
            ("current_support", state.get("current_support")),
            ("support_level", state.get("support_level")),
            ("levels.support.immediate", support_levels.get("immediate")),
            ("levels.support.major", support_levels.get("major")),
            ("previous_support", state.get("previous_support")),
        ]
    else:
        resistance_levels = levels.get("resistance", {}) if isinstance(levels.get("resistance"), dict) else {}
        candidates = [
            ("current_resistance", state.get("current_resistance")),
            ("resistance_level", state.get("resistance_level")),
            ("levels.resistance.immediate", resistance_levels.get("immediate")),
            ("levels.resistance.major", resistance_levels.get("major")),
            ("previous_resistance", state.get("previous_resistance")),
        ]

    for source, raw in candidates:
        value = _safe_float(raw)
        if value is not None and value > 0:
            return value, source
    return None, None


def _apply_first_cycle_sr_buffer_guard(
    *,
    sr: dict[str, Any],
    spot: float | None,
    previous_state: dict[str, Any] | None,
    buffer_points: float = 25.0,
) -> dict[str, Any]:
    """
    Enforce restart/reset-safe structural buffers using persisted anchors.

    Support rule:
      Do not allow support demotion if spot is still above old_support - 25.

    Resistance rule:
      Do not allow upward resistance promotion if spot is still below old_resistance + 25.

    Zero/invalid spot: if spot is absent or clearly invalid (< 1000 for Indian indices),
    force SR levels back to previous anchors entirely — the SR engine output from a
    zero-spot tick is meaningless and would otherwise broadcast extreme guard defaults.

    This runs after SR engine selection, so even if the first OI read misses
    previous immediate state internally, downstream engines still receive guarded SR.
    """
    sr_out = dict(sr or {})
    support_obj = dict(sr_out.get("support") or {})
    resistance_obj = dict(sr_out.get("resistance") or {})

    spot_value = _safe_float(spot)

    # Hard guard: zero or implausibly small spot means the data tick is corrupt.
    # Restore previous anchors unconditionally and return early.
    if spot_value is None or spot_value < 1000:
        prev_sup, _ = _resolve_sr_anchor(previous_state, "support")
        prev_res, _ = _resolve_sr_anchor(previous_state, "resistance")
        if prev_sup and prev_sup > 0:
            support_obj["strike"] = prev_sup
            support_obj["immediate"] = prev_sup
            support_obj["major"] = prev_sup
        if prev_res and prev_res > 0:
            resistance_obj["strike"] = prev_res
            resistance_obj["immediate"] = prev_res
            resistance_obj["major"] = prev_res
        sr_out["support"] = support_obj
        sr_out["resistance"] = resistance_obj
        return {
            "sr": sr_out,
            "sr_cold_start_guard_applied": True,
            "sr_previous_support_anchor_used": prev_sup,
            "sr_previous_support_anchor_source": "zero_spot_guard",
            "sr_previous_resistance_anchor_used": prev_res,
            "sr_previous_resistance_anchor_source": "zero_spot_guard",
            "sr_support_buffer_blocked": True,
            "sr_resistance_buffer_blocked": True,
        }

    support_range = list(sr_out.get("support_range") or [])
    resistance_range = list(sr_out.get("resistance_range") or [])

    # spot_value already validated above (zero-spot early return). Recompute for
    # the remainder of the normal guard path (spot is valid and >= 1000 here).
    spot_value = _safe_float(spot)

    prev_support_anchor, prev_support_source = _resolve_sr_anchor(previous_state, "support")
    prev_resistance_anchor, prev_resistance_source = _resolve_sr_anchor(previous_state, "resistance")

    current_support_strike = _safe_float(support_obj.get("strike"))
    current_support_immediate = _safe_float(support_obj.get("immediate"))
    current_support_major = _safe_float(support_obj.get("major"))

    current_resistance_strike = _safe_float(resistance_obj.get("strike"))
    current_resistance_immediate = _safe_float(resistance_obj.get("immediate"))
    current_resistance_major = _safe_float(resistance_obj.get("major"))

    support_buffer_blocked = False
    resistance_buffer_blocked = False
    guard_applied = False

    if (
        spot_value is not None
        and prev_support_anchor is not None
        and (
            (current_support_strike is not None and current_support_strike < prev_support_anchor)
            or (current_support_immediate is not None and current_support_immediate < prev_support_anchor)
            or (current_support_major is not None and current_support_major < prev_support_anchor)
        )
        and spot_value > (prev_support_anchor - buffer_points)
    ):
        support_buffer_blocked = True
        guard_applied = True

        if current_support_strike is None or current_support_strike < prev_support_anchor:
            support_obj["strike"] = prev_support_anchor
        if current_support_immediate is None or current_support_immediate < prev_support_anchor:
            support_obj["immediate"] = prev_support_anchor
        if current_support_major is None or current_support_major < prev_support_anchor:
            support_obj["major"] = prev_support_anchor

        if support_range:
            guarded_range: list[Any] = []
            for item in support_range:
                value = _safe_float(item)
                if value is None:
                    guarded_range.append(item)
                else:
                    guarded_range.append(max(value, prev_support_anchor))
            sr_out["support_range"] = guarded_range

    if (
        spot_value is not None
        and prev_resistance_anchor is not None
        and (
            (current_resistance_strike is not None and current_resistance_strike > prev_resistance_anchor)
            or (current_resistance_immediate is not None and current_resistance_immediate > prev_resistance_anchor)
            or (current_resistance_major is not None and current_resistance_major > prev_resistance_anchor)
        )
        and spot_value < (prev_resistance_anchor + buffer_points)
    ):
        resistance_buffer_blocked = True
        guard_applied = True

        if current_resistance_strike is None or current_resistance_strike > prev_resistance_anchor:
            resistance_obj["strike"] = prev_resistance_anchor
        if current_resistance_immediate is None or current_resistance_immediate > prev_resistance_anchor:
            resistance_obj["immediate"] = prev_resistance_anchor
        if current_resistance_major is None or current_resistance_major > prev_resistance_anchor:
            resistance_obj["major"] = prev_resistance_anchor

        if resistance_range:
            guarded_range: list[Any] = []
            for item in resistance_range:
                value = _safe_float(item)
                if value is None:
                    guarded_range.append(item)
                else:
                    guarded_range.append(min(value, prev_resistance_anchor))
            sr_out["resistance_range"] = guarded_range

    sr_out["support"] = support_obj
    sr_out["resistance"] = resistance_obj

    return {
        "sr": sr_out,
        "sr_cold_start_guard_applied": guard_applied,
        "sr_previous_support_anchor_used": prev_support_anchor,
        "sr_previous_support_anchor_source": prev_support_source,
        "sr_previous_resistance_anchor_used": prev_resistance_anchor,
        "sr_previous_resistance_anchor_source": prev_resistance_source,
        "sr_support_buffer_blocked": support_buffer_blocked,
        "sr_resistance_buffer_blocked": resistance_buffer_blocked,
    }


def _run_ordered_pipeline(
    *,
    features: dict[str, Any],
    symbol: str,
    expiry: str | None,
    previous_score: float | None,
    last_10_scores: list[float] | None,
    previous_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Enforced execution order to avoid circular dependencies:
    preprocessing -> feature engines -> regime -> trap -> arbitration/decision -> trade plan.
    This helper runs the stages up to regime-adjusted feature outputs.
    """
    # Stage 1: Feature engines
    oi = run_oi_analysis(features, previous_state=previous_state)
    sr = run_sr_engine(features, previous_state=previous_state)
    liquidity_map_for_trap = build_liquidity_map(rows=features.get("rows") or [], spot=features.get("spot"))
    sr = _promote_exposed_resistance(
        sr=sr,
        spot=features.get("spot"),
        rows=features.get("rows") or [],
        liquidity_map=liquidity_map_for_trap,
        strike_gap=float(features.get("strike_gap", 50.0) or 50.0),
    )

    sr_guard = _apply_first_cycle_sr_buffer_guard(
        sr=sr,
        spot=features.get("spot"),
        previous_state=previous_state,
        buffer_points=25.0,
    )
    sr = sr_guard["sr"]

    base_volume = run_volume_analysis(features, previous_state=previous_state)
    base_breakout = run_breakout_engine(features, sr)
    base_trap = run_trap_engine(
        features,
        base_breakout,
        oi,
        base_volume,
        previous_state=previous_state,
        liquidity_map=liquidity_map_for_trap,
        prev_spot=_safe_float((previous_state or {}).get("spot")),
        prev_oi_total=_safe_float((previous_state or {}).get("total_chain_oi")),
        strike_gap=int(float(features.get("strike_gap", 50.0) or 50.0)),
    )
    base_material_breach = detect_material_breach(
        spot=features.get("spot"),
        support=sr.get("support", {}).get("strike"),
        resistance=sr.get("resistance", {}).get("strike"),
        rows=features.get("rows") or [],
        prev_support=_safe_float((previous_state or {}).get("support_level")),
        prev_resistance=_safe_float((previous_state or {}).get("resistance_level")),
    )

    # Stage 2: Regime from base features
    atr_threshold_for_regime = float(base_breakout.get("atr_threshold") or 0.0)
    avg_atr_for_regime = _update_and_get_avg_atr(symbol=symbol, expiry=expiry, atr_value=atr_threshold_for_regime)
    if not avg_atr_for_regime or avg_atr_for_regime <= 0:
        avg_atr_for_regime = float(features.get("atr_proxy") or 1.0)
    atr_ratio = atr_threshold_for_regime / max(1e-9, float(avg_atr_for_regime))
    regime = run_regime_engine(
        oi,
        base_volume,
        base_breakout,
        base_trap,
        context={
            "atr_ratio": atr_ratio,
            "score": float(previous_score or 0.0),
            "last_10_scores": list(last_10_scores or []),
            "breakout_confirmed": bool(base_breakout.get("breakout_up") or base_breakout.get("breakout_down")),
            "current_committed_regime": (previous_state or {}).get("committed_regime"),
            "candidate_regime": (previous_state or {}).get("candidate_regime"),
            "candidate_regime_count": (previous_state or {}).get("candidate_regime_count"),
        },
    )

    # Stage 3: Recompute sensitive engines with regime-adjusted thresholds
    pre_adjusted_thresholds = regime.get("adjusted_thresholds", {})
    volume_threshold = float(pre_adjusted_thresholds.get("volume_expansion_threshold", 1.2) or 1.2)
    breakout_atr_multiplier = float(pre_adjusted_thresholds.get("breakout_atr_multiplier", 1.2) or 1.2)

    volume = run_volume_analysis(features, expansion_threshold=volume_threshold, previous_state=previous_state)
    breakout = run_breakout_engine(features, sr, atr_multiplier=breakout_atr_multiplier)
    trap = run_trap_engine(
        features,
        breakout,
        oi,
        volume,
        previous_state=previous_state,
        liquidity_map=liquidity_map_for_trap,
        prev_spot=_safe_float((previous_state or {}).get("spot")),
        prev_oi_total=_safe_float((previous_state or {}).get("total_chain_oi")),
        strike_gap=int(float(features.get("strike_gap", 50.0) or 50.0)),
    )
    regime = run_regime_engine(
        oi,
        volume,
        breakout,
        trap,
        context={
            "atr_ratio": atr_ratio,
            "score": float(previous_score or 0.0),
            "last_10_scores": list(last_10_scores or []),
            "breakout_confirmed": bool(breakout.get("breakout_up") or breakout.get("breakout_down")),
            "current_committed_regime": (previous_state or {}).get("committed_regime"),
            "candidate_regime": (previous_state or {}).get("candidate_regime"),
            "candidate_regime_count": (previous_state or {}).get("candidate_regime_count"),
        },
    )

    return {
        "oi": oi,
        "sr": sr,
        "sr_guard": sr_guard,
        "volume": volume,
        "breakout": breakout,
        "trap": trap,
        "material_breach": base_material_breach,
        "regime": regime,
        "adjusted_thresholds": regime.get("adjusted_thresholds", pre_adjusted_thresholds),
    }


def _safe_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _build_per_strike_liquidity_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        strike = _safe_float(row.get("strike"))
        if strike is None:
            continue
        ce_oi = _safe_float(row.get("CE_OI")) or 0.0
        pe_oi = _safe_float(row.get("PE_OI")) or 0.0
        ce_vol = _safe_float(row.get("CE_Volume")) or 0.0
        pe_vol = _safe_float(row.get("PE_Volume")) or 0.0
        # parser emits change pct in percent units (e.g. -3.2); normalize to ratio (-0.032).
        ce_change = (_safe_float(row.get("CE_OIChangePct")) or 0.0) / 100.0
        pe_change = (_safe_float(row.get("PE_OIChangePct")) or 0.0) / 100.0
        liquidity_score = ce_oi + pe_oi + 0.2 * (ce_vol + pe_vol)
        normalized.append(
            {
                "strike": int(round(strike)),
                "oi_ce": ce_oi,
                "oi_pe": pe_oi,
                "vol_ce": ce_vol,
                "vol_pe": pe_vol,
                "oi_ce_change": ce_change,
                "oi_pe_change": pe_change,
                "liquidity_score": liquidity_score,
            }
        )
    return normalized


def _find_row_by_strike(
    rows: list[dict[str, Any]],
    strike_value: float | None,
) -> dict[str, Any] | None:
    if strike_value is None:
        return None
    for row in rows:
        strike = _safe_float(row.get("strike"))
        if strike is None:
            continue
        if abs(strike - float(strike_value)) < 1e-6:
            return row
    return None


def _promote_exposed_resistance(
    *,
    sr: dict[str, Any],
    spot: float | None,
    rows: list[dict[str, Any]],
    liquidity_map: dict[str, Any] | None,
    strike_gap: float,
) -> dict[str, Any]:
    result = dict(sr or {})
    resistance_obj = dict((result.get("resistance") or {}))
    spot_value = _safe_float(spot)
    resistance_value = _safe_float(resistance_obj.get("strike"))
    resistance_defense = _safe_float(resistance_obj.get("defense_score")) or 0.0
    call_wall = _safe_float((liquidity_map or {}).get("call_wall"))
    gap = max(1.0, float(strike_gap or 50.0))

    if (
        spot_value is not None
        and resistance_value is not None
        and call_wall is not None
        and call_wall > resistance_value
        and (call_wall - resistance_value) >= gap
        and spot_value > resistance_value
        and resistance_defense < 1.0
    ):
        promoted_row = _find_row_by_strike(rows, call_wall)
        if promoted_row is not None:
            ce_oi = _safe_float(promoted_row.get("CE_OI")) or 0.0
            pe_oi = _safe_float(promoted_row.get("PE_OI")) or 0.0
            resistance_obj["defense_score"] = round(ce_oi / max(pe_oi, 1.0), 2)
        resistance_obj["previous_immediate"] = resistance_value
        resistance_obj["strike"] = call_wall
        resistance_obj["immediate"] = call_wall
        resistance_obj["promoted_from_exposed_level"] = resistance_value
        resistance_obj["promotion_reason"] = "call_wall_promoted_after_exposed_resistance"

    result["resistance"] = resistance_obj
    return result


def detect_data_anomalies(
    *,
    spot: float | None,
    total_ce_oi: float,
    total_pe_oi: float,
    atm_ce_oi_change: float,
    atm_pe_oi_change: float,
    total_volume: float,
    previous_total_oi: float | None,
) -> dict[str, Any]:
    """
    Flag data quality issues before feeding into engines.
    Returns a dict with any detected anomalies and a boolean `has_anomaly`.
    """
    flags: list[str] = []
    total_oi = total_ce_oi + total_pe_oi

    # Zero-spot guard (already handled in SR guard, but flag it here too).
    if spot is None or (isinstance(spot, (int, float)) and float(spot) < 1000):
        flags.append("zero_or_invalid_spot")

    # Zero-volume cycle (market halt or data gap).
    if total_volume < 1.0:
        flags.append("zero_volume_cycle")

    # Zero total OI — extremely unlikely unless data feed is broken.
    if total_oi < 1.0:
        flags.append("zero_total_oi")

    # Single-cycle OI jump > 50% of previous total — likely a data error.
    if previous_total_oi and previous_total_oi > 1.0:
        oi_jump_pct = abs(total_oi - previous_total_oi) / previous_total_oi * 100.0
        if oi_jump_pct > 50.0:
            flags.append(f"large_oi_jump_{int(oi_jump_pct)}pct")

    # Single-strike ATM OI change that is implausibly large (> 200% of prior ATM total).
    atm_total = abs(atm_ce_oi_change) + abs(atm_pe_oi_change)
    if total_oi > 1.0 and atm_total / total_oi > 0.40:
        flags.append("abnormal_atm_oi_concentration")

    return {
        "has_anomaly": len(flags) > 0,
        "anomaly_flags": flags,
    }


def _count_level_touches(
    *,
    spot: float | None,
    level: float | None,
    strike_gap: float,
    previous_state: dict[str, Any] | None,
    touch_key: str,
) -> int:
    """
    Count how many cycles price has been within half a strike-gap of a structural level.
    Increments a persistent counter in previous_state[touch_key] each cycle a touch occurs,
    resets when level changes significantly (> 1.5× strike_gap from stored level).

    Returns the current touch count (0 if no touch this cycle).
    """
    prev = previous_state or {}
    stored_level = _safe_float(prev.get(f"{touch_key}_level"))
    stored_count = int(prev.get(touch_key, 0) or 0)

    if spot is None or level is None:
        return stored_count

    spot_f = float(spot)
    level_f = float(level)
    gap = max(1.0, float(strike_gap))
    proximity = abs(spot_f - level_f)

    # If the level moved significantly, reset counter.
    if stored_level is not None and abs(level_f - stored_level) > gap * 1.5:
        return 0

    # Increment if price is within half a strike-gap of the level.
    if proximity <= gap * 0.5:
        return stored_count + 1
    return stored_count


def _previous_trap_probability(previous_state: dict[str, Any] | None) -> float | None:
    state = previous_state or {}
    trap_hist = state.get("trap_probability_history", [])
    if isinstance(trap_hist, list):
        for item in reversed(trap_hist):
            value = _safe_float(item)
            if value is not None:
                return max(0.0, min(95.0, value))
    for key in ("trap_probability", "trap_risk", "expiry_risk"):
        value = _safe_float(state.get(key))
        if value is not None:
            return max(0.0, min(95.0, value))
    return None


def _trap_state_from_probability(probability: float) -> str:
    value = float(probability or 0.0)
    if TRAP_STABLE_MID_MIN <= value <= TRAP_STABLE_MID_MAX:
        return "STABLE_MID"
    return _trap_level_from_probability(value)


def _stabilize_trap_probability(
    *,
    new_trap_probability: float,
    previous_state: dict[str, Any] | None,
) -> dict[str, Any]:
    raw_new = max(0.0, min(95.0, float(new_trap_probability or 0.0)))
    prev_trap = _previous_trap_probability(previous_state)
    if prev_trap is None:
        smoothed = raw_new
        stabilized = raw_new
        hysteresis_applied = False
    else:
        smoothed = max(
            0.0,
            min(
                95.0,
                (TRAP_SMOOTH_PREV_WEIGHT * float(prev_trap))
                + (TRAP_SMOOTH_NEW_WEIGHT * raw_new),
            ),
        )
        if abs(raw_new - float(prev_trap)) < TRAP_HYSTERESIS_DEADBAND:
            stabilized = float(prev_trap)
            hysteresis_applied = True
        else:
            stabilized = smoothed
            hysteresis_applied = False
    return {
        "trap_probability": round(stabilized, 2),
        "trap_state": _trap_state_from_probability(stabilized),
        "prev_trap_probability": prev_trap,
        "smoothed_probability": round(smoothed, 2),
        "hysteresis_applied": hysteresis_applied,
    }


def _apply_stabilized_trap(trap: dict[str, Any], payload: dict[str, Any]) -> None:
    trap_probability = float(payload.get("trap_probability", 0.0) or 0.0)
    trap_state = str(payload.get("trap_state") or _trap_level_from_probability(trap_probability))
    trap["trap_probability_pct"] = int(round(trap_probability))
    trap["trap_probability"] = int(round(trap_probability))
    trap["trap_risk"] = int(round(trap_probability))
    trap["trap_state"] = trap_state
    trap["trap_level"] = "Moderate" if trap_state == "STABLE_MID" else _trap_level_from_probability(trap_probability)
    trap["trap_prev_probability"] = payload.get("prev_trap_probability")
    trap["trap_smoothed_probability"] = payload.get("smoothed_probability")
    trap["trap_hysteresis_applied"] = bool(payload.get("hysteresis_applied", False))


def _classify_day_trend(
    *,
    spot: float | None,
    previous_close: float | None,
    open_price: float | None,
) -> str:
    spot_value = _safe_float(spot)
    prev_close_value = _safe_float(previous_close)
    open_value = _safe_float(open_price)

    pct_vs_prev_close = (
        (spot_value - prev_close_value) / prev_close_value
        if spot_value is not None and prev_close_value not in (None, 0)
        else None
    )
    pct_from_open = (
        (spot_value - open_value) / open_value
        if spot_value is not None and open_value not in (None, 0)
        else None
    )
    composite_score = (0.6 * float(pct_vs_prev_close or 0.0)) + (0.4 * float(pct_from_open or 0.0))

    if composite_score >= 0.007:
        return "Bullish"
    if composite_score <= -0.007:
        return "Bearish"
    return "Neutral"


def _classify_long_trend(
    *,
    spot: float | None,
    previous_close: float | None,
    structure_bias: str | None,
) -> str:
    spot_value = _safe_float(spot)
    prev_close_value = _safe_float(previous_close)
    bias_text = str(structure_bias or "").strip().lower()

    if spot_value is not None and prev_close_value is not None:
        if spot_value > prev_close_value and bias_text.startswith("bullish"):
            return "Bullish"
        if spot_value < prev_close_value and bias_text.startswith("bearish"):
            return "Bearish"
    return "Neutral"


def check_sr_breach(spot: float | None, support: float | None, resistance: float | None) -> str | None:
    spot_value = _safe_float(spot)
    support_value = _safe_float(support)
    resistance_value = _safe_float(resistance)
    if spot_value is None:
        return None

    if resistance_value is not None:
        res_threshold = max(50.0, resistance_value * 0.002)
        if spot_value > resistance_value + res_threshold:
            return "resistance_breached"

    if support_value is not None:
        sup_threshold = max(50.0, support_value * 0.002)
        if spot_value < support_value - sup_threshold:
            return "support_breached"

    return None


def _compute_price_displacement_momentum(
    *,
    spot: float | None,
    open_price: float | None,
) -> dict[str, Any]:
    spot_value = _safe_float(spot)
    open_value = _safe_float(open_price)
    if spot_value is None or open_value in (None, 0):
        return {
            "displacement": 0.0,
            "displacement_pct": 0.0,
            "momentum_score": 0.0,
            "momentum_direction": "neutral",
        }

    displacement = float(spot_value - open_value)
    displacement_pct = abs(displacement) / float(open_value)
    momentum_score = min(1.0, displacement_pct / 0.01)
    momentum_direction = "bullish" if displacement > 0 else "bearish" if displacement < 0 else "neutral"
    return {
        "displacement": round(displacement, 2),
        "displacement_pct": round(displacement_pct, 6),
        "momentum_score": round(momentum_score, 4),
        "momentum_direction": momentum_direction,
    }


def _build_v2_intelligence(
    rows: list[dict[str, Any]],
    spot: float | None,
    symbol: str,
    expiry: str | None,
    timestamp: str | None,
    previous_close: float | None = None,
    open_price: float | None = None,
    day_high: float | None = None,
    day_low: float | None = None,
    previous_score: float | None = None,
    last_10_scores: list[float] | None = None,
    previous_regime: str | None = None,
    previous_alignment: float | None = None,
    previous_atr_ratio: float | None = None,
    previous_volume_ratio: float | None = None,
    previous_oi_delta: float | None = None,
    previous_state: dict[str, Any] | None = None,
    adaptive_state: dict[str, Any] | None = None,
    total_signals_logged: int = 0,
    engine_stats: dict[str, float] | None = None,
    evaluation_time: datetime | None = None,
) -> dict[str, Any]:
    session_eval_time = evaluation_time or _parse_timestamp_utc(timestamp)
    previous_state = _reset_state_for_new_session(
        previous_state,
        timestamp=session_eval_time,
    )
    normalized = normalize_chain(rows)
    features = build_feature_frame(
        normalized,
        spot=spot,
        symbol=symbol,
        expiry=expiry,
        timestamp=timestamp,
        previous_state=previous_state,
    )

    pipeline = _run_ordered_pipeline(
        features=features,
        symbol=symbol,
        expiry=expiry,
        previous_score=previous_score,
        last_10_scores=last_10_scores,
        previous_state=previous_state,
    )
    oi = pipeline["oi"]
    sr = pipeline["sr"]
    sr_guard = pipeline.get("sr_guard", {}) or {}
    volume = pipeline["volume"]
    breakout = pipeline["breakout"]
    trap = pipeline["trap"]
    material_breach = pipeline["material_breach"]
    regime = pipeline["regime"]
    adjusted_thresholds = pipeline["adjusted_thresholds"]
    price_momentum = _compute_price_displacement_momentum(
        spot=spot,
        open_price=open_price,
    )

    atr_threshold = float(breakout.get("atr_threshold") or 0.0)
    avg_atr = _update_and_get_avg_atr(symbol=symbol, expiry=expiry, atr_value=atr_threshold)
    if avg_atr is None or avg_atr <= 0:
        avg_atr = float(features.get("atr_proxy") or 1.0)
    current_atr_ratio = float(atr_threshold / max(1e-9, avg_atr))
    volatility_state = "Expanding" if current_atr_ratio > 1.2 else "Contracting" if current_atr_ratio < 0.8 else "Stable"

    oi_alignment = str(oi.get("alignment", "mixed"))
    oi_strength = max(0.0, min(1.0, float(oi.get("oi_strength", 0.0) or 0.0)))
    oi_score = float(oi.get("oi_bias", 0.0) or 0.0)
    oi_score = max(-1.0, min(1.0, oi_score))

    rvr_ce = max(0.0, min(1.0, float(volume.get("rvr", {}).get("ce", 0.0) or 0.0)))
    rvr_pe = max(0.0, min(1.0, float(volume.get("rvr", {}).get("pe", 0.0) or 0.0)))
    volume_score = max(-1.0, min(1.0, rvr_pe - rvr_ce))
    breakout_score = 1.0 if breakout.get("breakout_up") else -1.0 if breakout.get("breakout_down") else 0.0
    volume_expansion_score = max(
        0.0,
        min(
            1.0,
            float(
                volume.get(
                    "volume_expansion_score",
                    1.0 if bool(volume.get("volume_expansion")) else max(0.0, min(1.0, (rvr_ce + rvr_pe) / 2.0)),
                )
                or 0.0
            ),
        ),
    )
    previous_spot_raw = previous_state.get("spot") if isinstance(previous_state, dict) else None
    previous_spot = float(previous_spot_raw) if isinstance(previous_spot_raw, (int, float)) else None
    align = _compute_alignment_score(
        spot=spot,
        previous_spot=previous_spot,
        oi_shift_score=float(oi.get("oi_shift_score", oi_strength) or oi_strength),
        volume_expansion_score=float(volume_expansion_score),
    )
    alignment_score = float(align["alignment_score"])
    price_momentum_score = float(align["price_momentum"])
    breakout_strength_raw = _derive_breakout_strength(
        spot=spot,
        support=sr.get("support", {}).get("strike"),
        resistance=sr.get("resistance", {}).get("strike"),
        breakout=breakout,
    )
    if volume_expansion_score <= 0.4:
        breakout_strength_raw = 0.0
    breakout_strength_adjusted = max(0.0, min(1.0, breakout_strength_raw * alignment_score))
    breakout["breakout_strength_raw"] = round(float(breakout_strength_raw), 4)
    breakout["breakout_strength"] = round(float(breakout_strength_adjusted), 4)
    breakout_score = 0.0 if volume_expansion_score <= 0.4 else max(-1.0, min(1.0, breakout_score * alignment_score))

    support_score = float(sr.get("support", {}).get("score") or 0.0)
    resistance_score = float(sr.get("resistance", {}).get("score") or 0.0)
    support_zone_pressure = float(sr.get("support_zone_pressure", 0.0) or 0.0)
    resistance_zone_pressure = float(sr.get("resistance_zone_pressure", 0.0) or 0.0)
    support_zone_state = str(sr.get("support_zone_state", "Stable") or "Stable")
    resistance_zone_state = str(sr.get("resistance_zone_state", "Stable") or "Stable")
    sr_score = max(-1.0, min(1.0, (support_score - resistance_score) / 100.0))
    trap_raw = max(0.0, min(1.0, float(trap.get("trap_raw", 0.0) or 0.0)))
    trap_raw = max(0.0, min(1.0, trap_raw + ((1.0 - alignment_score) * 0.15)))
    trap["trap_raw"] = round(trap_raw, 4)
    trap_probability_pct = int(round(trap_raw * 100.0))
    trap["trap_probability_pct"] = trap_probability_pct
    trap["trap_probability"] = trap_probability_pct
    trap["trap_level"] = _trap_level_from_probability(trap_probability_pct)
    trap_penalty = max(0.0, min(1.0, float(trap_probability_pct) / 100.0))
    sr_breach_state = check_sr_breach(
        spot=spot,
        support=sr.get("support", {}).get("strike"),
        resistance=sr.get("resistance", {}).get("strike"),
    )
    breakout_candidate = False
    projection_override = None
    regime_hint = None

    if sr_breach_state == "resistance_breached":
        projection_override = "Resistance Broken — Monitoring"
        regime_hint = "Trend Day Candidate"
        sr_score = -abs(sr_score)
        breakout_strength_raw = max(0.0, min(1.0, breakout_strength_raw + 0.2))
        breakout_score = max(0.3, breakout_score)
        trap_penalty = max(0.0, trap_penalty * 0.75)
        regime["regime_type"] = "Trend Day Candidate"
        breakout["breakout_up"] = True
    elif sr_breach_state == "support_breached":
        projection_override = "Support Broken — Monitoring"
        regime_hint = "Breakdown Candidate"
        sr_score = -abs(sr_score)
        breakout_strength_raw = max(0.0, min(1.0, breakout_strength_raw + 0.2))
        breakout_score = min(-0.3, breakout_score) if breakout_score < 0 else -0.3
        trap_penalty = max(0.0, trap_penalty * 0.75)
        regime["regime_type"] = "Breakdown Candidate"
        breakout["breakout_down"] = True

    if bool(material_breach.get("material_breach_confirmed")) and str(material_breach.get("confirmation_type") or "") == "support_abandonment":
        projection_override = "Support Broken — Support Abandonment Confirmed"
    elif bool(material_breach.get("material_breach_confirmed")) and str(material_breach.get("confirmation_type") or "") == "bearish_positioning":
        projection_override = "Support Broken — Bearish Positioning Confirmed"

    # Zone-pressure integration:
    # - High support pressure increases breakdown potential.
    # - High resistance pressure increases breakout-up potential.
    if bool(breakout.get("breakout_down")) and support_zone_pressure > 60.0:
        breakout_strength_adjusted = max(0.0, min(1.0, breakout_strength_adjusted + 0.1))
        breakout["breakout_strength"] = round(float(breakout_strength_adjusted), 4)
    if bool(breakout.get("breakout_up")) and resistance_zone_pressure > 60.0:
        breakout_strength_adjusted = max(0.0, min(1.0, breakout_strength_adjusted + 0.1))
        breakout["breakout_strength"] = round(float(breakout_strength_adjusted), 4)

    directional_scores = [oi_score, volume_score, breakout_score, sr_score]
    mean_dir = sum(directional_scores) / max(1, len(directional_scores))
    dominant_sign = 1 if mean_dir > 0 else -1 if mean_dir < 0 else 0
    aligned = 0
    for s in directional_scores:
        sign_s = 1 if s > 0 else -1 if s < 0 else 0
        if dominant_sign != 0 and sign_s == dominant_sign:
            aligned += 1
    current_alignment = aligned / max(1, len(directional_scores))

    day_trend = _classify_day_trend(
        spot=spot,
        previous_close=previous_close,
        open_price=open_price,
    )

    confidence_proxy = max(
        0.0,
        min(
            100.0,
            (abs(mean_dir) * 60.0) + (current_alignment * 40.0),
        ),
    )
    support_strength_01 = max(0.0, min(1.0, support_score / 100.0 if support_score > 1 else support_score))
    resistance_strength_01 = max(0.0, min(1.0, resistance_score / 100.0 if resistance_score > 1 else resistance_score))
    conflict_resolver = run_conflict_resolver(
        regime=str(regime.get("regime_type") or regime.get("regime") or "Transition"),
        confidence=float(confidence_proxy),
        breakout_strength=float(breakout_strength_adjusted),
        trap_probability=float(trap_probability_pct),
        support_strength=float(support_strength_01),
        resistance_strength=float(resistance_strength_01),
        alignment_score=float(alignment_score),
        support_zone_pressure=float(support_zone_pressure),
        resistance_zone_pressure=float(resistance_zone_pressure),
        material_breach=material_breach,
    )
    breakout_strength_adjusted = float(
        conflict_resolver.get("adjusted_breakout_strength", breakout_strength_adjusted) or breakout_strength_adjusted
    )
    breakout["breakout_strength"] = round(float(breakout_strength_adjusted), 4)
    conflict_suppressed = set(str(x) for x in (conflict_resolver.get("suppressed_signals") or []))
    conflict_breakout_suppressed = "breakout" in conflict_suppressed
    if conflict_breakout_suppressed:
        raw_breakout_strength = float(breakout.get("breakout_strength_raw", 0.0) or 0.0)
        breakout["breakout_up"] = False
        breakout["breakout_down"] = False
        if raw_breakout_strength > 0.70:
            breakout_candidate = True
            breakout["breakout_candidate"] = True
            breakout_strength_adjusted = max(0.0, min(1.0, raw_breakout_strength * 0.3))
            breakout["breakout_strength"] = round(float(breakout_strength_adjusted), 4)
            breakout_score = breakout_score * 0.3
        else:
            breakout["breakout_strength"] = 0.0
            breakout_strength_adjusted = 0.0
            breakout_score = 0.0

    bias_stability = compute_bias_stability(last_10_scores)
    now_dt = evaluation_time or datetime.now(timezone.utc)
    base_weights = dict(_calibrated_weights)
    state = adaptive_state or {}
    current_weights = state.get("weights") if isinstance(state.get("weights"), dict) else base_weights
    session_start_raw = state.get("session_start_utc")
    try:
        session_start_dt = (
            datetime.fromisoformat(session_start_raw)
            if isinstance(session_start_raw, str)
            else now_dt
        )
        if session_start_dt.tzinfo is None:
            session_start_dt = session_start_dt.replace(tzinfo=timezone.utc)
    except Exception:
        session_start_dt = now_dt
    elapsed_minutes = max(0.0, (now_dt - session_start_dt).total_seconds() / 60.0)
    allow_adaptation = (total_signals_logged >= 5) or (elapsed_minutes >= 60.0)
    if not allow_adaptation:
        current_weights = base_weights
    last_recalc_raw = state.get("last_recalc_utc")
    try:
        last_recalc_dt = (
            datetime.fromisoformat(last_recalc_raw)
            if isinstance(last_recalc_raw, str)
            else None
        )
        if last_recalc_dt and last_recalc_dt.tzinfo is None:
            last_recalc_dt = last_recalc_dt.replace(tzinfo=timezone.utc)
    except Exception:
        last_recalc_dt = None
    recalc_due = (
        allow_adaptation
        and (
            last_recalc_dt is None
            or ((now_dt - last_recalc_dt).total_seconds() / 60.0) >= ADAPTIVE_RECALC_MINUTES
        )
    )
    if recalc_due:
        effective_stats = engine_stats or {
            "oi_accuracy": 0.55,
            "volume_accuracy": 0.55,
            "breakout_accuracy": 0.55,
            "sr_accuracy": 0.55,
        }
        current_weights = compute_adaptive_weights(
            engine_stats=effective_stats,
            current_weights=current_weights,
        ).get("adaptive_weights", current_weights)

    support_immediate = sr.get("support", {}).get("immediate")
    support_major = sr.get("support", {}).get("major")
    resistance_immediate = sr.get("resistance", {}).get("immediate")
    resistance_major = sr.get("resistance", {}).get("major")

    decision_v3 = run_decision_engine_v3(
        oi_score=oi_score,
        volume_score=volume_score,
        breakout_score=breakout_score,
        sr_score=sr_score,
        trap_penalty=trap_penalty,
        alignment_ratio=current_alignment,
        bias_stability_score=float(bias_stability.get("bias_stability_score", 55) or 55),
        regime_type=str(regime.get("regime_type") or regime.get("regime") or "Transition"),
        volatility_ratio=current_atr_ratio,
        session_phase=_infer_session_phase(features.get("meta", {}).get("timestamp")),
        previous_primary_bias=str((previous_state or {}).get("primary_bias") or "Neutral"),
        rolling_force_history=list((previous_state or {}).get("rolling_force_history") or []),
        rolling_clarity_history=list((previous_state or {}).get("rolling_clarity_history") or []),
        breakout_confirmed=bool(breakout.get("breakout_up") or breakout.get("breakout_down")),
        volume_expansion_confirmed=bool(volume.get("volume_expansion")),
        cycle_timestamp=str(features.get("meta", {}).get("timestamp") or ""),
        spot=spot,
        support_immediate=support_immediate,
        support_major=support_major,
        resistance_immediate=resistance_immediate,
        resistance_major=resistance_major,
        weights=current_weights,
    )
    directional_force = dict(decision_v3.get("directional_force") or {})
    bull_force_raw = max(0.0, float(directional_force.get("bull", 50.0) or 50.0) / 100.0)
    bear_force_raw = max(0.0, float(directional_force.get("bear", 50.0) or 50.0) / 100.0)
    momentum_score = float(price_momentum.get("momentum_score", 0.0) or 0.0)
    momentum_direction = str(price_momentum.get("momentum_direction", "neutral") or "neutral")
    if momentum_direction == "bullish":
        bull_force_raw += momentum_score * 0.10
    elif momentum_direction == "bearish":
        bear_force_raw += momentum_score * 0.10
    force_total = bull_force_raw + bear_force_raw
    if force_total > 0:
        bull_force = int(round((bull_force_raw / force_total) * 100.0))
        bull_force = max(0, min(100, bull_force))
        bear_force = 100 - bull_force
        directional_force["bull"] = bull_force
        directional_force["bear"] = bear_force
        directional_force["strength"] = abs(bull_force - bear_force)
        decision_v3["directional_force"] = directional_force
        decision_v3["directional_force_value"] = abs(bull_force - bear_force)
        decision_v3["bull_probability"] = round(bull_force / 100.0, 4)
        decision_v3["bear_probability"] = round(bear_force / 100.0, 4)
        decision_v3["probability_bull"] = bull_force
        decision_v3["probability_bear"] = bear_force
        if bull_force > 55:
            decision_v3["bias"] = "Bullish"
        elif bear_force > 55:
            decision_v3["bias"] = "Bearish"
        else:
            decision_v3["bias"] = "Neutral"
    current_regime = str(regime.get("regime_type") or regime.get("regime") or "Transition")
    regime_mapped = (
        "Trend"
        if current_regime in ("Trend", "Trend Day", "Breakdown")
        else "Range"
        if current_regime in ("Range", "Range Day")
        else "Transition"
    )
    decision = {
        "bias": decision_v3["bias"],
        "bull_probability": decision_v3["bull_probability"],
        "bear_probability": decision_v3["bear_probability"],
        "confidence": decision_v3["confidence"],
        "weighted_score": decision_v3["composite_score"],
        "composite_score": decision_v3["composite_score"],
        "alignment_ratio": round(current_alignment, 4),
        "volatility_ratio": round(current_atr_ratio, 4),
        "volatility_state": volatility_state,
        "regime": regime_mapped,
        "weight_distribution": decision_v3.get("weight_distribution", base_weights),
        "structural_clarity_score": decision_v3.get("structural_clarity_score"),
        "directional_force": decision_v3.get("directional_force"),
        "clarity": decision_v3.get("clarity"),
        "execution_risk": decision_v3.get("execution_risk"),
        "state": decision_v3.get("state"),
        "primary_bias": decision_v3.get("primary_bias"),
        "framework_status": decision_v3.get("framework_status"),
        "drift": decision_v3.get("drift"),
        "micro_bias": decision_v3.get("micro_bias"),
        "last_primary_update_time": decision_v3.get("last_primary_update_time"),
        "rolling_force_history": decision_v3.get("rolling_force_history", []),
        "rolling_clarity_history": decision_v3.get("rolling_clarity_history", []),
        "retail_mapping": decision_v3.get("retail_mapping", {}),
        "engine_contributions": decision_v3.get("engine_contributions", {}),
        "engine_scores": decision_v3.get("engine_scores", {}),
        "projection": str(conflict_resolver.get("projection") or "No Confirmed Breakout"),
        "conflict_market_state": str(conflict_resolver.get("market_state") or "Balanced"),
        "conflict_flags": list(conflict_resolver.get("conflict_flags") or []),
    }
    if projection_override:
        decision["projection"] = projection_override
        decision["regime_hint"] = regime_hint

    # Structural clarity override using normalized variance across key live signals.
    clarity_inputs = [
        max(0.0, min(1.0, float(alignment_score))),
        max(0.0, min(1.0, float(breakout_strength_adjusted))),
        max(0.0, min(1.0, float(oi.get("oi_velocity_score", 0.0) or 0.0))),
        max(0.0, min(1.0, float(trap_probability_pct) / 100.0)),
    ]
    clarity_mean = sum(clarity_inputs) / max(1, len(clarity_inputs))
    clarity_var = sum((x - clarity_mean) ** 2 for x in clarity_inputs) / max(1, len(clarity_inputs))
    clarity_override = max(0.0, min(100.0, (1.0 - max(0.0, min(1.0, clarity_var))) * 100.0))
    decision["clarity"] = round(float(clarity_override), 2)
    decision["confidence"] = round(float(clarity_override), 2)
    decision["regime_candidate"] = str(decision.get("state") or "")
    decision["regime_hold_count"] = int(regime.get("candidate_regime_count", 0) or 0)
    decision["regime_zone"] = _map_regime_zone(str(decision.get("state") or ""))

    detected_committed_regime = _derive_committed_regime_label(
        state=str(decision.get("state") or ""),
        engine_regime=str(regime.get("regime") or ""),
    )
    committed_regime, next_candidate_regime, next_candidate_regime_count = _apply_committed_regime_hysteresis(
        detected_regime=detected_committed_regime,
        current_committed_regime=(previous_state or {}).get("committed_regime"),
        candidate_regime=(previous_state or {}).get("candidate_regime"),
        candidate_regime_count=int((previous_state or {}).get("candidate_regime_count", 0) or 0),
        last_detected_regime=(previous_state or {}).get("last_detected_regime"),
    )

    target = run_target_engine(features, sr, breakout, oi, trap, volume, decision=decision, regime=regime)
    if "expansion_targets" in conflict_suppressed:
        target["primary_target"] = None
        target["extended_target"] = None
        target["expansion_score"] = 0.0
    support_level = sr.get("support", {}).get("strike")
    resistance_level = sr.get("resistance", {}).get("strike")
    if (
        _safe_float(spot) is not None
        and _safe_float(resistance_level) is not None
        and float(spot or 0.0) > float(resistance_level or 0.0)
        and float(trap.get("trap_probability_pct", 0) or 0.0) < 45.0
        and not str(trap.get("trap_type") or "").strip()
    ):
        trap["trap_type"] = "Breakout In Progress"
        trap["trap_direction"] = ""
        trap["trap_message"] = (
            f"Breakout in progress - watch for acceptance above {int(float(resistance_level))}."
        )
        trap["trap_affected_level"] = resistance_level
        trap["show_affected_level"] = True
    support_reference_state = _resolve_absorption_reference_level(
        spot=spot,
        current_support=support_level,
        current_resistance=resistance_level,
        current_timestamp_utc=session_eval_time.astimezone(timezone.utc)
        if isinstance(session_eval_time, datetime)
        else None,
        previous_state=previous_state,
    )
    absorption_reference_level = support_reference_state.get("absorption_reference_level")
    oi_imbalance_trap = _detect_oi_imbalance_trap(
        rows=rows,
        support_level=support_level,
        resistance_level=resistance_level,
    )
    strongest_oi_strike = support_level
    if resistance_score > support_score:
        strongest_oi_strike = resistance_level
    expiry_adaptive = run_expiry_adaptive_mode(
        expiry=expiry,
        spot=spot,
        support=support_level,
        resistance=resistance_level,
        expected_move=target.get("expected_move"),
        bias=str((decision or {}).get("bias", "Neutral")),
        trap_risk=trap.get("trap_probability_pct", 0),
        session_phase=target.get("session_phase"),
        strongest_oi_strike=strongest_oi_strike,
        strike_gap=features.get("strike_gap"),
    )
    target["target_1"] = expiry_adaptive["target1"]
    target["target_2"] = expiry_adaptive["target2"]
    target["target1"] = expiry_adaptive["target1"]
    target["target2"] = expiry_adaptive["target2"]
    target["adjustedMove"] = expiry_adaptive["adjustedMove"]
    target["expiry_multiplier"] = expiry_adaptive["expiry_multiplier"]
    target["expiry_mode"] = expiry_adaptive["expiry_mode"]
    target["expansion_score"] = round(
        max(0.0, min(1.0, float(target.get("expansion_score", 0.0) or 0.0) * alignment_score)),
        4,
    )
    if bool(breakout.get("breakout_up")) and resistance_zone_pressure > 60.0:
        target["expansion_score"] = round(
            max(0.0, min(1.0, float(target.get("expansion_score", 0.0) or 0.0) + 0.1)),
            4,
        )
    if bool(breakout.get("breakout_down")) and support_zone_pressure > 60.0:
        target["expansion_score"] = round(
            max(0.0, min(1.0, float(target.get("expansion_score", 0.0) or 0.0) + 0.1)),
            4,
        )

    trap_affected_level, trap_direction = _canonicalize_trap_reference(
        trap=trap,
        spot=spot,
        support_level=support_level,
        resistance_level=resistance_level,
        breakout_up=bool(breakout.get("breakout_up")),
        breakout_down=bool(breakout.get("breakout_down")),
    )
    trap["trap_affected_level"] = trap_affected_level
    trap["trap_direction"] = trap_direction
    trap["show_affected_level"] = bool(str(trap.get("trap_type") or "").strip() and trap_affected_level is not None)

    trap_probability = float(trap.get("trap_probability_pct", 0.0) or 0.0)
    # Stale-resistance trap discount:
    # If price has stayed above resistance for a sustained period and SR did not
    # transition, reduce resistance-side false-break trap inflation.
    support_transition_now = _is_support_transition_active(
        support_reference_state.get("support_shift_cycle", 0)
    )
    prev_cycle_resistance_for_stale = _safe_float(
        (previous_state or {}).get("current_resistance")
        or (previous_state or {}).get("resistance_level")
        or (((previous_state or {}).get("levels") or {}).get("resistance", {}) or {}).get("immediate")
    )
    current_cycle_resistance_for_stale = _safe_float(support_reference_state.get("current_resistance"))
    resistance_transition_now = (
        prev_cycle_resistance_for_stale is not None
        and current_cycle_resistance_for_stale is not None
        and abs(prev_cycle_resistance_for_stale - current_cycle_resistance_for_stale) > 1e-6
    )
    sr_transition_now = bool(support_transition_now or resistance_transition_now)
    above_resistance_now = (
        _safe_float(spot) is not None
        and _safe_float(resistance_level) is not None
        and float(spot or 0.0) > float(resistance_level or 0.0)
    )
    prev_seconds_above_resistance = int((previous_state or {}).get("seconds_above_resistance", 0) or 0)
    seconds_above_resistance = (
        prev_seconds_above_resistance + REFRESH_SECONDS if above_resistance_now else 0
    )
    stale_break_window_met = bool(
        above_resistance_now and (seconds_above_resistance >= 20 * 60) and (not sr_transition_now)
    )
    trap_type_text = str(trap.get("trap_type") or "").strip().lower()
    resistance_false_break_context = bool(
        ("false-break" in trap_type_text)
        or ("breakout failure" in trap_type_text)
        or (str(trap.get("trap_direction") or "").strip().lower() == "upside")
    )
    stale_resistance_discount_applied = False
    stale_resistance_discount_points = 0.0
    if stale_break_window_met and resistance_false_break_context:
        stale_resistance_discount_points = 12.0
        trap_probability = max(5.0, trap_probability - stale_resistance_discount_points)
        trap["trap_probability_pct"] = int(round(trap_probability))
        trap["trap_probability"] = int(round(trap_probability))
        trap["trap_risk"] = int(round(trap_probability))
        trap["trap_type"] = "Breakout In Progress"
        trap["trap_direction"] = ""
        trap["trap_message"] = (
            f"Spot has held above resistance {int(float(resistance_level or 0.0))} for 20+ minutes without SR transition; "
            "discounting stale false-break risk."
        )
        trap["trap_affected_level"] = resistance_level
        trap["show_affected_level"] = True
        stale_resistance_discount_applied = True
    trap["stale_resistance_discount_applied"] = bool(stale_resistance_discount_applied)
    trap["stale_resistance_discount_points"] = float(stale_resistance_discount_points)
    trap["seconds_above_resistance"] = int(seconds_above_resistance)
    trap["stale_break_window_met"] = bool(stale_break_window_met)

    oi_buildup_type = str(oi.get("buildup_type") or "")
    pinning_active = oi_buildup_type.strip().lower() == "two-sided writing"
    pinning_trap_modifier_points = PINNING_TRAP_MODIFIER_POINTS if pinning_active else 0.0
    if pinning_trap_modifier_points > 0.0:
        trap_probability = min(95.0, trap_probability + pinning_trap_modifier_points)
        trap["trap_probability_pct"] = int(round(trap_probability))
        trap["trap_probability"] = int(round(trap_probability))
        trap["trap_risk"] = int(round(trap_probability))
    trap["pinning_active"] = bool(pinning_active)
    trap["pinning_trap_modifier_points"] = float(pinning_trap_modifier_points)

    breakout_strength = breakout_strength_adjusted
    mss = _compute_market_structure_score(
        alignment_score=alignment_score,
        breakout_strength=breakout_strength,
        oi_velocity_score=float(oi.get("oi_velocity_score", 0.0) or 0.0),
        clarity=float(decision.get("clarity", decision.get("structural_clarity_score", 0.0)) or 0.0),
        trap_probability=trap_probability,
    )
    dps = _compute_directional_pressure_score(
        directional_force=dict(decision.get("directional_force") or {}),
        alignment_score=alignment_score,
        market_structure_score=float(mss.get("market_structure_score", 0.0) or 0.0),
        oi_bias=oi_score,
        oi_velocity_score=float(oi.get("oi_velocity_score", 0.0) or 0.0),
        volume_expansion_score=volume_expansion_score,
        ce_rvr=float((volume.get("rvr", {}) or {}).get("ce", 0.0) or 0.0),
        pe_rvr=float((volume.get("rvr", {}) or {}).get("pe", 0.0) or 0.0),
        oi_buildup_type=oi_buildup_type,
        trap_probability=trap_probability,
        spot=spot,
        support=support_level,
        resistance=resistance_level,
        day_high=day_high,
        day_low=day_low,
        previous_alignment_score=previous_alignment,
        previous_directional_dominance=(previous_state or {}).get("directional_force_dominance"),
    )
    reversal_decay_cycles = int((previous_state or {}).get("reversal_decay_cycles", 0) or 0)
    reversal_detected_now = bool(dps.get("dps_decay_applied", False))
    if reversal_detected_now:
        reversal_decay_cycles = REVERSAL_DECAY_CYCLES
    elif reversal_decay_cycles > 0:
        reversal_decay_cycles -= 1
        dps_value = float(dps.get("directional_pressure_score", 0.0) or 0.0) * REVERSAL_DECAY
        dps_scenario_value = float(
            dps.get("dps_scenario_adjusted", dps.get("directional_pressure_score", 0.0)) or 0.0
        ) * REVERSAL_DECAY
        dps_adjusted_value = float(dps.get("dps_adjusted", 0.0) or 0.0) * REVERSAL_DECAY
        dps["directional_pressure_score"] = round(dps_value, 4)
        dps["dps_scenario_adjusted"] = round(dps_scenario_value, 4)
        dps["dps_adjusted"] = round(dps_adjusted_value, 4)
        pressure_state, trade_action, pressure_explanation = _pressure_labels_from_dps_adjusted(dps_adjusted_value)
        dps["pressure_state"] = pressure_state
        dps["trade_action"] = trade_action
        dps["pressure_explanation"] = pressure_explanation
        dps["dps_decay_applied"] = True
    previous_bias = str((previous_state or {}).get("previous_bias") or "Neutral")
    current_bias_for_dps = str(decision.get("bias", "Neutral") or "Neutral")
    if previous_bias != "Neutral" and current_bias_for_dps != previous_bias:
        dps["directional_pressure_score"] = 0.0
        dps["dps_scenario_adjusted"] = 0.0
        dps["dps_adjusted"] = 0.0
        dps["pressure_state"] = "Balanced Pressure"
        dps["trade_action"] = "WAIT"
        dps["pressure_explanation"] = "Directional pressure reset after bias reversal."
    decision["directional_pressure_score"] = dps["directional_pressure_score"]
    decision["dps_scenario_adjusted"] = dps.get("dps_scenario_adjusted")
    decision["dps_adjusted"] = dps["dps_adjusted"]
    decision["oi_scenario"] = dps.get("oi_scenario")
    decision["oi_scenario_multiplier"] = dps.get("oi_scenario_multiplier")
    decision["dps_scenario_multiplier"] = dps.get("oi_scenario_multiplier")
    decision["pinning_active"] = bool(dps.get("pinning_active", False))
    decision["pinning_trap_modifier_points"] = float(pinning_trap_modifier_points)
    decision["pressure_state"] = dps["pressure_state"]
    decision["trade_action"] = dps["trade_action"]
    decision["pressure_explanation"] = dps["pressure_explanation"]
    decision["directional_force_dominance"] = dps["directional_dominance"]
    decision["dps_decay_applied"] = bool(dps.get("dps_decay_applied"))
    decision["reversal_decay_cycles"] = int(reversal_decay_cycles)
    wall_break_pre = detect_wall_break(
        spot=spot,
        support=support_level,
        resistance=resistance_level,
        support_center=sr.get("support_center"),
        resistance_center=sr.get("resistance_center"),
        rows=features.get("rows") or [],
    )
    suppression_threshold = 0.55 * (0.7 if bool(wall_break_pre.get("wall_break_signal")) else 1.0)
    breakout_suppressed = alignment_score < suppression_threshold or conflict_breakout_suppressed
    breakout_probability = compute_breakout_probability(
        spot=spot,
        support=support_level,
        resistance=resistance_level,
        alignment_score=alignment_score,
        volume_expansion_score=volume_expansion_score,
        oi_bias=oi_score,
        trap_probability=trap_probability,
        support_zone_pressure=support_zone_pressure,
        resistance_zone_pressure=resistance_zone_pressure,
        breakout_strength=breakout_strength,
        clarity=float(decision.get("clarity", 0.0) or 0.0),
        directional_force=dict(decision.get("directional_force") or {}),
        day_trend=day_trend,
    )
    support_row_for_absorption = next(
        (
            row
            for row in rows
            if _safe_float(row.get("strike")) is not None
            and absorption_reference_level is not None
            and abs(float(row.get("strike")) - float(absorption_reference_level)) < 1e-6
        ),
        None,
    )
    support_absorption = _detect_support_absorption(
        spot=spot,
        support=absorption_reference_level,
        strike_gap=features.get("strike_gap"),
        pe_oi_change_pct=(support_row_for_absorption or {}).get("PE_OIChangePct"),
        volume_expansion_score=volume_expansion_score,
        breakout_strength=breakout_strength_adjusted,
        trap_probability=trap_probability,
    )
    confirmation_type = str(material_breach.get("confirmation_type") or "")
    material_breach_confirmed = bool(material_breach.get("material_breach_confirmed"))
    absorption_detected = bool(support_absorption.get("absorption_detected"))
    absorption_wins = False
    if bool(material_breach.get("support_broken")) and absorption_detected:
        if not material_breach_confirmed or not confirmation_type:
            absorption_wins = True
        elif confirmation_type == "support_abandonment":
            absorption_wins = False
        elif confirmation_type == "bearish_positioning":
            absorption_wins = float(trap_probability or 0.0) > 70.0
    material_breach["absorption_conflict"] = bool(absorption_detected and material_breach_confirmed)
    material_breach["absorption_wins"] = absorption_wins
    if absorption_wins:
        decision["projection"] = "Support Broken — Monitoring"
        decision["trade_action"] = "WAIT"
    elif bool(material_breach.get("support_broken")) and material_breach_confirmed:
        if confirmation_type == "support_abandonment":
            decision["projection"] = "Support Broken — Abandonment Confirmed"
            decision["trade_action"] = "BREAKDOWN WATCH"
        elif confirmation_type == "bearish_positioning" and float(trap_probability or 0.0) <= 70.0:
            decision["projection"] = "Support Broken — Bearish Positioning Confirmed"
            decision["trade_action"] = "BREAKDOWN WATCH"
    breach_projection_override: str | None = None
    if material_breach_confirmed:
        if bool(material_breach.get("resistance_broken")):
            if absorption_detected:
                breach_projection_override = "Resistance Broken — Absorption Active"
                decision["trade_action"] = "WAIT"
            else:
                breach_projection_override = "Resistance Broken — Monitoring Expansion"
        elif bool(material_breach.get("support_broken")):
            if absorption_detected:
                breach_projection_override = "Support Broken — Absorption Active"
                decision["trade_action"] = "WAIT"
            else:
                breach_projection_override = "Support Broken — Monitoring Breakdown"

    if breach_projection_override:
        decision["projection"] = breach_projection_override

    breach_regime_override: str | None = None
    if material_breach_confirmed:
        if absorption_detected and (
            bool(material_breach.get("support_broken")) or bool(material_breach.get("resistance_broken"))
        ):
            breach_regime_override = "Trap Day"
        elif bool(material_breach.get("resistance_broken")):
            breach_regime_override = "Trend Day"
        elif bool(material_breach.get("support_broken")):
            breach_regime_override = "Breakdown Day"

    if breach_regime_override:
        committed_regime = breach_regime_override
        detected_committed_regime = breach_regime_override
        next_candidate_regime = ""
        next_candidate_regime_count = 0

    range_trap_cap_applied = False
    range_trap_cap_reason: str | None = None
    range_trap_cap_stage: str | None = None
    pre_readiness_range_like_session = _is_range_like_session(
        committed_regime=committed_regime,
        stabilized_regime_family=(previous_state or {}).get("stabilized_regime_family"),
        range_locked=bool((previous_state or {}).get("range_locked", False)),
        no_edge=bool((previous_state or {}).get("no_edge", False)),
    )
    if pre_readiness_range_like_session and not material_breach_confirmed:
        trap_stability_payload = _stabilize_trap_probability(
            new_trap_probability=min(float(trap_probability or 0.0), 72.0),
            previous_state=previous_state,
        )
        _apply_stabilized_trap(trap, trap_stability_payload)
        trap_probability = float(trap.get("trap_probability_pct", 0.0) or 0.0)
        range_trap_cap_applied = True
        range_trap_cap_reason = "range_family_cap"
        range_trap_cap_stage = "pre_readiness"

    absorption_wait_override = bool(absorption_detected and str(decision.get("trade_action") or "") == "WAIT")
    trade_readiness = _compute_trade_readiness(
        clarity=float(decision.get("clarity", 0.0) or 0.0),
        alignment_score=alignment_score,
        trap_probability=trap_probability,
        execution_risk=float(decision.get("execution_risk", 0.0) or 0.0),
        breakout_suppressed=breakout_suppressed,
        breakout_candidate=breakout_candidate,
        breakout_probability=max(
            float(breakout_probability.get("upside", 0.0) or 0.0),
            float(breakout_probability.get("downside", 0.0) or 0.0),
        ),
        skip_trap_deduction=absorption_wait_override,
    )
    decision["trade_readiness"] = trade_readiness["trade_readiness"]
    decision["readiness_state"] = trade_readiness["readiness_state"]
    backend_state = _readiness_regime_state(
        committed_regime=committed_regime,
        backend_state=str(decision.get("state", "") or ""),
    )
    if backend_state == "Aggressive Trend":
        decision["trade_readiness"] = max(float(decision.get("trade_readiness", 0.0) or 0.0), 55.0)
    elif backend_state == "Cautious Trend":
        decision["trade_readiness"] = max(float(decision.get("trade_readiness", 0.0) or 0.0), 40.0)
    elif backend_state == "Standby":
        decision["trade_readiness"] = min(float(decision.get("trade_readiness", 0.0) or 0.0), 38.0)
    # Readiness reconciliation gates with hysteresis to avoid boundary oscillation.
    prev_readiness_active = bool((previous_state or {}).get("readiness_active", False))
    is_watch_action = str(decision.get("trade_action", "")) in {"BREAKOUT WATCH", "BREAKDOWN WATCH"}
    watch_upper = 57.0
    watch_lower = 53.0
    readiness_score = float(decision.get("trade_readiness", 0.0) or 0.0)

    if not prev_readiness_active and readiness_score >= watch_upper:
        readiness_active = True
    elif prev_readiness_active and readiness_score < watch_lower:
        readiness_active = False
    else:
        readiness_active = prev_readiness_active

    if is_watch_action and not readiness_active:
        decision["trade_action"] = "WAIT"
    if str(decision.get("trade_action", "")) in {"BREAKOUT WATCH", "BREAKDOWN WATCH"}:
        decision["trade_readiness"] = max(float(decision.get("trade_readiness", 0.0) or 0.0), 55.0)
    if absorption_wins:
        decision["trade_readiness"] = min(float(decision.get("trade_readiness", 0.0) or 0.0), 45.0)
        readiness_active = False
    decision["trade_readiness"] = max(0.0, min(100.0, float(decision.get("trade_readiness", 0.0) or 0.0)))
    decision["readiness_active"] = readiness_active
    if not readiness_active and str(decision.get("trade_action", "")) in {"LONG BIAS", "SHORT BIAS"}:
        decision["trade_action"] = "WAIT"
    if absorption_wins:
        decision["readiness_state"] = "Absorption Active"
    elif float(decision.get("trade_readiness", 0.0) or 0.0) >= 70.0:
        decision["readiness_state"] = "High"
    elif float(decision.get("trade_readiness", 0.0) or 0.0) >= 40.0:
        decision["readiness_state"] = "Moderate"
    else:
        decision["readiness_state"] = "Low"
    if float(decision.get("trade_readiness", 0.0) or 0.0) < 25.0:
        decision["trade_action"] = "WAIT"
    elif float(decision.get("trade_readiness", 0.0) or 0.0) < 40.0 and str(decision.get("trade_action")) in {"LONG BIAS", "SHORT BIAS"}:
        decision["trade_action"] = "WAIT"

    support_transition_badge = _is_support_transition_active(
        support_reference_state.get("support_shift_cycle", 0)
    )
    previous_cycle_resistance = _safe_float(
        (previous_state or {}).get("current_resistance")
        or (previous_state or {}).get("resistance_level")
        or (((previous_state or {}).get("levels") or {}).get("resistance", {}) or {}).get("immediate")
    )
    current_cycle_resistance = _safe_float(support_reference_state.get("current_resistance"))
    resistance_transition_badge = (
        previous_cycle_resistance is not None
        and current_cycle_resistance is not None
        and abs(previous_cycle_resistance - current_cycle_resistance) > 1e-6
    )
    structural_state = _derive_spc_structural_state(
        trap_probability=trap_probability,
        support_transition_active=support_transition_badge,
        resistance_transition_active=resistance_transition_badge,
        support_shift_cycle=int(support_reference_state.get("support_shift_cycle", 0) or 0),
        absorption_detected=absorption_detected,
    )
    raw_candidate_regime = detected_committed_regime
    range_lock_payload = _apply_range_lock_and_no_edge(
        raw_candidate_regime=raw_candidate_regime,
        structural_state=structural_state,
        trap_probability=trap_probability,
        trade_readiness=float(decision.get("trade_readiness", 0.0) or 0.0),
        breach_confirmed=material_breach_confirmed,
        pressure_state=str(decision.get("pressure_state", "") or ""),
        current_regime=(previous_state or {}).get("committed_regime") or committed_regime,
    )
    candidate_regime_after_range_lock = str(range_lock_payload.get("candidate_regime") or raw_candidate_regime or "Range Play")
    range_locked = bool(range_lock_payload.get("range_locked", False))
    no_edge = bool(range_lock_payload.get("no_edge", False))
    derived_market_state = str(range_lock_payload.get("market_state") or "")
    regime_stabilizer = _apply_regime_stabilizer(
        raw_candidate_regime=candidate_regime_after_range_lock,
        current_regime=(previous_state or {}).get("committed_regime") or committed_regime,
        regime_hold_cycles=int((previous_state or {}).get("regime_hold_cycles", 0) or 0),
        regime_candidate=(previous_state or {}).get("regime_candidate"),
        regime_candidate_streak=int((previous_state or {}).get("regime_candidate_streak", 0) or 0),
        structural_state=structural_state,
    )
    committed_regime = str(regime_stabilizer.get("final_regime") or committed_regime or "Range Play")
    stabilized_regime_family = str(regime_stabilizer.get("final_family") or _regime_family(committed_regime))
    next_candidate_regime = str(regime_stabilizer.get("regime_candidate") or "")
    next_candidate_regime_count = int(regime_stabilizer.get("regime_candidate_streak", 0) or 0)
    decision["regime_hold_count"] = int(regime_stabilizer.get("regime_hold_cycles", 0) or 0)
    decision["regime_candidate"] = candidate_regime_after_range_lock
    decision["regime_zone"] = _map_regime_zone(committed_regime)
    decision["structural_state_marker"] = structural_state
    decision["range_locked"] = range_locked
    decision["no_edge"] = no_edge
    decision["market_state_marker"] = derived_market_state
    if no_edge:
        decision["trade_action"] = "WAIT"
        decision["projection"] = "No Confirmed Breakout"
    momentum_override = _apply_momentum_override(
        trade_action=str(decision.get("trade_action", "WAIT")),
        spot=spot,
        open_price=open_price,
        day_high=day_high,
        day_low=day_low,
        support=support_level,
        resistance=resistance_level,
        directional_force=dict(decision.get("directional_force") or {}),
        clarity=float(decision.get("clarity", 0.0) or 0.0),
        volume_expansion_score=volume_expansion_score,
        alignment_score=alignment_score,
        breakout_candidate=breakout_candidate,
        material_breach=material_breach,
    )
    decision["trade_action"] = momentum_override["trade_action"]
    decision["momentum_override_score"] = momentum_override["momentum_score"]
    decision["momentum_override_explanation"] = momentum_override["momentum_override_explanation"]
    if str(decision.get("trade_action", "")) in {"BREAKOUT WATCH", "BREAKDOWN WATCH"} and not bool(decision.get("readiness_active", False)):
        decision["trade_action"] = "WAIT"
    if absorption_wins:
        decision["trade_action"] = "WAIT"
        decision["projection"] = "Support Broken — Monitoring"
    if breach_projection_override:
        decision["projection"] = breach_projection_override

    # Trade action changes only when regime zone changes.
    prev_regime_zone = str((previous_state or {}).get("regime_zone") or "")
    current_regime_zone = str(decision.get("regime_zone") or "")
    if (
        prev_regime_zone
        and current_regime_zone
        and prev_regime_zone == current_regime_zone
        and not (
            bool(decision.get("readiness_active", False))
            and str(decision.get("trade_action", "")) in {"LONG BIAS", "SHORT BIAS"}
        )
    ):
        prev_trade_action = str((previous_state or {}).get("trade_action") or "")
        if prev_trade_action:
            decision["trade_action"] = prev_trade_action

    if (
        bool(decision.get("readiness_active", False))
        and str(decision.get("trade_action", "WAIT")) == "WAIT"
        and not absorption_wins
    ):
        dps_adjusted_value = float(decision.get("dps_adjusted", 0.0) or 0.0)
        if dps_adjusted_value > 0.35:
            decision["trade_action"] = "LONG BIAS"
        elif dps_adjusted_value < -0.35:
            decision["trade_action"] = "SHORT BIAS"

    current_bias = str(decision.get("bias", "Neutral"))
    current_projection = str(decision.get("projection", "No Confirmed Breakout"))
    force_strength = float(
        (decision.get("directional_force") or {}).get("strength")
        if isinstance(decision.get("directional_force"), dict)
        else 0.0
    )
    if force_strength <= 0:
        weighted_score_fallback = float(decision.get("weighted_score", 0.0) or 0.0)
        force_strength = abs(weighted_score_fallback) * 100.0

    if breach_projection_override:
        stable_bias = current_bias
        stable_projection = current_projection
        bias_change_counter = int((previous_state or {}).get("bias_change_counter", 0) or 0)
        projection_change_counter = 0
        bias_stability_cycles = int((previous_state or {}).get("bias_stability_cycles", 0) or 0)
        persistence_drift = str((previous_state or {}).get("drift") or decision.get("drift") or "Stable")
    else:
        stability = _apply_signal_stability_layer(
            previous_state=previous_state,
            new_bias=current_bias,
            new_projection=current_projection,
            current_mss=float(mss.get("market_structure_score", 0.0) or 0.0),
            directional_force=force_strength,
            confidence=float(decision.get("confidence", 50.0) or 50.0),
            clarity=float(decision.get("clarity", decision.get("structural_clarity_score", 0.0)) or 0.0),
        )
        stable_bias = str(stability["primary_bias"])
        stable_projection = str(stability["projection"])
        bias_change_counter = int(stability["bias_change_counter"])
        projection_change_counter = int(stability["projection_change_counter"])
        bias_stability_cycles = int(stability["bias_stability_cycles"])
        persistence_drift = str(stability["drift"])
        mss["market_structure_score"] = float(stability["market_structure_score"])
    decision["projection"] = stable_projection
    decision["drift"] = persistence_drift
    decision["primary_bias"] = stable_bias
    decision["micro_bias"] = current_bias
    decision["framework_status"] = "Stable"

    mss_conflict = _apply_mss_bias_conflict(
        market_structure_score=float(mss.get("market_structure_score", 0.0) or 0.0),
        bias=stable_bias,
        state=str(decision.get("state", "")),
        conflict_flags=list(decision.get("conflict_flags", []) or []),
    )
    decision["state"] = mss_conflict["state"]
    decision["structure_bias"] = mss_conflict["structure_bias"]
    decision["transition_phase"] = bool(mss_conflict["transition_phase"])
    decision["conflict_flags"] = list(mss_conflict["conflict_flags"])
    bull_prob_pct = round(float((decision.get("bull_probability", 0.5) or 0.5) * 100.0), 2)
    bear_prob_pct = round(float((decision.get("bear_probability", 0.5) or 0.5) * 100.0), 2)
    directional_force_value = float((decision.get("directional_force") or {}).get("strength", 0.0) or 0.0)
    if abs(bull_prob_pct - bear_prob_pct) < 30.0 and directional_force_value < 55.0:
        decision["conflict_market_state"] = "Range Conflict"
    if sr_breach_state == "resistance_breached":
        decision["projection"] = "Upside Breakout"
    elif sr_breach_state == "support_breached":
        decision["projection"] = "Downside Breakout"
    if breakout_candidate and str(decision.get("projection", "No Confirmed Breakout")) == "No Confirmed Breakout":
        decision["projection"] = "Potential Breakout Watch"
    if breach_projection_override:
        decision["projection"] = breach_projection_override
    if breach_regime_override:
        committed_regime = breach_regime_override
        detected_committed_regime = breach_regime_override
        next_candidate_regime = ""
        next_candidate_regime_count = 0
    long_trend = _classify_long_trend(
        spot=spot,
        previous_close=previous_close,
        structure_bias=str(decision.get("structure_bias", stable_bias)),
    )
    if committed_regime in {"Trend Day", "Breakdown Day"}:
        trap_conf_adj = adjust_trap_by_confidence(
            base_trap=float(trap.get("trap_probability_pct", 0) or 0),
            smoothed_score=float(decision.get("weighted_score", 0.0) or 0.0),
            confidence_percent=float(decision.get("confidence", 0) or 0),
        )
        trap_stability_payload = _stabilize_trap_probability(
            new_trap_probability=float(trap_conf_adj["trap_probability"]),
            previous_state=previous_state,
        )
        _apply_stabilized_trap(trap, trap_stability_payload)
        trap["confidence_factor"] = float(trap_conf_adj["confidence_factor"])
        trap["trap_trend_adjustment_applied"] = True
    else:
        trap["confidence_factor"] = 1.0
    trap["is_trap"] = bool(trap["trap_probability_pct"] >= 60)
    high_zone_pressure = support_zone_pressure > 60.0 or resistance_zone_pressure > 60.0
    if high_zone_pressure and int(trap["trap_probability_pct"]) >= 60:
        trap["trap_type"] = "False-Break Risk"
        trap["trap_message"] = "Zone pressure is high but trap risk is elevated: false-break risk."

    trap["oi_imbalance_trap"] = oi_imbalance_trap
    if int(oi_imbalance_trap.get("trap_probability", 0) or 0) > 0:
        trap["trap_reason"] = oi_imbalance_trap.get("trap_reason")
    if int(oi_imbalance_trap.get("support_strength", 0) or 0) > 0:
        trap["support_reason"] = oi_imbalance_trap.get("support_reason")

    weighted_score = float(decision.get("weighted_score", 0.0) or 0.0)

    current_alignment = float(decision.get("alignment_ratio", 0.0) or 0.0)
    current_atr_ratio = float(decision.get("volatility_ratio", 1.0) or 1.0)
    current_regime = str(decision.get("regime", "Range"))
    atm_row = features.get("atm_row") or {}
    rows = features.get("rows") or []
    atm_total_volume = float(atm_row.get("CE_Volume", 0.0) or 0.0) + float(atm_row.get("PE_Volume", 0.0) or 0.0)
    avg_total_volume = (
        sum(float(r.get("CE_Volume", 0.0) or 0.0) + float(r.get("PE_Volume", 0.0) or 0.0) for r in rows) / max(1, len(rows))
    )
    current_volume_ratio = atm_total_volume / max(1.0, avg_total_volume)
    current_oi_delta = abs(float(atm_row.get("CE_DeltaOI", 0.0) or 0.0)) + abs(
        float(atm_row.get("PE_DeltaOI", 0.0) or 0.0)
    )
    wall_break = wall_break_pre
    regime_shift = detect_regime_shift(
        previous_smoothed_score=float(previous_score or 0.0),
        current_smoothed_score=weighted_score,
        previous_regime=str(previous_regime or current_regime),
        current_regime=current_regime,
        previous_alignment=float(previous_alignment or 0.0),
        current_alignment=current_alignment,
        previous_atr_ratio=float(previous_atr_ratio or current_atr_ratio),
        current_atr_ratio=current_atr_ratio,
    )
    momentum_exhaustion = detect_momentum_exhaustion(
        smoothed_score=weighted_score,
        previous_smoothed_score=float(previous_score or 0.0),
        volume_ratio=current_volume_ratio,
        previous_volume_ratio=float(previous_volume_ratio or current_volume_ratio),
        oi_delta=current_oi_delta,
        previous_oi_delta=float(previous_oi_delta or current_oi_delta),
        atr_ratio=current_atr_ratio,
        previous_atr_ratio=float(previous_atr_ratio or current_atr_ratio),
    )
    combo_detector = detect_exhaustion_trap_combo(
        trap_risk=float(expiry_adaptive.get("trap_risk", trap.get("trap_probability_pct", 0)) or 0),
        momentum_exhaustion=bool(momentum_exhaustion.get("momentum_exhaustion")),
        confidence=float(decision.get("confidence", 50.0) or 50.0),
        volatility_state=str(decision.get("volatility_state", "Stable") or "Stable"),
    )
    resistance_strike = sr.get("resistance", {}).get("strike")
    support_strike = sr.get("support", {}).get("strike")
    breakout_up = bool(breakout.get("breakout_up")) and (volume_expansion_score > 0.4)
    breakout_down = bool(breakout.get("breakout_down")) and (volume_expansion_score > 0.4)
    breakout["breakout_up"] = breakout_up
    breakout["breakout_down"] = breakout_down
    breakout_suppressed = alignment_score < suppression_threshold or conflict_breakout_suppressed
    strong_bias = abs(weighted_score) > 0.5
    dominant_direction = "up" if weighted_score > 0 else "down" if weighted_score < 0 else "neutral"

    alerts: list[dict[str, Any]] = []
    suppression_reason_map: dict[str, str] = {}
    if breakout_suppressed:
        suppression_reason_map["rule:breakout_signals"] = (
            "conflict_resolver_suppression" if conflict_breakout_suppressed else "alignment_below_0.55"
        )
    for sr_alert in sr.get("alerts", []) or []:
        if not isinstance(sr_alert, dict):
            continue
        message = str(sr_alert.get("message", "")).strip()
        if not message:
            continue
        digits = re.findall(r"\d[\d,]*", message)
        alert_level = None
        if digits:
            try:
                alert_level = float(digits[0].replace(",", ""))
            except ValueError:
                alert_level = None
        lower = message.lower()
        direction = "neutral"
        if "resistance" in lower or "breakdown" in lower:
            direction = "down"
        elif "support" in lower or "breakout" in lower:
            direction = "up"
        if material_breach_confirmed and alert_level is not None:
            if direction == "up" and resistance_strike is not None and abs(alert_level - float(resistance_strike)) > 1e-6:
                suppression_reason_map[f"alert:{message}"] = "stale_resistance_alert_after_breach"
                continue
            if direction == "down" and support_strike is not None and abs(alert_level - float(support_strike)) > 1e-6:
                suppression_reason_map[f"alert:{message}"] = "stale_support_alert_after_breach"
                continue
        alerts.append(
            {
                "message": message,
                "direction": direction,
                "tier": str(sr_alert.get("tier", "immediate")),
                "source": "sr",
            }
        )

    if breakout_up and resistance_strike is not None and not breakout_suppressed:
        alert = {"message": f"Breakout above {resistance_strike}", "direction": "up", "tier": "immediate", "source": "breakout"}
        alerts.append(alert)

    if breakout_down and support_strike is not None and not breakout_suppressed:
        alert = {"message": f"Breakdown below {support_strike}", "direction": "down", "tier": "immediate", "source": "breakout"}
        alerts.append(alert)

    if bool(wall_break.get("wall_break_signal")) and wall_break.get("wall_break_reason"):
        alerts.append(
            {
                "message": str(wall_break.get("wall_break_reason")),
                "direction": "up" if wall_break.get("wall_break_direction") == "upside" else "down",
                "tier": "immediate",
                "source": "wall_break",
            }
        )

    regime_now = str(decision.get("regime", "") or "")
    projection_now = str(decision.get("projection", "") or "")
    is_range_no_breakout = regime_now == "Range" and projection_now.strip().lower() in {"no breakout", "range"}
    if is_range_no_breakout:
        downgraded: list[dict[str, Any]] = []
        for alert in alerts:
            msg = str(alert.get("message", ""))
            if msg.lower().startswith("breakout above"):
                suppression_reason_map[f"alert:{msg}"] = "range_no_breakout_downgrade"
                downgraded.append(
                    {
                        "message": msg.replace("Breakout above", "Low conviction breakout watch above"),
                        "direction": "neutral",
                        "tier": alert.get("tier", "immediate"),
                        "source": alert.get("source", "breakout"),
                    }
                )
            elif msg.lower().startswith("breakdown below"):
                suppression_reason_map[f"alert:{msg}"] = "range_no_breakout_downgrade"
                downgraded.append(
                    {
                        "message": msg.replace("Breakdown below", "Low conviction breakdown watch below"),
                        "direction": "neutral",
                        "tier": alert.get("tier", "immediate"),
                        "source": alert.get("source", "breakout"),
                    }
                )
            else:
                downgraded.append(alert)
        alerts = downgraded

    typed_alerts: list[dict[str, str]] = []
    suppressed_counter = 0
    for alert in alerts:
        alert_type = "primary" if alert["direction"] == dominant_direction else "counter"
        if strong_bias and alert_type == "counter":
            suppressed_counter += 1
            suppression_reason_map[f"alert:{alert['message']}"] = "counter_trend_strong_bias"
            continue
        typed_alerts.append(
            {
                "message": str(alert["message"]),
                "direction": str(alert["direction"]),
                "type": alert_type,
                "tier": str(alert.get("tier", "immediate")),
                "source": str(alert.get("source", "signal")),
            }
        )

    expiry_trap_risk = float(expiry_adaptive.get("trap_risk", trap.get("trap_probability_pct", 0)) or 0.0)
    post_stabilizer_range_like_session = _is_range_like_session(
        committed_regime=committed_regime,
        stabilized_regime_family=stabilized_regime_family,
        range_locked=range_locked,
        no_edge=no_edge,
    )
    if post_stabilizer_range_like_session and not material_breach_confirmed:
        expiry_trap_risk = min(expiry_trap_risk, 72.0)
        range_trap_cap_applied = True
        range_trap_cap_reason = "range_family_cap"
        range_trap_cap_stage = "expiry" if range_trap_cap_stage is None else "pre_readiness+expiry"
    trap_stability_payload = _stabilize_trap_probability(
        new_trap_probability=expiry_trap_risk,
        previous_state=previous_state,
    )
    _apply_stabilized_trap(trap, trap_stability_payload)
    expiry_adaptive["trap_risk"] = round(float(trap.get("trap_probability_pct", 0.0) or 0.0), 2)
    reversal_prob = compute_early_reversal_probability(
        momentum_exhaustion=bool(momentum_exhaustion.get("momentum_exhaustion")),
        trap_risk=float(expiry_adaptive.get("trap_risk", trap.get("trap_probability_pct", 0)) or 0),
        bias_stability_score=float(bias_stability.get("bias_stability_score", 55) or 55),
        atr_ratio=float(current_atr_ratio),
        alignment_ratio=float(current_alignment),
    )
    auto_exit = generate_auto_exit_suggestion(
        bias=stable_bias,
        momentum_exhaustion=bool(momentum_exhaustion.get("momentum_exhaustion")),
        reversal_probability=float(reversal_prob.get("reversal_probability", 0) or 0),
        regime_shift_alert=bool(regime_shift.get("regime_shift_alert")),
        confidence=float(decision.get("confidence", 50.0) or 50.0),
    )
    reversal_risk = int(reversal_prob.get("reversal_probability", 0) or 0)
    candidate_signals: list[dict[str, Any]] = []
    if (breakout_up or breakout_down) and not breakout_suppressed:
        candidate_signals.append(
            {
                "type": "breakout",
                "base_priority": 80,
                "message": "Breakout setup active" if breakout_up else "Breakdown setup active",
            }
        )
    if abs(weighted_score) > 0.35 and current_alignment >= 0.5:
        candidate_signals.append(
            {
                "type": "trend_continuation",
                "base_priority": 75,
                "message": "Trend continuation structure",
            }
        )
    if bool(momentum_exhaustion.get("momentum_exhaustion")):
        candidate_signals.append(
            {
                "type": "exhaustion",
                "base_priority": 70,
                "message": str(momentum_exhaustion.get("exhaustion_type") or "Momentum exhaustion"),
            }
        )
    if bool(trap.get("trap_probability_pct", 0) >= 60):
        candidate_signals.append(
            {
                "type": "trap_warning",
                "base_priority": 72,
                "message": "Trap risk elevated",
            }
        )
    if bool(auto_exit.get("exit_signal")):
        candidate_signals.append(
            {
                "type": "exit_signal",
                "base_priority": 78,
                "message": str(auto_exit.get("exit_reason") or "Consider protecting open gains"),
            }
        )
    if bool(wall_break.get("wall_break_signal")) and wall_break.get("wall_break_reason"):
        candidate_signals.append(
            {
                "type": "breakout",
                "base_priority": 82,
                "message": str(wall_break.get("wall_break_reason")),
            }
        )
    prioritized = prioritize_signals(
        signals=candidate_signals,
        confidence=float(decision.get("confidence", 50.0) or 50.0),
        regime=str(decision.get("regime", "Range") or "Range"),
        projection=str(decision.get("projection", "") or ""),
        expiry_mode=bool(expiry_adaptive.get("expiry_mode")),
        session_phase=str(target.get("session_phase", "Transition") or "Transition"),
        reversal_probability=float(reversal_prob.get("reversal_probability", 0) or 0),
    )
    suppression_reason_map.update(
        {
            f"signal:{k}": v
            for k, v in (prioritized.get("suppression_reason_map", {}) or {}).items()
            if isinstance(k, str) and isinstance(v, str)
        }
    )
    engine_scores = decision.get("engine_scores", {}) if isinstance(decision.get("engine_scores"), dict) else {}
    weight_distribution = (
        decision.get("weight_distribution", {})
        if isinstance(decision.get("weight_distribution"), dict)
        else {}
    )
    engine_debug_map: dict[str, dict[str, float]] = {}
    for key in ("oi", "volume", "breakout", "sr"):
        if key not in engine_scores or key not in weight_distribution:
            continue
        raw_score = float(engine_scores.get(key, 0.0))
        weight = float(weight_distribution.get(key, 0.0))
        engine_debug_map[key] = {
            "raw_score": round(raw_score, 4),
            "weight": round(weight, 4),
            "contribution": round(raw_score * weight, 4),
        }
    logger.debug(
        "Decision[%s %s] composite=%.4f smoothed=%.4f bias=%s conf=%.1f bull_force=%s bear_force=%s clarity=%s risk=%s state=%s weights=%s engine_map=%s",
        symbol,
        expiry or "AUTO",
        float(decision.get("composite_score", 0.0) or 0.0),
        float(decision.get("weighted_score", 0.0) or 0.0),
        stable_bias,
        float(decision.get("confidence", 0.0) or 0.0),
        (decision.get("directional_force") or {}).get("bull"),
        (decision.get("directional_force") or {}).get("bear"),
        decision.get("clarity"),
        decision.get("execution_risk"),
        decision.get("state"),
        decision.get("weight_distribution"),
        engine_debug_map,
    )
    logger.debug(
        "Alerts[%s %s] dominant=%s strong_bias=%s suppressed_counter=%d emitted=%d prioritized=%d suppression_reasons=%s",
        symbol,
        expiry or "AUTO",
        dominant_direction,
        strong_bias,
        suppressed_counter,
        len(typed_alerts),
        len(prioritized.get("prioritized_signals", [])),
        suppression_reason_map,
    )
    if no_edge:
        stable_bias = "Neutral"
        decision["primary_bias"] = "Neutral"
        decision["bias"] = "Neutral"
        decision["trade_action"] = "WAIT"
        decision["conflict_market_state"] = "NO_EDGE"
    summary_line = (
        f"Put writers defending {support_level}; upside momentum building."
        if stable_bias == "Bullish"
        else f"Call writers active near {resistance_level}; downside pressure holding."
        if stable_bias == "Bearish"
        else f"Price balancing between {support_level} and {resistance_level}; wait for cleaner move."
    )
    decision_explanation = (
        "Price has moved materially below support. Breakdown confirmation in progress."
        if bool(material_breach.get("support_broken"))
        else "Price has moved materially above resistance. Breakout confirmation in progress."
        if bool(material_breach.get("resistance_broken"))
        else "Trap risk elevated near key levels."
        if trap_probability_pct >= 60
        else summary_line
    )
    if momentum_score > 0.7:
        decision_explanation = f"{decision_explanation} Strong intraday price displacement detected."
    if decision.get("momentum_override_explanation"):
        decision_explanation = f"{decision_explanation} {decision.get('momentum_override_explanation')}"
    trap_stability_payload = _stabilize_trap_probability(
        new_trap_probability=float(trap.get("trap_probability_pct", 0.0) or 0.0),
        previous_state=previous_state,
    )
    _apply_stabilized_trap(trap, trap_stability_payload)
    trap_probability = float(trap.get("trap_probability_pct", 0.0) or 0.0)
    blocking_reason = _determine_blocking_reason(
        trade_action=str(decision.get("trade_action", "WAIT")),
        readiness_active=bool(decision.get("readiness_active", False)),
        trade_readiness=float(decision.get("trade_readiness", 0.0) or 0.0),
        trap_probability=trap_probability,
        absorption_detected=absorption_detected,
        absorption_wins=absorption_wins,
        material_breach=material_breach,
        conflict_market_state=str(decision.get("conflict_market_state", "") or ""),
        support_transition_badge=support_transition_badge,
        resistance_transition_badge=resistance_transition_badge,
        dps_adjusted=float(decision.get("dps_adjusted", 0.0) or 0.0),
    )
    winning_engine = _determine_winning_engine(
        trade_action=str(decision.get("trade_action", "WAIT")),
        blocking_reason=blocking_reason,
        material_breach=material_breach,
        absorption_wins=absorption_wins,
    )
    decision_confidence = _compute_decision_confidence(
        trade_readiness=float(decision.get("trade_readiness", 0.0) or 0.0),
        trap_probability=trap_probability,
        trade_action=str(decision.get("trade_action", "WAIT")),
        blocking_reason=blocking_reason,
        support_transition_badge=support_transition_badge,
        resistance_transition_badge=resistance_transition_badge,
        material_breach_confirmed=material_breach_confirmed,
    )
    resolved_reason = _derive_resolved_reason(
        trade_action=str(decision.get("trade_action", "WAIT")),
        blocking_reason=blocking_reason,
        material_breach=material_breach,
        support_absorption=support_absorption,
        pressure_state=str(decision.get("pressure_state", "") or ""),
        summary_line=summary_line,
    )
    readiness_v2 = _compute_readiness_v2(
        previous_state=previous_state,
        committed_regime=committed_regime,
        stabilized_regime_family=stabilized_regime_family,
        range_locked=range_locked,
        regime_hold_cycles=int(regime_stabilizer.get("regime_hold_cycles", 0) or 0),
        candidate_regime_count=int(next_candidate_regime_count),
        support_transition_badge=support_transition_badge,
        resistance_transition_badge=resistance_transition_badge,
        support_shift_cycle=int(support_reference_state.get("support_shift_cycle", 0) or 0),
        structural_state=structural_state,
        material_breach_confirmed=material_breach_confirmed,
        confirmation_type=confirmation_type,
        no_edge=no_edge,
        spot=spot,
        support_level=support_level,
        resistance_level=resistance_level,
        bias=stable_bias,
        session_phase=str(target.get("session_phase") or decision.get("session_phase") or "Transition"),
        breakout_probability_up=float(breakout_probability.get("upside", 0.0) or 0.0),
        breakout_probability_down=float(breakout_probability.get("downside", 0.0) or 0.0),
        support_zone_pressure=float(support_zone_pressure or 0.0),
        resistance_zone_pressure=float(resistance_zone_pressure or 0.0),
        trap_probability=trap_probability,
        trap_type=str(trap.get("trap_type") or ""),
        blocking_reason=blocking_reason,
        winning_engine=winning_engine,
        conflict_market_state=str(decision.get("conflict_market_state", "") or ""),
        absorption_wins=absorption_wins,
        oi_scenario=str(dps.get("oi_scenario") or ""),
        session_range_pct=float(dps.get("session_range_pct", 0.0) or 0.0),
    )
    # Readiness V2 is now the active readiness contract. Keep the explicit V2
    # fields for diagnostics, but promote them into the primary readiness keys
    # consumed by payloads, logs, and the frontend.
    decision["trade_readiness"] = readiness_v2["trade_readiness_v2"]
    decision["readiness_state"] = readiness_v2["readiness_state_v2"]
    decision["readiness_active"] = bool(readiness_v2["readiness_active_v2"])
    decision["readiness_model"] = "V2"
    decision["trade_readiness_v2"] = readiness_v2["trade_readiness_v2"]
    decision["readiness_state_v2"] = readiness_v2["readiness_state_v2"]
    decision["readiness_active_v2"] = bool(readiness_v2["readiness_active_v2"])
    decision["readiness_structure_quality"] = readiness_v2["readiness_structure_quality"]
    decision["readiness_directional_alignment"] = readiness_v2["readiness_directional_alignment"]
    decision["readiness_execution_quality"] = readiness_v2["readiness_execution_quality"]
    decision["readiness_risk_friction"] = readiness_v2["readiness_risk_friction"]
    decision["readiness_cap_reason"] = readiness_v2["readiness_cap_reason"]
    decision["readiness_floor_reason"] = readiness_v2["readiness_floor_reason"]
    decision["readiness_regime_used"] = readiness_v2["readiness_regime_used"]
    decision["readiness_regime_family_used"] = readiness_v2["readiness_regime_family_used"]
    decision["readiness_range_like_session"] = bool(readiness_v2["readiness_range_like_session"])
    decision["readiness_raw_score_v2"] = readiness_v2["readiness_raw_score_v2"]
    decision["readiness_invalid_sr_geometry"] = bool(readiness_v2["readiness_invalid_sr_geometry"])
    decision["readiness_smoothing_applied"] = bool(readiness_v2["readiness_smoothing_applied"])
    decision["readiness_transition_guard_applied"] = bool(
        readiness_v2.get("readiness_transition_guard_applied", False)
    )
    decision["readiness_active_on_threshold_effective"] = readiness_v2.get(
        "readiness_active_on_threshold_effective",
        READINESS_ACTIVE_ON_THRESHOLD,
    )

    # Re-evaluate range-lock/no-edge with the active readiness contract (V2).
    # Earlier pipeline stages may still run with pre-V2 readiness for regime
    # stabilization continuity, but published lock flags must follow spec:
    # trap >= 55 and readiness <= RANGE_LOCK_READINESS_MAX (45).
    range_lock_payload_v2 = _apply_range_lock_and_no_edge(
        raw_candidate_regime=str(decision.get("regime_candidate") or detected_committed_regime or committed_regime),
        structural_state=structural_state,
        trap_probability=trap_probability,
        trade_readiness=float(decision.get("trade_readiness", 0.0) or 0.0),
        breach_confirmed=material_breach_confirmed,
        pressure_state=str(decision.get("pressure_state", "") or ""),
        current_regime=committed_regime,
    )
    range_locked = bool(range_lock_payload_v2.get("range_locked", False))
    no_edge = bool(range_lock_payload_v2.get("no_edge", False))
    derived_market_state = str(range_lock_payload_v2.get("market_state") or derived_market_state or "")
    decision["range_locked"] = range_locked
    decision["no_edge"] = no_edge
    decision["market_state_marker"] = derived_market_state
    if no_edge:
        decision["trade_action"] = "WAIT"
        decision["projection"] = "No Confirmed Breakout"

    if not bool(decision.get("readiness_active", False)) and str(decision.get("trade_action", "")) in {
        "LONG BIAS",
        "SHORT BIAS",
        "BREAKOUT WATCH",
        "BREAKDOWN WATCH",
    }:
        decision["trade_action"] = "WAIT"

    near_threshold_points = max(30.0, min(75.0, float(features.get("strike_gap", 50.0) or 50.0) * 0.6))
    spc_state = _resolve_spc_state(
        spot=spot,
        support_level=_safe_float(support_level),
        resistance_level=_safe_float(resistance_level),
        support_broken=bool(material_breach.get("support_broken")),
        resistance_broken=bool(material_breach.get("resistance_broken")),
        material_breach_confirmed=bool(material_breach.get("material_breach_confirmed")),
        near_threshold_points=near_threshold_points,
    )
    move_quality = _resolve_move_quality(
        spc_state=spc_state,
        trap_probability=trap_probability,
        absorption_detected=absorption_detected,
        material_breach_confirmed=bool(material_breach.get("material_breach_confirmed")),
        support_transition_active=bool(support_transition_badge),
        resistance_transition_active=bool(resistance_transition_badge),
    )
    spc_decision = _derive_spc_decision(
        spc_state=spc_state,
        move_quality=move_quality,
        trade_readiness=float(decision.get("trade_readiness", 0.0) or 0.0),
        readiness_active=bool(decision.get("readiness_active", False)),
    )
    decision["spc_state"] = spc_state
    decision["move_quality"] = move_quality
    decision["spc_decision"] = spc_decision
    decision["trade_action"] = _map_spc_decision_to_trade_action(
        spc_decision=spc_decision,
        spc_state=spc_state,
        support_broken=bool(material_breach.get("support_broken")),
        resistance_broken=bool(material_breach.get("resistance_broken")),
        dps_adjusted=float(decision.get("dps_adjusted", 0.0) or 0.0),
        fallback_trade_action=str(decision.get("trade_action", "WAIT")),
    )
    if spc_decision == "DISTRUST" and str(decision.get("projection", "")).strip().lower() in {
        "upside breakout",
        "downside breakout",
        "potential breakout watch",
    }:
        decision["projection"] = "No Confirmed Breakout"

    # Keep action-reason telemetry consistent with the SPC decision layer.
    blocking_reason = _determine_blocking_reason(
        trade_action=str(decision.get("trade_action", "WAIT")),
        readiness_active=bool(decision.get("readiness_active", False)),
        trade_readiness=float(decision.get("trade_readiness", 0.0) or 0.0),
        trap_probability=trap_probability,
        absorption_detected=absorption_detected,
        absorption_wins=absorption_wins,
        material_breach=material_breach,
        conflict_market_state=str(decision.get("conflict_market_state", "") or ""),
        support_transition_badge=support_transition_badge,
        resistance_transition_badge=resistance_transition_badge,
        dps_adjusted=float(decision.get("dps_adjusted", 0.0) or 0.0),
    )
    winning_engine = _determine_winning_engine(
        trade_action=str(decision.get("trade_action", "WAIT")),
        blocking_reason=blocking_reason,
        material_breach=material_breach,
        absorption_wins=absorption_wins,
    )
    decision_confidence = _compute_decision_confidence(
        trade_readiness=float(decision.get("trade_readiness", 0.0) or 0.0),
        trap_probability=trap_probability,
        trade_action=str(decision.get("trade_action", "WAIT")),
        blocking_reason=blocking_reason,
        support_transition_badge=support_transition_badge,
        resistance_transition_badge=resistance_transition_badge,
        material_breach_confirmed=material_breach_confirmed,
    )
    resolved_reason = _derive_resolved_reason(
        trade_action=str(decision.get("trade_action", "WAIT")),
        blocking_reason=blocking_reason,
        material_breach=material_breach,
        support_absorption=support_absorption,
        pressure_state=str(decision.get("pressure_state", "") or ""),
        summary_line=summary_line,
    )

    signal_history = _update_signal_history(
        previous_state,
        timestamp=str(features.get("meta", {}).get("timestamp") or _utc_iso(event_timestamp) or ""),
        trade_action=str(decision.get("trade_action", "WAIT")),
        resolved_reason=resolved_reason,
        blocking_reason=blocking_reason,
        winning_engine=winning_engine,
        decision_confidence=decision_confidence,
    )
    trade_plan = generate_trade_plan(
        bias=stable_bias,
        probability_bull=float((decision.get("bull_probability", 0.5) or 0.5) * 100.0),
        confidence=float(decision.get("confidence", 50.0) or 50.0),
        support=support_level,
        resistance=resistance_level,
        target1=target.get("target_1"),
        target2=target.get("target_2"),
        trap_risk=int(expiry_adaptive["trap_risk"] or 0),
        volatility_state=decision.get("volatility_state"),
        spot=spot,
        spc_state=str(decision.get("spc_state") or ""),
        spc_decision=str(decision.get("spc_decision") or ""),
        trade_action=str(decision.get("trade_action") or "WAIT"),
        range_locked=bool(range_locked),
        no_edge=bool(no_edge),
    )

    support_zone = sr.get("support_range")
    if support_zone is None:
        support_zone = [sr.get("support", {}).get("immediate"), sr.get("support", {}).get("major")]
    resistance_zone = sr.get("resistance_range")
    if resistance_zone is None:
        resistance_zone = [sr.get("resistance", {}).get("immediate"), sr.get("resistance", {}).get("major")]
    playbook = generate_intraday_playbook(
        primary_bias=str(decision.get("primary_bias", stable_bias)),
        regime=str(committed_regime),
        trap_probability=trap_probability,
        market_structure_score=float(mss.get("market_structure_score", 0.0) or 0.0),
        support_zone=support_zone,
        resistance_zone=resistance_zone,
        expansion_target=target.get("primary_target"),
    )
    def _match_row(strike_value: float | None) -> dict[str, Any] | None:
        if strike_value is None:
            return None
        for row in rows:
            try:
                if float(row.get("strike")) == float(strike_value):
                    return row
            except (TypeError, ValueError):
                continue
        return None

    support_row = _match_row(support_level)
    resistance_row = _match_row(resistance_level)
    liquidity_map = build_liquidity_map(rows=rows, spot=spot)
    market_insight = generate_market_insight(
        support=support_level,
        resistance=resistance_level,
        support_center=sr.get("support_center"),
        resistance_center=sr.get("resistance_center"),
        support_zone_pressure=support_zone_pressure,
        resistance_zone_pressure=resistance_zone_pressure,
        oi_velocity=float(oi.get("oi_velocity_score", 0.0) or 0.0),
        volume_expansion=float(volume_expansion_score),
        trap_probability=trap_probability,
        market_structure_score=float(mss.get("market_structure_score", 0.0) or 0.0),
        spot=spot,
        pe_oi_change_near_support=(support_row or {}).get("PE_OIChangePct"),
        ce_oi_change_near_resistance=(resistance_row or {}).get("CE_OIChangePct"),
    )
    if bool(support_absorption.get("absorption_detected")) and support_absorption.get("message"):
        market_insight.setdefault("market_insight", []).append(str(support_absorption.get("message")))
    if bool(wall_break.get("wall_break_signal")) and wall_break.get("wall_break_reason"):
        market_insight.setdefault("market_insight", []).append(str(wall_break.get("wall_break_reason")))
        market_insight.setdefault("market_insight", []).append(
            "Upside breakout probability rising." if wall_break.get("wall_break_direction") == "upside" else "Downside breakout probability rising."
        )
    logger.debug(
        "Insight[%s %s] structure=%s insight=%s wall_break=%s",
        symbol,
        expiry or "AUTO",
        market_insight.get("institutional_structure"),
        market_insight.get("market_insight"),
        wall_break,
    )
    warmup_active = bool(trap.get("warmup_active", False))
    spot_sample_count = int(trap.get("spot_sample_count", 0) or 0)
    observation_window_seconds = int(trap.get("observation_window_seconds", 0) or 0)
    rejection_wick_score = float(trap.get("rejection_wick_score", 0.0) or 0.0)
    time_above_level_ratio = float(trap.get("time_above_level_ratio", 0.0) or 0.0)
    oi_shift_score_live = float(oi.get("oi_shift_score", oi.get("oi_strength", 0.0)) or 0.0)

    prev_wick_zero_streak = int((previous_state or {}).get("wick_zero_streak", 0) or 0)
    prev_oi_high_streak = int((previous_state or {}).get("oi_near_one_streak", 0) or 0)
    prev_vol_high_streak = int((previous_state or {}).get("volume_near_one_streak", 0) or 0)
    trap_hist_prev = [
        float(x)
        for x in ((previous_state or {}).get("trap_probability_history", []) or [])
        if isinstance(x, (int, float))
    ]
    trap_history = (trap_hist_prev + [float(trap_probability)])[-20:]

    wick_zero_streak = (prev_wick_zero_streak + 1) if ((not warmup_active) and rejection_wick_score <= 1e-6) else 0
    oi_near_one_streak = (prev_oi_high_streak + 1) if oi_shift_score_live >= 0.98 else 0
    volume_near_one_streak = (prev_vol_high_streak + 1) if float(volume_expansion_score) >= 0.98 else 0

    validation_warnings: list[str] = []
    if max(trap_history) < 40:
        validation_warnings.append("trap_probability_low_variance")
    if wick_zero_streak > 20:
        validation_warnings.append("rejection_wick_score_stuck_zero")
    if oi_near_one_streak > 20:
        validation_warnings.append("oi_shift_score_near_one_streak")
    if volume_near_one_streak > 20:
        validation_warnings.append("volume_expansion_score_near_one_streak")
    if validation_warnings:
        logger.warning(
            "ValidationWarnings[%s %s] %s",
            symbol,
            expiry,
            ",".join(validation_warnings),
        )

    response_warnings = _validate_response_consistency(
        rows=rows,
        support_level=support_level,
        resistance_level=resistance_level,
        stable_bias=stable_bias,
        market_structure_score=float(mss.get("market_structure_score", 0.0) or 0.0),
        structural_state=str(decision.get("structural_state") or ""),
        market_state_label=str(decision.get("market_state") or ""),
        conflict_market_state=str(decision.get("conflict_market_state") or ""),
        trap_state=str(decision.get("trap_state") or ""),
        no_edge=bool(decision.get("no_edge", False)),
        range_locked=bool(decision.get("range_locked", False)),
    )
    if response_warnings and _should_emit_response_warning(
        symbol=symbol,
        expiry=expiry,
        warnings=response_warnings,
        timestamp=evaluation_time,
    ):
        logger.warning(
            "ResponseWarnings[%s %s] %s",
            symbol,
            expiry,
            ",".join(response_warnings),
        )

    event_timestamp = evaluation_time or _parse_timestamp_utc(features.get("meta", {}).get("timestamp"))
    event_timestamp_ist = event_timestamp.astimezone(IST)
    minute_of_day = event_timestamp_ist.hour * 60 + event_timestamp_ist.minute
    opening_window_start = 9 * 60 + 15
    opening_window_end = 9 * 60 + 30
    in_opening_window = opening_window_start <= minute_of_day < opening_window_end
    spot_value = _safe_float(spot)
    session_high_value = _safe_float(day_high)
    session_low_value = _safe_float(day_low)
    prev_opening_high = _safe_float((previous_state or {}).get("opening_range_high"))
    prev_opening_low = _safe_float((previous_state or {}).get("opening_range_low"))

    opening_high_candidates = [value for value in (prev_opening_high, session_high_value, spot_value) if value is not None]
    opening_low_candidates = [value for value in (prev_opening_low, session_low_value, spot_value) if value is not None]
    if in_opening_window:
        opening_range_high = max(opening_high_candidates) if opening_high_candidates else None
        opening_range_low = min(opening_low_candidates) if opening_low_candidates else None
    else:
        opening_range_high = prev_opening_high
        opening_range_low = prev_opening_low

    intraday_zones = get_intraday_zones(
        session_high=session_high_value,
        session_low=session_low_value,
        opening_high=opening_range_high,
        opening_low=opening_range_low,
        spot=spot_value,
        previous_close=_safe_float(previous_close),
        vwap=_safe_float(features.get("vwap")),
    )

    event_messages: list[str] = []
    if bool(material_breach.get("resistance_broken")):
        event_messages.append("Resistance break")
    if bool(material_breach.get("support_broken")):
        event_messages.append("Support break")
    if str(decision.get("conflict_market_state", "") or "").strip().lower() in {"compression", "range conflict"}:
        event_messages.append("Range compression")
    if float(oi.get("oi_velocity_score", 0.0) or 0.0) >= 0.8 or float(oi.get("oi_shift_score", oi.get("oi_strength", 0.0)) or 0.0) >= 0.85:
        event_messages.append("OI spike")
    previous_bias_for_event = str((previous_state or {}).get("previous_bias") or "Neutral")
    current_bias_for_event = str(decision.get("primary_bias", stable_bias) or stable_bias)
    if previous_bias_for_event not in {"", "Neutral"} and current_bias_for_event not in {"", "Neutral"} and current_bias_for_event != previous_bias_for_event:
        event_messages.append("Trend reversal")
    for event_message in event_messages:
        _emit_market_event(
            timestamp=event_timestamp,
            raw_event=event_message,
            symbol=symbol,
            expiry=expiry,
        )

    session_phase_payload = compute_session_phase(
        timestamp=event_timestamp,
        spot=spot,
        support=support_level,
        resistance=resistance_level,
        volatility_ratio=current_atr_ratio,
        range_compression_events_5m=_recent_event_count(
            symbol=symbol,
            expiry=expiry,
            raw_event="Range compression",
            minutes=5,
            timestamp=event_timestamp,
        ),
        oi_spike_events_5m=_recent_event_count(
            symbol=symbol,
            expiry=expiry,
            raw_event="OI spike",
            minutes=5,
            timestamp=event_timestamp,
        ),
        material_breach=material_breach,
        volume_expansion_score=volume_expansion_score,
        oi_shift_score=float(oi.get("oi_shift_score", oi.get("oi_strength", 0.0)) or 0.0),
    )
    # ── Greeks + Strike Guidance ──────────────────────────────────────────
    _raw_atm_iv = float((atm_row or {}).get("CE_IV", 0) or 0)
    atm_iv = _raw_atm_iv / 100.0 if _raw_atm_iv > 1.0 else _raw_atm_iv
    if atm_iv <= 0.001:
        atm_iv = 0.0
    if atm_iv > 0:
        _iv_history[symbol].append(atm_iv)
    iv_rank_result = compute_iv_rank(
        current_iv=atm_iv,
        iv_history=list(_iv_history[symbol]),
    )
    chain_greeks = compute_chain_greeks(
        rows=rows,
        spot=spot or 0,
        expiry_str=expiry or "",
        fallback_iv=atm_iv if atm_iv > 0 else None,
    )
    per_strike_liquidity_rows = _build_per_strike_liquidity_rows(rows)
    days_exp = chain_greeks[0]["ce"]["days_to_expiry"] if chain_greeks else 0
    _raw_atm_pe_iv = float((atm_row or {}).get("PE_IV", 0) or 0)
    atm_pe_iv = _raw_atm_pe_iv / 100.0 if _raw_atm_pe_iv > 1.0 else _raw_atm_pe_iv
    if atm_pe_iv <= 0.001:
        atm_pe_iv = 0.0
    strike_intelligence = compute_strike_intelligence(
        {
            "spot": float(spot or 0.0),
            "support": float(support_level or 0.0),
            "resistance": float(resistance_level or 0.0),
            "strike_gap": int(float(features.get("strike_gap", 50.0) or 50.0)),
            "chain_greeks": chain_greeks,
            "liquidity_map": per_strike_liquidity_rows,
            "iv_rank": float(iv_rank_result.get("iv_rank") or 0.0),
            "iv_percentile": float(iv_rank_result.get("iv_percentile") or 0.0),
            "atm_ce_iv": float(atm_iv or 0.0),
            "atm_pe_iv": float(atm_pe_iv or 0.0),
            "prev_straddle_premium": (previous_state or {}).get("prev_straddle_premium"),
            "trap_probability": float(trap_probability or 0.0),
            "trap_direction": str(trap_direction or ""),
            "bias": str(stable_bias or "Neutral"),
            "session_phase": str(session_phase_payload.get("session_phase", "")),
            "days_to_expiry": int(days_exp or 0),
            "oi_scenario": str(decision.get("oi_scenario") or ""),
            "defense_ratio_ce": float((sr.get("resistance", {}) or {}).get("defense_score") or 0.0),
            "defense_ratio_pe": float((sr.get("support", {}) or {}).get("defense_score") or 0.0),
        }
    )
    directional_entry_signal = strike_intelligence.get("directional_signal", "WAIT")
    legacy_entry_signal = strike_intelligence.get("entry_signal", "WAIT_NO_SETUP")
    entry_target = compute_entry_target(
        {
            "spot": float(spot or 0.0),
            "support": float(support_level or 0.0),
            "resistance": float(resistance_level or 0.0),
            "strike_gap": int(float(features.get("strike_gap", 50.0) or 50.0)),
            "put_wall": float((liquidity_map or {}).get("put_wall") or 0.0),
            "call_wall": float((liquidity_map or {}).get("call_wall") or 0.0),
            "max_pain_strike": strike_intelligence.get("max_pain_strike"),
            "defense_ratio_ce": float((sr.get("resistance", {}) or {}).get("defense_score") or 0.0),
            "defense_ratio_pe": float((sr.get("support", {}) or {}).get("defense_score") or 0.0),
            "liquidity_map": per_strike_liquidity_rows,
            "chain_greeks": chain_greeks,
            "trap_probability": float(trap_probability or 0.0),
            "bias": str(stable_bias or "Neutral"),
            "oi_scenario": str(decision.get("oi_scenario") or ""),
            "session_phase": str(session_phase_payload.get("session_phase", "")),
            "days_to_expiry": int(days_exp or 0),
            "iv_rank": float(iv_rank_result.get("iv_rank") or 0.0),
            "atm_straddle_premium": strike_intelligence.get("atm_straddle_premium"),
            "entry_signal": (
                directional_entry_signal
                if directional_entry_signal not in ("WAIT", "WAIT_NO_SETUP", None)
                else legacy_entry_signal
            ),
            "price_magnet_strike": strike_intelligence.get("price_magnet_strike"),
            "magnet_pull_direction": strike_intelligence.get("magnet_pull_direction"),
            "magnet_distance_pts": strike_intelligence.get("magnet_distance_pts"),
            "secondary_magnet": strike_intelligence.get("secondary_magnet"),
            "magnet_character": strike_intelligence.get("magnet_character"),
            "compression_zone": strike_intelligence.get("compression_zone"),
        }
    )
    strike_guidance = generate_strike_guidance(
        trade_action=str(decision.get("trade_action", "WAIT")),
        readiness_active=bool(readiness_v2.get("readiness_active_v2", False)),
        trap_probability=float(trap_probability or 0),
        session_phase=str(session_phase_payload.get("session_phase", "")),
        days_to_expiry=days_exp,
        iv_rank=iv_rank_result.get("iv_rank"),
        chain_greeks=chain_greeks,
        bias=str(stable_bias or "Neutral"),
        support=support_level,
        resistance=resistance_level,
        spc_state=str(decision.get("spc_state") or ""),
        execution_mode=str(trade_plan.get("trade_plan", {}).get("execution_mode") or ""),
        delta_guidance=str(trade_plan.get("trade_plan", {}).get("delta_strike_guidance") or ""),
        avoid_buying_premium=bool(trade_plan.get("trade_plan", {}).get("avoid_buying_premium", False)),
        entry_zone=str(trade_plan.get("trade_plan", {}).get("entry_zone") or ""),
        stop_zone=str(trade_plan.get("trade_plan", {}).get("stop_zone") or ""),
        target_zone=str(trade_plan.get("trade_plan", {}).get("target_zone") or ""),
        position_size_fraction=_safe_float(trade_plan.get("trade_plan", {}).get("position_size_fraction")),
        position_size_label=str(trade_plan.get("trade_plan", {}).get("position_size_label") or ""),
    )

    session_phase_payload = _stabilize_session_phase(
        current_phase=session_phase_payload.get("session_phase"),
        current_confidence=session_phase_payload.get("confidence"),
        timestamp=event_timestamp,
        previous_state=previous_state,
    )

    cycle_log_entry = {
        "timestamp": features.get("meta", {}).get("timestamp"),
        "symbol": symbol,
        "expiry": expiry,
        "spot_price": spot,
        "primary_bias": decision.get("primary_bias", stable_bias),
        "micro_bias": decision.get("micro_bias", stable_bias),
        "drift": decision.get("drift", "Stable"),
        "directional_force": decision.get("directional_force", {}),
        "clarity": decision.get("clarity"),
        "execution_risk": decision.get("execution_risk"),
        "trap_probability": trap_probability,
        "trap_level": trap.get("trap_level") or _trap_level_from_probability(trap_probability),
        "trap_state": trap.get("trap_state"),
        "trap_type": trap.get("trap_type"),
        "trap_hysteresis_applied": bool(trap.get("trap_hysteresis_applied", False)),
        "directional_signal": strike_intelligence.get("directional_signal"),
        "directional_bias": strike_intelligence.get("directional_bias"),
        "directional_rr": strike_intelligence.get("directional_rr"),
        "range_trap_cap_applied": range_trap_cap_applied,
        "range_trap_cap_reason": range_trap_cap_reason,
        "range_trap_cap_stage": range_trap_cap_stage,
        "stale_resistance_discount_applied": bool(stale_resistance_discount_applied),
        "stale_resistance_discount_points": round(float(stale_resistance_discount_points), 2),
        "seconds_above_resistance": int(seconds_above_resistance),
        "stale_break_window_met": bool(stale_break_window_met),
        "oi_imbalance_trap_probability": int(oi_imbalance_trap.get("trap_probability", 0) or 0),
        "oi_imbalance_trap_reason": oi_imbalance_trap.get("trap_reason"),
        "oi_imbalance_support_strength": int(oi_imbalance_trap.get("support_strength", 0) or 0),
        "oi_imbalance_support_reason": oi_imbalance_trap.get("support_reason"),
        "support_level": support_level,
        "resistance_level": resistance_level,
        "sr_first_cycle_after_reset": bool(sr.get("sr_first_cycle_after_reset", False)),
        "sr_cold_start_guard_applied": bool(sr_guard.get("sr_cold_start_guard_applied", False)),
        "sr_previous_support_anchor_used": sr_guard.get("sr_previous_support_anchor_used"),
        "sr_previous_support_anchor_source": sr_guard.get("sr_previous_support_anchor_source"),
        "sr_previous_resistance_anchor_used": sr_guard.get("sr_previous_resistance_anchor_used"),
        "sr_previous_resistance_anchor_source": sr_guard.get("sr_previous_resistance_anchor_source"),
        "sr_support_buffer_blocked": bool(sr_guard.get("sr_support_buffer_blocked", False)),
        "sr_resistance_buffer_blocked": bool(sr_guard.get("sr_resistance_buffer_blocked", False)),
        "previous_support": support_reference_state.get("previous_support"),
        "current_support": support_reference_state.get("current_support"),
        "previous_resistance": support_reference_state.get("previous_resistance"),
        "current_resistance": support_reference_state.get("current_resistance"),
        "sr_anchor_age_seconds": support_reference_state.get("sr_anchor_age_seconds"),
        "seeded_flush_last_fired_at": _last_seeded_flush_ist.isoformat() if _last_seeded_flush_ist else None,
        "cycle_count_since_flush": int(_cycle_count_since_flush),
        "absorption_reference_level": support_reference_state.get("absorption_reference_level"),
        "support_shift_cycle": support_reference_state.get("support_shift_cycle"),
        "sr_breach_state": sr_breach_state,
        "support_zone_pressure": round(float(support_zone_pressure), 2),
        "support_zone_state": support_zone_state,
        "resistance_zone_pressure": round(float(resistance_zone_pressure), 2),
        "resistance_zone_state": resistance_zone_state,
        "breakout_strength": round(float(breakout_strength), 4),
        "breakout_candidate": breakout_candidate,
        "rejection_wick_score": rejection_wick_score,
        "time_above_level_ratio": time_above_level_ratio,
        "oi_shift_score": float(oi.get("oi_shift_score", oi.get("oi_strength", 0.0)) or 0.0),
        "oi_velocity_score": float(oi.get("oi_velocity_score", 0.0) or 0.0),
        "volume_expansion_score": round(float(volume_expansion_score), 4),
        "warmup_active": warmup_active,
        "spot_sample_count": spot_sample_count,
        "observation_window_seconds": observation_window_seconds,
        "price_momentum_score": round(float(price_momentum_score), 4),
        "alignment_score": round(float(alignment_score), 4),
        "directional_pressure_score": decision.get("directional_pressure_score"),
        "dps_adjusted": decision.get("dps_adjusted"),
        "oi_scenario": decision.get("oi_scenario"),
        "dps_scenario_multiplier": decision.get("dps_scenario_multiplier"),
        "spc_state": decision.get("spc_state"),
        "move_quality": decision.get("move_quality"),
        "spc_decision": decision.get("spc_decision"),
        "execution_mode": trade_plan.get("trade_plan", {}).get("execution_mode"),
        "delta_band": trade_plan.get("trade_plan", {}).get("delta_band"),
        "delta_strike_guidance": trade_plan.get("trade_plan", {}).get("delta_strike_guidance"),
        "entry_zone": trade_plan.get("trade_plan", {}).get("entry_zone"),
        "stop_zone": trade_plan.get("trade_plan", {}).get("stop_zone"),
        "target_zone": trade_plan.get("trade_plan", {}).get("target_zone"),
        "pinning_active": bool(decision.get("pinning_active", False)),
        "pinning_trap_modifier_points": decision.get("pinning_trap_modifier_points"),
        "reversal_decay_cycles": decision.get("reversal_decay_cycles"),
        "pressure_state": decision.get("pressure_state"),
        "trade_action": decision.get("trade_action"),
        "trade_readiness": decision.get("trade_readiness"),
        "readiness_state": decision.get("readiness_state"),
        "readiness_active": bool(decision.get("readiness_active", False)),
        "readiness_model": decision.get("readiness_model"),
        "trade_readiness_v2": decision.get("trade_readiness_v2"),
        "readiness_state_v2": decision.get("readiness_state_v2"),
        "readiness_active_v2": bool(decision.get("readiness_active_v2", False)),
        "readiness_structure_quality": decision.get("readiness_structure_quality"),
        "readiness_directional_alignment": decision.get("readiness_directional_alignment"),
        "readiness_execution_quality": decision.get("readiness_execution_quality"),
        "readiness_risk_friction": decision.get("readiness_risk_friction"),
        "readiness_cap_reason": decision.get("readiness_cap_reason"),
        "readiness_floor_reason": decision.get("readiness_floor_reason"),
        "readiness_regime_used": decision.get("readiness_regime_used"),
        "readiness_regime_family_used": decision.get("readiness_regime_family_used"),
        "readiness_range_like_session": bool(decision.get("readiness_range_like_session", False)),
        "readiness_raw_score_v2": decision.get("readiness_raw_score_v2"),
        "readiness_invalid_sr_geometry": bool(decision.get("readiness_invalid_sr_geometry", False)),
        "readiness_smoothing_applied": bool(decision.get("readiness_smoothing_applied", False)),
        "readiness_transition_guard_applied": bool(
            decision.get("readiness_transition_guard_applied", False)
        ),
        "resolved_reason": resolved_reason,
        "blocking_reason": blocking_reason,
        "winning_engine": winning_engine,
        "decision_confidence": decision_confidence,
        "support_transition_badge": support_transition_badge,
        "resistance_transition_badge": resistance_transition_badge,
        "raw_candidate_regime": raw_candidate_regime,
        "candidate_regime_after_range_lock": candidate_regime_after_range_lock,
        "stabilized_regime_family": stabilized_regime_family,
        "range_locked": range_locked,
        "no_edge": no_edge,
        "regime_hold_cycles": int(regime_stabilizer.get("regime_hold_cycles", 0) or 0),
        "regime_candidate": next_candidate_regime,
        "regime_candidate_streak": int(next_candidate_regime_count),
        "regime_stabilizer_applied": True,
        "regime_state": decision.get("state"),
        "regime_hold_count": decision.get("regime_hold_count"),
        "regime_zone": decision.get("regime_zone"),
        "momentum_override_score": decision.get("momentum_override_score"),
        "momentum_override_explanation": decision.get("momentum_override_explanation"),
        "market_structure_score": mss.get("market_structure_score"),
        "mss_score": mss.get("market_structure_score"),
        "structure_state": mss.get("structure_state"),
        "structural_state": decision.get("state") or mss.get("structure_state"),
        "structure_bias": decision.get("structure_bias"),
        "breakout_probability": breakout_probability,
        "validation_warnings": validation_warnings,
        "engine_contribution_map": engine_debug_map,
        "previous_bias": stability.get("previous_bias"),
        "new_bias": stability.get("new_bias"),
        "previous_projection": stability.get("previous_projection"),
        "new_projection": stability.get("new_projection"),
        "smoothed_mss": mss.get("market_structure_score"),
        "conflict_flags": list(conflict_resolver.get("conflict_flags") or []),
        "bias_change_counter": int(bias_change_counter),
        "projection_change_counter": int(projection_change_counter),
        "bias_stability_cycles": int(bias_stability_cycles),
        "persistence_drift": str(persistence_drift),
        "volatility_factor": float(
            trap.get("volatility_factor")
            if trap.get("volatility_factor") is not None
            else max(0.0, min(1.0, abs(float(current_atr_ratio) - 1.0)))
        ),
        "institutional_structure": market_insight.get("institutional_structure"),
        "market_insight": market_insight.get("market_insight", []),
        "wall_break": wall_break,
        "liquidity_map": liquidity_map,
        "support_absorption": support_absorption,
        "session_phase": session_phase_payload.get("session_phase"),
        "session_phase_confidence": session_phase_payload.get("confidence"),
    }
    log_key = _cache_key(symbol=symbol, instrument_type=INSTRUMENT_TYPE, expiry=expiry)
    if _should_log_cycle(log_key):
        _append_cycle_log(cycle_log_entry)

    _spot_val = float(spot or 0)
    if _spot_val > 0 and chain_greeks:
        _sorted = sorted(chain_greeks, key=lambda row: abs(float(row.get("strike", 0) or 0) - _spot_val))
        _atm_centered = sorted(_sorted[:20], key=lambda row: float(row.get("strike", 0) or 0))
    else:
        _atm_centered = chain_greeks[:20]

    return {
        "is_complete": True,
        "meta": features["meta"],
        "warnings": response_warnings,
        "institutional_structure": market_insight.get("institutional_structure"),
        "market_insight": market_insight.get("market_insight", []),
        "wall_break": wall_break,
        "liquidity_map": liquidity_map,
        "support_absorption": support_absorption,
        "previous_support": support_reference_state.get("previous_support"),
        "current_support": support_reference_state.get("current_support"),
        "previous_resistance": support_reference_state.get("previous_resistance"),
        "current_resistance": support_reference_state.get("current_resistance"),
        "absorption_reference_level": support_reference_state.get("absorption_reference_level"),
        "_internal": {
            "smoothed_score": decision.get("weighted_score"),
        },
        "decision_engine": {
            "directional_pressure_score": decision.get("directional_pressure_score"),
            "dps_adjusted": decision.get("dps_adjusted"),
            "oi_scenario": decision.get("oi_scenario"),
            "dps_scenario_multiplier": decision.get("dps_scenario_multiplier"),
            "spc_state": decision.get("spc_state"),
            "move_quality": decision.get("move_quality"),
            "spc_decision": decision.get("spc_decision"),
            "pinning_active": bool(decision.get("pinning_active", False)),
            "pinning_trap_modifier_points": decision.get("pinning_trap_modifier_points"),
            "reversal_decay_cycles": int(decision.get("reversal_decay_cycles", 0) or 0),
            "pressure_state": decision.get("pressure_state"),
            "trade_action": decision.get("trade_action"),
            "pressure_explanation": decision.get("pressure_explanation"),
        },
        "market_state": {
            "volatility_state": decision.get("volatility_state"),
            "bias": stable_bias,
            "probability_bull": round(float((decision.get("bull_probability", 0.5) or 0.5) * 100.0), 2),
            "probability_bear": round(float((decision.get("bear_probability", 0.5) or 0.5) * 100.0), 2),
            "confidence": float(decision.get("confidence", 50.0) or 50.0),
            "composite_score": float(decision.get("composite_score", 0.0) or 0.0),
            "directional_force": decision.get("directional_force", {}),
            "directional_force_value": float(decision.get("directional_force_value", 0.0) or 0.0),
            "clarity": float(decision.get("clarity", decision.get("structural_clarity_score", 0.0)) or 0.0),
            "execution_risk": float(decision.get("execution_risk", 0.0) or 0.0),
            "risk": float(decision.get("risk", decision.get("execution_risk", 0.0)) or 0.0),
            "state": str(decision.get("state", "")),
            "transition_phase": bool(decision.get("transition_phase", False)),
            "projection": str(decision.get("projection", "No Confirmed Breakout")),
            "regime_hint": decision.get("regime_hint"),
            "conflict_market_state": str(decision.get("conflict_market_state", "Balanced")),
            "conflict_flags": list(decision.get("conflict_flags", [])),
            "primary_bias": str(decision.get("primary_bias", stable_bias)),
            "micro_bias": str(decision.get("micro_bias", stable_bias)),
            "framework_status": str(decision.get("framework_status", "Stable")),
            "drift": str(decision.get("drift", "Stable")),
            "regime_state": str(decision.get("state", "")),
            "regime_candidate": str(decision.get("regime_candidate", "")),
            "regime_hold_count": int(decision.get("regime_hold_count", 0) or 0),
            "regime_zone": str(decision.get("regime_zone", "")),
            "bias_stability_cycles": int(bias_stability_cycles),
            "bias_change_counter": int(bias_change_counter),
            "last_primary_update_time": decision.get("last_primary_update_time"),
            "rolling_force_history": decision.get("rolling_force_history", []),
            "rolling_clarity_history": decision.get("rolling_clarity_history", []),
            "retail_mapping": decision.get("retail_mapping", {}),
            "engine_contributions": decision.get("engine_contributions", {}),
            "engine_scores": decision.get("engine_scores", {}),
            "adaptive_mode": "Active" if allow_adaptation else "Base",
            "adaptive_weights": decision.get("weight_distribution", base_weights),
            "day_trend": day_trend,
            "long_trend": long_trend,
            "session_phase": session_phase_payload.get("session_phase"),
            "iv_rank": iv_rank_result.get("iv_rank"),
            "iv_context": iv_rank_result.get("iv_context"),
            "selling_favoured": iv_rank_result.get("selling_favoured"),
            "strike_guidance": strike_guidance,
            "strike_intelligence": strike_intelligence,
            "entry_target": entry_target,
            "trade_side": strike_intelligence.get("trade_side"),
            "trade_side_reason": strike_intelligence.get("trade_side_reason"),
            "entry_signal": strike_intelligence.get("entry_signal"),
            "entry_signal_reason": strike_intelligence.get("entry_signal_reason"),
            "entry_signal_strength": strike_intelligence.get("entry_signal_strength"),
            "recommended_strike": strike_intelligence.get("recommended_strike"),
            "recommended_option": strike_intelligence.get("recommended_option"),
            "recommended_action": strike_intelligence.get("recommended_action"),
            "delta_target_min": strike_intelligence.get("delta_target_min"),
            "delta_target_max": strike_intelligence.get("delta_target_max"),
            "position_size_fraction": strike_intelligence.get("position_size_fraction"),
            "stop_description": strike_intelligence.get("stop_description"),
            "target_description": strike_intelligence.get("target_description"),
            "max_pain_strike": strike_intelligence.get("max_pain_strike"),
            "price_magnet_strike": strike_intelligence.get("price_magnet_strike"),
            "price_magnet_combined": strike_intelligence.get("price_magnet_combined"),
            "magnet_pull_direction": strike_intelligence.get("magnet_pull_direction"),
            "magnet_distance_pts": strike_intelligence.get("magnet_distance_pts"),
            "secondary_magnet": strike_intelligence.get("secondary_magnet"),
            "between_magnets": strike_intelligence.get("between_magnets"),
            "magnet_character": strike_intelligence.get("magnet_character"),
            "compression_zone": strike_intelligence.get("compression_zone"),
            "max_pain_pull": strike_intelligence.get("max_pain_pull"),
            "iv_skew": strike_intelligence.get("iv_skew"),
            "atm_straddle_premium": strike_intelligence.get("atm_straddle_premium"),
            "straddle_trend": strike_intelligence.get("straddle_trend"),
            "ce_wall_holding": strike_intelligence.get("ce_wall_holding"),
            "pe_wall_holding": strike_intelligence.get("pe_wall_holding"),
            "volume_spike_strikes": strike_intelligence.get("volume_spike_strikes"),
            "session_phase_confidence": session_phase_payload.get("confidence"),
            "momentum_score": momentum_score,
            "momentum_direction": momentum_direction,
            "bias_stability_label": bias_stability.get("bias_stability_label"),
            "bias_stability_score": bias_stability.get("bias_stability_score"),
            "trap_risk": int(trap.get("trap_probability_pct", 0) or 0),
            "trap_state": str(trap.get("trap_state") or trap.get("trap_level") or ""),
            "trap_hysteresis_applied": bool(trap.get("trap_hysteresis_applied", False)),
            "range_trap_cap_applied": range_trap_cap_applied,
            "range_trap_cap_reason": range_trap_cap_reason,
            "range_trap_cap_stage": range_trap_cap_stage,
            "reversal_risk": reversal_risk,
            "support": support_level,
            "resistance": resistance_level,
            "material_breach": material_breach,
            "support_absorption": support_absorption,
            "previous_support": support_reference_state.get("previous_support"),
            "current_support": support_reference_state.get("current_support"),
            "previous_resistance": support_reference_state.get("previous_resistance"),
            "current_resistance": support_reference_state.get("current_resistance"),
            "sr_first_cycle_after_reset": bool(sr.get("sr_first_cycle_after_reset", False)),
            "sr_cold_start_guard_applied": bool(sr_guard.get("sr_cold_start_guard_applied", False)),
            "sr_previous_support_anchor_used": sr_guard.get("sr_previous_support_anchor_used"),
            "sr_previous_support_anchor_source": sr_guard.get("sr_previous_support_anchor_source"),
            "sr_previous_resistance_anchor_used": sr_guard.get("sr_previous_resistance_anchor_used"),
            "sr_previous_resistance_anchor_source": sr_guard.get("sr_previous_resistance_anchor_source"),
            "sr_support_buffer_blocked": bool(sr_guard.get("sr_support_buffer_blocked", False)),
            "sr_resistance_buffer_blocked": bool(sr_guard.get("sr_resistance_buffer_blocked", False)),
            "sr_anchor_age_seconds": support_reference_state.get("sr_anchor_age_seconds"),
            "seeded_flush_last_fired_at": _last_seeded_flush_ist.isoformat() if _last_seeded_flush_ist else None,
            "cycle_count_since_flush": int(_cycle_count_since_flush),
            "absorption_reference_level": support_reference_state.get("absorption_reference_level"),
            "support_shift_cycle": support_reference_state.get("support_shift_cycle"),
            "support_transition_active": _is_support_transition_active(
                support_reference_state.get("support_shift_cycle", 0)
            ),
            "support_transition_badge": support_transition_badge,
            "resistance_transition_badge": resistance_transition_badge,
            "absorption_detected": bool(support_absorption.get("absorption_detected")),
            "absorption_level": support_absorption.get("level"),
            "absorption_message": support_absorption.get("message"),
            "support_zone_pressure": round(float(support_zone_pressure), 2),
            "support_zone_state": support_zone_state,
            "resistance_zone_pressure": round(float(resistance_zone_pressure), 2),
            "resistance_zone_state": resistance_zone_state,
            "target1": target.get("target_1"),
            "target2": target.get("target_2"),
            "entry_zone": trade_plan.get("trade_plan", {}).get("entry_zone"),
            "stop_zone": trade_plan.get("trade_plan", {}).get("stop_zone"),
            "target_zone": trade_plan.get("trade_plan", {}).get("target_zone"),
            "execution_mode": trade_plan.get("trade_plan", {}).get("execution_mode"),
            "delta_band": trade_plan.get("trade_plan", {}).get("delta_band"),
            "delta_strike_guidance": trade_plan.get("trade_plan", {}).get("delta_strike_guidance"),
            "avoid_buying_premium": bool(trade_plan.get("trade_plan", {}).get("avoid_buying_premium", False)),
            "summary_line": summary_line,
            "decision_explanation": decision_explanation,
            "resolved_reason": resolved_reason,
            "blocking_reason": blocking_reason,
            "winning_engine": winning_engine,
            "decision_confidence": decision_confidence,
            "sr_breach_state": sr_breach_state,
            "alignment_score": round(float(alignment_score), 4),
            "directional_pressure_score": decision.get("directional_pressure_score"),
            "dps_adjusted": decision.get("dps_adjusted"),
            "oi_scenario": decision.get("oi_scenario"),
            "dps_scenario_multiplier": decision.get("dps_scenario_multiplier"),
            "spc_state": decision.get("spc_state"),
            "move_quality": decision.get("move_quality"),
            "spc_decision": decision.get("spc_decision"),
            "pinning_active": bool(decision.get("pinning_active", False)),
            "pinning_trap_modifier_points": decision.get("pinning_trap_modifier_points"),
            "reversal_decay_cycles": int(decision.get("reversal_decay_cycles", 0) or 0),
            "pressure_state": decision.get("pressure_state"),
            "trade_action": decision.get("trade_action"),
            "trade_readiness": decision.get("trade_readiness"),
            "readiness_state": decision.get("readiness_state"),
            "readiness_active": bool(decision.get("readiness_active", False)),
            "readiness_model": decision.get("readiness_model"),
            "directional_signal": strike_intelligence.get("directional_signal"),
            "directional_bias": strike_intelligence.get("directional_bias"),
            "directional_rr": strike_intelligence.get("directional_rr"),
            "trade_readiness_v2": decision.get("trade_readiness_v2"),
            "readiness_state_v2": decision.get("readiness_state_v2"),
            "readiness_active_v2": bool(decision.get("readiness_active_v2", False)),
            "readiness_structure_quality": decision.get("readiness_structure_quality"),
            "readiness_directional_alignment": decision.get("readiness_directional_alignment"),
            "readiness_execution_quality": decision.get("readiness_execution_quality"),
        "readiness_risk_friction": decision.get("readiness_risk_friction"),
        "readiness_cap_reason": decision.get("readiness_cap_reason"),
        "readiness_floor_reason": decision.get("readiness_floor_reason"),
        "readiness_regime_used": decision.get("readiness_regime_used"),
        "readiness_regime_family_used": decision.get("readiness_regime_family_used"),
        "readiness_range_like_session": bool(decision.get("readiness_range_like_session", False)),
        "readiness_raw_score_v2": decision.get("readiness_raw_score_v2"),
        "readiness_invalid_sr_geometry": bool(decision.get("readiness_invalid_sr_geometry", False)),
        "readiness_smoothing_applied": bool(decision.get("readiness_smoothing_applied", False)),
        "market_state": derived_market_state or None,
            "range_locked": range_locked,
            "no_edge": no_edge,
            "raw_candidate_regime": raw_candidate_regime,
            "candidate_regime_after_range_lock": candidate_regime_after_range_lock,
            "stabilized_regime_family": stabilized_regime_family,
            "regime_hold_cycles": int(regime_stabilizer.get("regime_hold_cycles", 0) or 0),
            "regime_candidate_streak": int(next_candidate_regime_count),
            "regime_stabilizer_applied": True,
            "committed_regime": committed_regime,
            "detected_regime": detected_committed_regime,
            "last_detected_regime": detected_committed_regime,
            "candidate_regime": next_candidate_regime,
            "candidate_regime_count": int(next_candidate_regime_count),
            "momentum_override_score": decision.get("momentum_override_score"),
            "momentum_override_explanation": decision.get("momentum_override_explanation"),
            "breakout_candidate": breakout_candidate,
            "market_structure_score": mss.get("market_structure_score"),
            "mss_score": mss.get("market_structure_score"),
            "structure_state": mss.get("structure_state"),
            "structural_state": decision.get("state") or mss.get("structure_state"),
            "structure_bias": decision.get("structure_bias"),
            "breakout_probability": breakout_probability,
            "regime_state": str(decision.get("state", "")),
            "regime_candidate": str(decision.get("regime_candidate", "")),
            "regime_hold_count": int(decision.get("regime_hold_count", 0) or 0),
            "regime_zone": str(decision.get("regime_zone", "")),
            "signal_history": signal_history,
        },
        "levels": {
            "resistance": {
                "strike": sr.get("resistance", {}).get("strike"),
                "immediate": sr.get("resistance", {}).get("immediate"),
                "major": sr.get("resistance", {}).get("major"),
                "range": sr.get("resistance_range"),
                "zone_pressure": sr.get("resistance_zone_pressure"),
                "zone_state": sr.get("resistance_zone_state"),
                "score": sr.get("resistance", {}).get("score"),
                "levels": sr.get("resistance", {}).get("levels", []),
            },
            "support": {
                "strike": sr.get("support", {}).get("strike"),
                "immediate": sr.get("support", {}).get("immediate"),
                "major": sr.get("support", {}).get("major"),
                "range": sr.get("support_range"),
                "zone_pressure": sr.get("support_zone_pressure"),
                "zone_state": sr.get("support_zone_state"),
                "score": sr.get("support", {}).get("score"),
                "levels": sr.get("support", {}).get("levels", []),
            },
            # Backward compatibility aliases expected by older UI code.
            "resistance_strike": sr.get("resistance", {}).get("strike"),
            "support_strike": sr.get("support", {}).get("strike"),
            "target_1": target.get("target_1"),
            "target_2": target.get("target_2"),
            "acceleration_zone": target.get("acceleration_zone"),
        },
        "signals": {
            "oi": oi,
            "volume": volume,
            "sr": sr,
            "breakout": breakout,
            "trap": trap,
            "oi_imbalance_trap": oi_imbalance_trap,
            "material_breach": material_breach,
            "support_absorption": support_absorption,
            "breakout_candidate": breakout_candidate,
            "sr_breach_state": sr_breach_state,
            "alignment_filter": {
                "alignment_score": round(float(alignment_score), 4),
                "price_momentum": round(float(price_momentum_score), 4),
                "oi_shift_score": round(float(oi.get("oi_shift_score", oi_strength) or oi_strength), 4),
                "volume_expansion_score": round(float(volume_expansion_score), 4),
                "breakout_suppressed": breakout_suppressed,
            },
            "market_structure": mss,
            "conflict_resolver": conflict_resolver,
            "regime_shift": regime_shift,
            "momentum_exhaustion": momentum_exhaustion,
            "exhaustion_trap_combo": combo_detector,
            "early_reversal": reversal_prob,
            "auto_exit": auto_exit,
            "prioritized_signals": prioritized.get("prioritized_signals", []),
            "expiry_adaptive": expiry_adaptive,
            "intraday_zones": intraday_zones,
            "liquidity_map": per_strike_liquidity_rows,
            "chain_greeks": _atm_centered,
            "alerts": typed_alerts,
            "alerts_meta": {
                "strong_directional_bias": strong_bias,
                "dominant_direction": dominant_direction,
                "suppressed_count": suppressed_counter,
                "counter_trend_count": len([a for a in typed_alerts if a.get("type") == "counter"]),
                "suppression_reason_map": suppression_reason_map,
            },
            "validation_warnings": validation_warnings,
        },
        "advanced": {
            "writers_activity": {
                "ce_top": sr.get("resistance", {}).get("levels", [])[:3],
                "pe_top": sr.get("support", {}).get("levels", [])[:3],
            },
            "futures_basis": {"basis": None, "type": "Unavailable"},
            "shift_tracker": {"support_shift": 0, "resistance_shift": 0},
            "pinning_pct": 0,
            "expiry_risk": trap.get("trap_probability_pct", 0),
            "institutional_zones": [
                sr.get("support", {}).get("strike"),
                sr.get("resistance", {}).get("strike"),
            ],
        },
        "trade_plan": trade_plan.get("trade_plan", {}),
        "intraday_playbook": playbook,
        "_state": {
            "regime": current_regime,
            "alignment_ratio": current_alignment,
            "atr_ratio": current_atr_ratio,
            "spot": spot,
            "volume_ratio": round(current_volume_ratio, 4),
            "oi_delta": round(current_oi_delta, 4),
            "primary_bias": decision.get("primary_bias", stable_bias),
            "micro_bias": decision.get("micro_bias", stable_bias),
            "last_primary_update_time": decision.get("last_primary_update_time"),
            "rolling_force_history": decision.get("rolling_force_history", []),
            "rolling_clarity_history": decision.get("rolling_clarity_history", []),
            "spot_observations": trap.get("spot_observations", []),
            "oi_prev_value": (oi.get("oi_state", {}) or {}).get("oi_prev_value"),
            "oi_prev_ts": (oi.get("oi_state", {}) or {}).get("oi_prev_ts"),
            "oi_velocity_history": (oi.get("oi_state", {}) or {}).get("oi_velocity_history", []),
            "oi_shift_history": (oi.get("oi_state", {}) or {}).get("oi_shift_history", []),
            "volume_prev_ts": (volume.get("volume_state", {}) or {}).get("volume_prev_ts"),
            "volume_history": (volume.get("volume_state", {}) or {}).get("volume_history", []),
            "trap_raw_prev": round(float(trap.get("trap_smoothed", trap.get("trap_raw", 0.0)) or 0.0), 4),
            "trap_smoothed_prev": round(
                float(trap.get("trap_smoothed_prev", trap.get("trap_smoothed", trap.get("trap_raw", 0.0))) or 0.0), 4
            ),
            "prev_straddle_premium": strike_intelligence.get("atm_straddle_premium"),
            "trap_state": str(trap.get("trap_state") or trap.get("trap_level") or ""),
            "trap_trend_adjustment_applied": bool(trap.get("trap_trend_adjustment_applied", False)),
            "trap_hysteresis_applied": bool(trap.get("trap_hysteresis_applied", False)),
            "total_chain_oi": float(trap.get("total_chain_oi", 0.0) or 0.0),
            "previous_bias": stable_bias,
            "previous_projection": stable_projection,
            "bias_change_counter": int(bias_change_counter),
            "projection_change_counter": int(projection_change_counter),
            "bias_stability_cycles": int(bias_stability_cycles),
            "reversal_decay_cycles": int(decision.get("reversal_decay_cycles", 0) or 0),
            "market_structure_score_prev": float(mss.get("market_structure_score", 0.0) or 0.0),
            "force_strength": round(float(force_strength), 4),
            "material_breach": material_breach,
            "sr_breach_state": sr_breach_state,
            "regime_state": str(decision.get("state", "")),
            "regime_candidate": str(decision.get("regime_candidate", "")),
            "regime_hold_count": int(decision.get("regime_hold_count", 0) or 0),
            "regime_zone": str(decision.get("regime_zone", "")),
            "committed_regime": committed_regime,
            "detected_regime": detected_committed_regime,
            "candidate_regime": next_candidate_regime,
            "candidate_regime_count": int(next_candidate_regime_count),
            "raw_candidate_regime": raw_candidate_regime,
            "candidate_regime_after_range_lock": candidate_regime_after_range_lock,
            "stabilized_regime_family": stabilized_regime_family,
            "regime_hold_cycles": int(regime_stabilizer.get("regime_hold_cycles", 0) or 0),
            "regime_candidate_streak": int(next_candidate_regime_count),
            "regime_family": stabilized_regime_family,
            "range_locked": range_locked,
            "no_edge": no_edge,
            "range_trap_cap_applied": range_trap_cap_applied,
            "range_trap_cap_reason": range_trap_cap_reason,
            "range_trap_cap_stage": range_trap_cap_stage,
            "stale_resistance_discount_applied": bool(stale_resistance_discount_applied),
            "stale_resistance_discount_points": round(float(stale_resistance_discount_points), 2),
            "seconds_above_resistance": int(seconds_above_resistance),
            "stale_break_window_met": bool(stale_break_window_met),
            "trade_readiness": decision.get("trade_readiness"),
            "readiness_state": decision.get("readiness_state"),
            "readiness_active": bool(decision.get("readiness_active", False)),
            "readiness_model": decision.get("readiness_model"),
            "trade_readiness_v2": decision.get("trade_readiness_v2"),
            "readiness_state_v2": decision.get("readiness_state_v2"),
            "readiness_active_v2": bool(decision.get("readiness_active_v2", False)),
            "readiness_structure_quality": decision.get("readiness_structure_quality"),
            "readiness_directional_alignment": decision.get("readiness_directional_alignment"),
            "readiness_execution_quality": decision.get("readiness_execution_quality"),
            "readiness_risk_friction": decision.get("readiness_risk_friction"),
            "readiness_cap_reason": decision.get("readiness_cap_reason"),
            "readiness_floor_reason": decision.get("readiness_floor_reason"),
            "readiness_regime_used": decision.get("readiness_regime_used"),
            "readiness_regime_family_used": decision.get("readiness_regime_family_used"),
            "readiness_range_like_session": bool(decision.get("readiness_range_like_session", False)),
            "readiness_raw_score_v2": decision.get("readiness_raw_score_v2"),
            "readiness_invalid_sr_geometry": bool(decision.get("readiness_invalid_sr_geometry", False)),
            "readiness_smoothing_applied": bool(decision.get("readiness_smoothing_applied", False)),
            "readiness_transition_guard_applied": bool(
                decision.get("readiness_transition_guard_applied", False)
            ),
            "breakout_candidate": breakout_candidate,
            "previous_support": support_reference_state.get("previous_support"),
            "current_support": support_reference_state.get("current_support"),
            "previous_resistance": support_reference_state.get("previous_resistance"),
            "current_resistance": support_reference_state.get("current_resistance"),
            "sr_first_cycle_after_reset": False,
            "sr_cold_start_guard_applied": bool(sr_guard.get("sr_cold_start_guard_applied", False)),
            "sr_previous_support_anchor_used": sr_guard.get("sr_previous_support_anchor_used"),
            "sr_previous_support_anchor_source": sr_guard.get("sr_previous_support_anchor_source"),
            "sr_previous_resistance_anchor_used": sr_guard.get("sr_previous_resistance_anchor_used"),
            "sr_previous_resistance_anchor_source": sr_guard.get("sr_previous_resistance_anchor_source"),
            "sr_support_buffer_blocked": bool(sr_guard.get("sr_support_buffer_blocked", False)),
            "sr_resistance_buffer_blocked": bool(sr_guard.get("sr_resistance_buffer_blocked", False)),
            "sr_anchor_started_at_utc": support_reference_state.get("sr_anchor_started_at_utc"),
            "sr_anchor_age_seconds": support_reference_state.get("sr_anchor_age_seconds"),
            "seeded_flush_last_fired_at": _last_seeded_flush_ist.isoformat() if _last_seeded_flush_ist else None,
            "cycle_count_since_flush": int(_cycle_count_since_flush),
            "absorption_reference_level": support_reference_state.get("absorption_reference_level"),
            "support_shift_cycle": support_reference_state.get("support_shift_cycle"),
            "blocking_reason": blocking_reason,
            "winning_engine": winning_engine,
            "decision_confidence": decision_confidence,
            "resolved_reason": resolved_reason,
            "support_transition_badge": support_transition_badge,
            "resistance_transition_badge": resistance_transition_badge,
            "signal_history": signal_history,
            "wick_zero_streak": int(wick_zero_streak),
            "oi_near_one_streak": int(oi_near_one_streak),
            "volume_near_one_streak": int(volume_near_one_streak),
            "trap_probability_history": [round(float(x), 4) for x in trap_history],
            "session_phase": session_phase_payload.get("session_phase"),
            "session_phase_confidence": session_phase_payload.get("confidence"),
            "session_phase_session_key": session_phase_payload.get("session_key"),
            "session_date": session_phase_payload.get("session_key"),
            "opening_range_high": opening_range_high,
            "opening_range_low": opening_range_low,
            "levels": {
                "support": {
                    "immediate": sr.get("support", {}).get("immediate"),
                    "major": sr.get("support", {}).get("major"),
                    "immediate_score": sr.get("support", {}).get("immediate_score"),
                    "zone_pressure": sr.get("support_zone_pressure"),
                    "zone_state": sr.get("support_zone_state"),
                },
                "resistance": {
                    "immediate": sr.get("resistance", {}).get("immediate"),
                    "major": sr.get("resistance", {}).get("major"),
                    "immediate_score": sr.get("resistance", {}).get("immediate_score"),
                    "zone_pressure": sr.get("resistance_zone_pressure"),
                    "zone_state": sr.get("resistance_zone_state"),
                },
            },
        },
        "_adaptive_state": {
            "session_start_utc": session_start_dt.isoformat(),
            "last_recalc_utc": now_dt.isoformat() if recalc_due else (last_recalc_dt.isoformat() if last_recalc_dt else None),
            "weights": current_weights,
        },
    }


async def _build_symbol_payloads(
    symbol: str,
    instrument_type: str,
    requested_expiries: list[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    option_chain_section: dict[str, Any] = {}
    summary_section: dict[str, Any] = {}
    daily_context = await asyncio.to_thread(get_daily_context, symbol)

    if symbol.upper() in BSE_SYMBOLS:
        contract_info = await fetch_sensex_contract_info_async(symbol)
    else:
        contract_info = await _fetch_contract_info_async(symbol)
    expiries = list(contract_info.get("expiryDates", []))
    strikes = list(contract_info.get("strikePrice", []))

    option_chain_section["contract_info"] = {
        "symbol": symbol,
        "instrument_type": instrument_type,
        "expiries": expiries,
        "strikes": strikes,
    }
    option_chain_section["daily_context"] = daily_context

    active_expiries = _resolve_active_expiries(expiries)
    if requested_expiries:
        valid_expiries = {str(item) for item in expiries}
        expiries_to_fetch = [str(item) for item in requested_expiries if str(item) in valid_expiries]
    else:
        expiries_to_fetch = active_expiries[:MAX_EXPIRIES_PER_SYMBOL]
    if not expiries_to_fetch:
        return option_chain_section, summary_section

    for expiry in expiries_to_fetch:
        if symbol.upper() in BSE_SYMBOLS:
            raw = await fetch_sensex_option_chain_async(
                symbol=symbol,
                expiry=expiry,
                instrument_type=instrument_type,
            )
        else:
            raw = await _fetch_option_chain_async(symbol=symbol, expiry=expiry, instrument_type=instrument_type)
        records = raw.get("records", {})
        rows = build_oi_volume_summary(raw, expiry=expiry)
        if not rows:
            continue

        target_projection = build_target_projection(rows, records.get("underlyingValue"))
        support = target_projection.get("support") if target_projection else None
        resistance = target_projection.get("resistance") if target_projection else None
        break_buffer = float(target_projection.get("breakBuffer", 0) or 0) if target_projection else 0.0

        decision_input = build_decision_input(rows, records.get("underlyingValue"), support, resistance, break_buffer)
        master_decision = master_decision_engine(decision_input)

        key = _cache_key(symbol=symbol, instrument_type=instrument_type, expiry=expiry)
        previous_score = await cache.get_previous_score(key)
        last_10_scores = await cache.get_score_history(key, limit=10)
        cached_previous_state = await cache.get_previous_state(f"STATE::{key}")
        persisted_previous_state = {} if cached_previous_state else _load_persisted_state("STATE", key)
        previous_state = cached_previous_state or persisted_previous_state
        cached_previous_adaptive_state = await cache.get_previous_state(f"ADAPT::{key}")
        persisted_previous_adaptive_state = (
            {} if cached_previous_adaptive_state else _load_persisted_state("ADAPT", key)
        )
        previous_adaptive_state = cached_previous_adaptive_state or persisted_previous_adaptive_state
        if key not in _alignment_bootstrap_logged:
            source = (
                "cache"
                if cached_previous_state
                else ("snapshot" if persisted_previous_state else "empty")
            )
            logger.info(
                "Alignment bootstrap [%s]: source=%s support=%s resistance=%s anchor_age=%s shift_cycle=%s",
                key,
                source,
                previous_state.get("current_support"),
                previous_state.get("current_resistance"),
                previous_state.get("sr_anchor_age_seconds"),
                previous_state.get("support_shift_cycle"),
            )
            _alignment_bootstrap_logged.add(key)
        perf_snapshot = tracker.get_daily_metrics(key)
        bias_acc = float(perf_snapshot.get("bias_accuracy_percent", 55.0) or 55.0) / 100.0
        trap_acc = float(perf_snapshot.get("trap_accuracy_percent", 55.0) or 55.0) / 100.0
        exit_acc = float(perf_snapshot.get("exit_accuracy_percent", 55.0) or 55.0) / 100.0
        engine_stats = {
            "oi_accuracy": bias_acc,
            "volume_accuracy": exit_acc if exit_acc > 0 else bias_acc,
            "breakout_accuracy": bias_acc,
            "sr_accuracy": trap_acc if trap_acc > 0 else bias_acc,
        }
        meta = {
            "symbol": symbol,
            "instrument_type": instrument_type,
            "expiry": expiry,
            "spot": records.get("underlyingValue"),
            "timestamp": records.get("timestamp"),
        }
        summary_payload = {
            "meta": meta,
            "target_projection": target_projection,
            "decision_input": decision_input,
            "master_decision": master_decision,
            "rows": rows,
        }

        v2_payload = _build_v2_intelligence(
            rows=rows,
            spot=records.get("underlyingValue"),
            symbol=symbol,
            expiry=expiry,
            timestamp=records.get("timestamp"),
            previous_close=records.get("previousClose"),
            open_price=records.get("OPEN", records.get("open", records.get("dayOpen"))),
            day_high=records.get("HIGH", records.get("high", records.get("dayHigh"))),
            day_low=records.get("LOW", records.get("low", records.get("dayLow"))),
            previous_score=previous_score,
            last_10_scores=last_10_scores,
            previous_regime=previous_state.get("regime"),
            previous_alignment=previous_state.get("alignment_ratio"),
            previous_atr_ratio=previous_state.get("atr_ratio"),
            previous_volume_ratio=previous_state.get("volume_ratio"),
            previous_oi_delta=previous_state.get("oi_delta"),
            previous_state=previous_state,
            adaptive_state=previous_adaptive_state,
            total_signals_logged=int(perf_snapshot.get("total_signals_logged", 0) or 0),
            engine_stats=engine_stats,
            evaluation_time=_parse_timestamp_utc(records.get("timestamp")),
        )
        daily_levels = (daily_context.get("levels") or {}) if isinstance(daily_context, dict) else {}
        daily_prev = (daily_context.get("previous_day") or {}) if isinstance(daily_context, dict) else {}
        daily_window = (daily_context.get("rolling_3m") or {}) if isinstance(daily_context, dict) else {}
        market_state = v2_payload.setdefault("market_state", {})
        market_state["daily_context"] = daily_context
        market_state["previous_day_open"] = (
            market_state.get("previous_day_open")
            or daily_levels.get("previous_day_open")
            or daily_prev.get("open")
        )
        market_state["previous_day_high"] = (
            market_state.get("previous_day_high")
            or daily_levels.get("previous_day_high")
            or daily_prev.get("high")
        )
        market_state["previous_day_low"] = (
            market_state.get("previous_day_low")
            or daily_levels.get("previous_day_low")
            or daily_prev.get("low")
        )
        market_state["previous_day_close"] = (
            market_state.get("previous_day_close")
            or daily_levels.get("previous_day_close")
            or daily_prev.get("close")
        )
        market_state["daily_trend_bias"] = (
            market_state.get("daily_trend_bias")
            or daily_window.get("trend_bias")
            or daily_context.get("trend_bias")
            if isinstance(daily_context, dict)
            else None
        )
        v2_payload["daily_context"] = daily_context
        mstate = v2_payload.get("market_state", {}) or {}
        signals = v2_payload.get("signals", {}) or {}
        auto_exit = (signals.get("auto_exit", {}) or {}).get("exit_signal", False)
        reversal_probability = (signals.get("early_reversal", {}) or {}).get("reversal_probability", 0)
        emitted_signals = [
            str(item.get("message", "")).strip()
            for item in (signals.get("alerts", []) or [])
            if isinstance(item, dict) and str(item.get("message", "")).strip()
        ]
        emitted_signals.extend(
            [
                str(item.get("message", "")).strip()
                for item in (signals.get("prioritized_signals", []) or [])
                if isinstance(item, dict) and str(item.get("message", "")).strip()
            ]
        )
        # Deduplicate: alerts and prioritized_signals can carry the same message text.
        emitted_signals = list(dict.fromkeys(emitted_signals))
        metrics = tracker.process_snapshot(
            key=key,
            timestamp=_parse_timestamp_utc(records.get("timestamp")),
            spot=records.get("underlyingValue"),
            bias=str(mstate.get("bias", "Neutral")),
            regime=str(mstate.get("volatility_state", "Stable")),
            confidence=float(mstate.get("confidence", 50) or 50),
            target1=mstate.get("target1"),
            target2=mstate.get("target2"),
            trap_risk=float(mstate.get("trap_risk", 0) or 0),
            reversal_probability=float(reversal_probability or 0),
            exit_signal=bool(auto_exit),
            expected_move=float((v2_payload.get("signals", {}).get("expiry_adaptive", {}) or {}).get("adjustedMove", target_projection.get("expectedMove", 1) if target_projection else 1) or 1),
            emitted_signals=emitted_signals,
        )
        v2_payload["performance"] = metrics
        eval_dt = _parse_timestamp_utc(records.get("timestamp"))
        session_key = f"{symbol.upper()}::{eval_dt.date().isoformat()}"
        if eval_dt.hour >= 15 and eval_dt.minute >= 30 and session_key not in _last_calibrated_session:
            updated = update_end_of_day_calibration(
                bias_accuracy=float(metrics.get("bias_accuracy_percent", 0.0) or 0.0),
                breakout_accuracy=float(metrics.get("bias_accuracy_percent", 0.0) or 0.0),
                trap_accuracy=float(metrics.get("trap_accuracy_percent", 0.0) or 0.0),
                clarity_vs_outcome_accuracy=float(metrics.get("exit_accuracy_percent", 0.0) or 0.0),
                oi_accuracy=float(metrics.get("bias_accuracy_percent", 0.0) or 0.0),
                session_date=eval_dt.date(),
            )
            _calibrated_weights.update(updated)
            _last_calibrated_session.add(session_key)

        public_v2_payload = _sanitize_public_v2_payload(v2_payload)
        compact_interpretations = [
            {
                "strikePrice": row.get("strike"),
                "ceLabel": row.get("CE_Interpretation"),
                "peLabel": row.get("PE_Interpretation"),
                "ceConfidence": row.get("CE_ConfidenceScore"),
                "peConfidence": row.get("PE_ConfidenceScore"),
            }
            for row in rows
        ]

        summary_section[key] = {
            "summary": summary_payload,
            "target_projection": {"meta": meta, "projection": target_projection},
            "interpretations": {
                "meta": {
                    "symbol": symbol,
                    "instrument_type": instrument_type,
                    "expiry": expiry,
                },
                "interpretations": compact_interpretations,
            },
            "v2": public_v2_payload,
        }
        weighted_score = v2_payload.get("_internal", {}).get("smoothed_score")
        if isinstance(weighted_score, (int, float)):
            await cache.set_previous_score(key, float(weighted_score))
            await cache.append_score_history(key, float(weighted_score))
        current_state = v2_payload.get("_state", {})
        if isinstance(current_state, dict):
            await cache.set_previous_state(f"STATE::{key}", current_state)
            _persist_state_snapshot("STATE", key, current_state)
        current_adaptive_state = v2_payload.get("_adaptive_state", {})
        if isinstance(current_adaptive_state, dict):
            await cache.set_previous_state(f"ADAPT::{key}", current_adaptive_state)
            _persist_state_snapshot("ADAPT", key, current_adaptive_state)

    return option_chain_section, summary_section


async def run_update_cycle() -> None:
    global _cycle_count_since_flush
    if not await cache.begin_fetch():
        logger.debug("Skipping update cycle: previous fetch still in progress.")
        return

    _prune_runtime_maps()
    started = time.perf_counter()
    try:
        option_chain_data: dict[str, Any] = {
            "generated_at": _utc_iso(datetime.now(timezone.utc)),
            "symbols": {},
            "instrument_type": INSTRUMENT_TYPE,
        }
        summary_data: dict[str, Any] = {
            "summaries": {},
            "target_projections": {},
            "interpretations": {},
            "v2": {},
        }
        cached_data = await cache.get_cached_data()
        cached_summary_data = (cached_data.get("summary_data") or {}) if isinstance(cached_data, dict) else {}
        cached_summaries = (cached_summary_data.get("summaries") or {}) if isinstance(cached_summary_data, dict) else {}
        cached_targets = (cached_summary_data.get("target_projections") or {}) if isinstance(cached_summary_data, dict) else {}
        cached_interpretations = (cached_summary_data.get("interpretations") or {}) if isinstance(cached_summary_data, dict) else {}
        cached_v2 = (cached_summary_data.get("v2") or {}) if isinstance(cached_summary_data, dict) else {}

        index_raw = await _fetch_index_data_async()
        option_chain_data["index_data"] = {"data": index_raw.get("data", [])}

        for symbol in SYMBOLS:
            symbol_option_chain, symbol_summaries = await _build_symbol_payloads(symbol, INSTRUMENT_TYPE)
            option_chain_data["symbols"][symbol] = symbol_option_chain

            for key, payload in symbol_summaries.items():
                summary_data["summaries"][key] = payload["summary"]
                summary_data["target_projections"][key] = payload["target_projection"]
                summary_data["interpretations"][key] = payload["interpretations"]
                summary_data["v2"][key] = payload["v2"]

            # Guardrail: if a symbol returns no fresh summaries for this cycle,
            # carry forward its last cached summaries to avoid meta-only shells.
            if not symbol_summaries:
                symbol_prefix = f"{INSTRUMENT_TYPE.upper()}::{symbol.upper()}::"
                carried = 0
                for key, payload in cached_summaries.items():
                    if isinstance(key, str) and key.startswith(symbol_prefix):
                        summary_data["summaries"][key] = payload
                        if key in cached_targets:
                            summary_data["target_projections"][key] = cached_targets[key]
                        if key in cached_interpretations:
                            summary_data["interpretations"][key] = cached_interpretations[key]
                        if key in cached_v2:
                            summary_data["v2"][key] = cached_v2[key]
                        carried += 1
                if carried > 0:
                    logger.warning(
                        "No fresh summaries for %s; carried forward %d cached payload(s).",
                        symbol,
                        carried,
                    )

        await cache.update_cache(option_chain_data, summary_data)
        latency_ms = (time.perf_counter() - started) * 1000
        await cache.mark_fetch_success(latency_ms=latency_ms)
        _cycle_count_since_flush += 1

        if ENABLE_HZC:
            # Optional offline historical-zone snapshots. This is context-only and
            # intentionally isolated from live SR/SPC decision flow.
            for symbol in SYMBOLS:
                try:
                    from app.infrastructure.persistence.historical_zone_scheduler import run_historical_zone_daily_if_due

                    zone_job = await asyncio.to_thread(run_historical_zone_daily_if_due, symbol)
                    if isinstance(zone_job, dict) and zone_job.get("status") == "written":
                        logger.info(
                            "Historical zone snapshot written [%s]: %s",
                            symbol,
                            zone_job.get("path"),
                        )
                except Exception as zone_exc:
                    logger.warning("Historical zone scheduler failed for %s: %s", symbol, zone_exc)

        logger.info("Background refresh success in %.2f ms", latency_ms)
    except Exception as exc:
        await cache.mark_fetch_failure(str(exc))
        logger.exception("Background refresh failed: %s", exc)
    finally:
        await cache.recompute_stale(stale_after_seconds=STALE_AFTER_SECONDS)
        await cache.end_fetch()


async def background_update_loop(stop_event: asyncio.Event) -> None:
    logger.info("Starting background updater loop: every %s sec", REFRESH_SECONDS)
    while not stop_event.is_set():
        try:
            now_ist = datetime.now(IST)
            await _check_scheduled_flush(now_ist)
            await run_update_cycle()
        except Exception as exc:  # belt-and-suspenders: loop must stay alive
            logger.exception("Background loop error: %s", exc)

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=REFRESH_SECONDS)
        except TimeoutError:
            continue

    logger.info("Background updater loop stopped")
