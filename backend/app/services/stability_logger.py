from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.cache import cache

LOG_DIR = Path(__file__).resolve().parents[2] / "logs" / "stability"
LOGGER_NAME = "optionlens.stability_logger"
WATCH_FIELDS = [
    "trade_action",
    "regime",
    "trade_readiness",
    "readiness_state",
    "bias",
    "session_phase",
    "absorption_detected",
    "absorption_level",
    "support_transition_active",
    "support_shift_cycle",
    "absorption_reference_level",
    "support_strike",
    "resistance_strike",
    "trap_probability",
    "trap_type",
    "breach_confirmed",
    "confirmation_type",
]
REQUIRED_FIELDS = [
    "spot_price",
    "trade_action",
    "regime",
    "trade_readiness",
    "readiness_state",
    "bias",
    "session_phase",
    "absorption_detected",
    "absorption_level",
    "support_transition_active",
    "support_shift_cycle",
    "absorption_reference_level",
    "support_strike",
    "resistance_strike",
    "trap_probability",
    "trap_type",
    "breach_confirmed",
]


@dataclass
class _FieldState:
    value: Any
    since_epoch: float


@dataclass
class _StreamState:
    snapshot_index: int = 0
    fields: dict[str, _FieldState] = field(default_factory=dict)


class StabilityLoggerService:
    def __init__(self) -> None:
        self.logger = logging.getLogger(LOGGER_NAME)
        self.enabled = os.getenv("OPTIONLENS_ENABLE_STABILITY_LOGGER", "false").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self.interval_seconds = max(1, int(os.getenv("OPTIONLENS_STABILITY_LOG_INTERVAL_SECONDS", "5")))
        self.symbol = os.getenv("OPTIONLENS_STABILITY_SYMBOL", "NIFTY").strip().upper() or "NIFTY"
        self.expiry = os.getenv("OPTIONLENS_STABILITY_EXPIRY", "").strip() or None
        self.instrument_type = os.getenv("OPTIONLENS_INSTRUMENT_TYPE", "Indices").strip() or "Indices"
        self._streams: dict[str, _StreamState] = {}
        self._lock_handle: Any | None = None
        LOG_DIR.mkdir(parents=True, exist_ok=True)

    async def run(self, stop_event: asyncio.Event) -> None:
        if not self.enabled:
            self.logger.info("Stability logger disabled")
            return
        if not self._acquire_process_lock():
            self.logger.warning("Stability logger already active in another process; skipping duplicate instance")
            return
        self.logger.info(
            "Starting stability logger: symbol=%s expiry=%s interval=%ss",
            self.symbol,
            self.expiry or "AUTO",
            self.interval_seconds,
        )
        while not stop_event.is_set():
            try:
                await self._log_once()
            except Exception:
                self.logger.warning("stability_logger failed", exc_info=True)
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=self.interval_seconds)
            except TimeoutError:
                continue
        self._release_process_lock()
        self.logger.info("Stability logger stopped")

    async def _log_once(self) -> None:
        data = await cache.get_cached_data()
        if not data.get("summary_data"):
            return
        payload, cache_key = self._resolve_payload(data)
        if not payload or not cache_key:
            return
        record = self._build_record(payload=payload, cache_key=cache_key)
        self._append_jsonl(LOG_DIR / f"stability_{datetime.now().strftime('%Y%m%d')}.jsonl", record)
        transitions = self._build_transitions(record)
        if transitions:
            transition_path = LOG_DIR / f"transitions_{datetime.now().strftime('%Y%m%d')}.jsonl"
            for transition in transitions:
                self._append_jsonl(transition_path, transition)

    def _resolve_payload(self, data: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
        v2_map = data.get("summary_data", {}).get("v2", {}) or {}
        if not isinstance(v2_map, dict) or not v2_map:
            return None, None
        exact_key = self._cache_key(symbol=self.symbol, instrument_type=self.instrument_type, expiry=self.expiry)
        if self.expiry and exact_key in v2_map:
            return v2_map.get(exact_key), exact_key

        symbol_payload = data.get("option_chain_data", {}).get("symbols", {}).get(self.symbol, {}) or {}
        contract_expiries = symbol_payload.get("contract_info", {}).get("expiries", []) if isinstance(symbol_payload, dict) else []
        for expiry in contract_expiries:
            candidate_key = self._cache_key(symbol=self.symbol, instrument_type=self.instrument_type, expiry=str(expiry))
            if candidate_key in v2_map:
                return v2_map.get(candidate_key), candidate_key

        prefix = f"{self.instrument_type.upper()}::{self.symbol}::"
        for key, payload in v2_map.items():
            if isinstance(key, str) and key.startswith(prefix):
                return payload, key
        return None, None

    def _build_record(self, *, payload: dict[str, Any], cache_key: str) -> dict[str, Any]:
        market_state = payload.get("market_state", {}) or {}
        signals = payload.get("signals", {}) or {}
        levels = payload.get("levels", {}) or {}
        internal_state = payload.get("_state", {}) or {}
        trap = signals.get("trap", {}) or {}
        breach = signals.get("material_breach", {}) or {}
        meta = payload.get("meta", {}) or {}
        symbol = str(meta.get("symbol") or self.symbol).upper()
        expiry = str(meta.get("expiry") or self.expiry or "")
        support_shift_cycle = int(market_state.get("support_shift_cycle", 0) or 0)
        support_transition_active = market_state.get("support_transition_active")
        if support_transition_active is None:
            support_transition_active = support_shift_cycle == 1

        record = {
            "_ts": datetime.now().isoformat(timespec="milliseconds"),
            "_epoch": time.time(),
            "snapshot_index": self._streams.get(cache_key, _StreamState()).snapshot_index + 1,
            "stream_key": cache_key,
            "symbol": symbol,
            "expiry": expiry or None,
            "spot_price": (
                market_state.get("spot")
                or payload.get("spot")
                or payload.get("spot_price")
                or meta.get("spot")
            ),
            "trade_action": market_state.get("trade_action"),
            "regime": market_state.get("regime") or market_state.get("state"),
            "trade_readiness": market_state.get("trade_readiness"),
            "readiness_state": market_state.get("readiness_state"),
            "bias": market_state.get("bias"),
            "committed_regime": internal_state.get("committed_regime"),
            "detected_regime": internal_state.get("detected_regime"),
            "candidate_regime": internal_state.get("candidate_regime"),
            "candidate_regime_count": internal_state.get("candidate_regime_count"),
            "readiness_active": internal_state.get("readiness_active"),
            "session_phase": market_state.get("session_phase"),
            "absorption_detected": market_state.get("absorption_detected"),
            "absorption_level": market_state.get("absorption_level"),
            "support_transition_active": support_transition_active,
            "support_shift_cycle": support_shift_cycle,
            "absorption_reference_level": market_state.get("absorption_reference_level"),
            "previous_support": internal_state.get("previous_support"),
            "cache_last_update": internal_state.get("last_update") or internal_state.get("updated_at"),
            "support_strike": levels.get("support", {}).get("strike"),
            "resistance_strike": levels.get("resistance", {}).get("strike"),
            "trap_probability": (
                trap.get("trap_probability_pct")
                if trap.get("trap_probability_pct") is not None
                else trap.get("trap_risk")
                if trap.get("trap_risk") is not None
                else trap.get("trap_probability")
            ),
            "trap_type": trap.get("trap_type"),
            "breach_confirmed": breach.get("material_breach_confirmed"),
            "confirmation_type": breach.get("confirmation_type"),
        }
        record["has_market_state"] = bool(market_state)
        record["has_signals"] = bool(signals)
        record["has_levels"] = bool(levels)
        record["missing_fields"] = self._missing_fields(record)
        record["is_complete"] = bool(
            record["has_market_state"]
            and record["has_signals"]
            and record["has_levels"]
            and not record["missing_fields"]
        )
        return record

    def _build_transitions(self, record: dict[str, Any]) -> list[dict[str, Any]]:
        stream_key = str(record.get("stream_key") or "")
        if not stream_key:
            return []
        state = self._streams.setdefault(stream_key, _StreamState())
        state.snapshot_index = int(record.get("snapshot_index", state.snapshot_index + 1) or state.snapshot_index + 1)
        transitions: list[dict[str, Any]] = []
        now_epoch = float(record.get("_epoch") or time.time())
        for field_name in WATCH_FIELDS:
            current_value = record.get(field_name)
            previous = state.fields.get(field_name)
            if previous is None:
                state.fields[field_name] = _FieldState(value=current_value, since_epoch=now_epoch)
                continue
            if previous.value != current_value:
                transitions.append(
                    {
                        "timestamp": record.get("_ts"),
                        "stream_key": stream_key,
                        "symbol": record.get("symbol"),
                        "expiry": record.get("expiry"),
                        "field": field_name,
                        "from": previous.value,
                        "to": current_value,
                        "held_for_seconds": round(max(0.0, now_epoch - previous.since_epoch), 3),
                        "snapshot_index": state.snapshot_index,
                    }
                )
                state.fields[field_name] = _FieldState(value=current_value, since_epoch=now_epoch)
        return transitions

    def _append_jsonl(self, path: Path, payload: dict[str, Any]) -> None:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=True, default=str) + "\n")

    def _missing_fields(self, record: dict[str, Any]) -> list[str]:
        missing = [field_name for field_name in REQUIRED_FIELDS if record.get(field_name) is None]
        if bool(record.get("breach_confirmed")) and record.get("confirmation_type") is None:
            missing.append("confirmation_type")
        return missing

    @staticmethod
    def _cache_key(symbol: str, instrument_type: str, expiry: str | None) -> str:
        return f"{instrument_type.upper()}::{symbol.upper()}::{expiry or 'AUTO'}"

    def _acquire_process_lock(self) -> bool:
        lock_path = LOG_DIR / ".logger.lock"
        handle = lock_path.open("a+b")
        try:
            handle.seek(0)
            handle.write(b"00000000")
            handle.flush()
            if os.name == "nt":
                import msvcrt

                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            return False
        handle.seek(0)
        handle.truncate()
        handle.write(f"{os.getpid():08x}".encode("ascii"))
        handle.flush()
        self._lock_handle = handle
        return True

    def _release_process_lock(self) -> None:
        handle = self._lock_handle
        if handle is None:
            return
        try:
            if os.name == "nt":
                import msvcrt

                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        finally:
            try:
                handle.seek(0)
                handle.truncate()
                handle.write(b"00000000")
                handle.flush()
            except OSError:
                pass
            handle.close()
            self._lock_handle = None
