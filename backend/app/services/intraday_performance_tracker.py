from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
import logging
from typing import Any

logger = logging.getLogger("optionlens.performance_tracker")

IST = timezone(timedelta(hours=5, minutes=30))
MARKET_OPEN_HOUR = 9
MARKET_OPEN_MINUTE = 15
EVAL_WINDOW_MINUTES = 5
MIN_DIRECTION_MOVE_PTS = 10.0
EXPECTED_MOVE_FACTOR = 0.15


@dataclass
class SignalRecord:
    timestamp: datetime
    spot: float
    bias: str
    regime: str
    signal_label: str
    confidence: float
    target1: float | None
    target2: float | None
    trap_risk: float
    reversal_probability: float
    exit_signal: bool
    expected_move: float
    max_spot: float
    min_spot: float
    evaluated: bool = False
    bias_result: str | None = None
    trap_success: bool | None = None
    exit_success: bool | None = None


@dataclass
class DayStats:
    day: date
    total_signals_logged: int = 0
    bias_success: int = 0
    bias_total_evaluated: int = 0
    trap_success: int = 0
    trap_total: int = 0
    exit_success: int = 0
    exit_total: int = 0
    signal_log: list[SignalRecord] = field(default_factory=list)
    last_bias: str | None = None


class IntradayPerformanceTracker:
    def __init__(self) -> None:
        self._store: dict[str, DayStats] = {}

    def _trading_day(self, timestamp: datetime | None = None) -> date:
        ts = (timestamp or datetime.now(timezone.utc)).astimezone(IST)
        open_cutoff = ts.replace(hour=MARKET_OPEN_HOUR, minute=MARKET_OPEN_MINUTE, second=0, microsecond=0)
        # Before market open, keep attaching to previous trading day.
        if ts < open_cutoff:
            return (ts - timedelta(days=1)).date()
        return ts.date()

    def _get_stats(self, key: str, timestamp: datetime | None = None) -> DayStats:
        today = self._trading_day(timestamp)
        stats = self._store.get(key)
        if stats is None or stats.day != today:
            stats = DayStats(day=today)
            self._store[key] = stats
        return stats

    @staticmethod
    def _pct(num: int, den: int) -> float:
        if den <= 0:
            return 0.0
        return round((num / den) * 100.0, 2)

    def process_snapshot(
        self,
        *,
        key: str,
        timestamp: datetime,
        spot: float | None,
        bias: str,
        regime: str,
        confidence: float,
        target1: float | None,
        target2: float | None,
        trap_risk: float,
        reversal_probability: float,
        exit_signal: bool,
        expected_move: float,
        emitted_signals: list[str] | None = None,
    ) -> dict[str, Any]:
        stats = self._get_stats(key, timestamp)
        if spot is None:
            return self.get_daily_metrics(key)

        # Update pending logs with latest spot for outcome checks.
        for item in stats.signal_log:
            if item.evaluated:
                continue
            item.max_spot = max(item.max_spot, float(spot))
            item.min_spot = min(item.min_spot, float(spot))

        signals = [s for s in (emitted_signals or []) if isinstance(s, str) and s.strip()]
        for signal_label in signals:
            rec = SignalRecord(
                timestamp=timestamp,
                spot=float(spot),
                bias=str(bias),
                regime=str(regime),
                signal_label=signal_label,
                confidence=float(confidence),
                target1=target1,
                target2=target2,
                trap_risk=float(trap_risk),
                reversal_probability=float(reversal_probability),
                exit_signal=bool(exit_signal),
                expected_move=max(1.0, float(expected_move)),
                max_spot=float(spot),
                min_spot=float(spot),
            )
            stats.signal_log.append(rec)
            stats.total_signals_logged += 1
        stats.last_bias = bias

        # Evaluate matured logs every 5 minutes window.
        maturity = timedelta(minutes=EVAL_WINDOW_MINUTES)
        evaluated_any = False
        for item in stats.signal_log:
            if item.evaluated or timestamp < (item.timestamp + maturity):
                continue

            required_move = max(MIN_DIRECTION_MOVE_PTS, EXPECTED_MOVE_FACTOR * item.expected_move)
            directional_move = 0.0
            opposite_move = 0.0
            success = False
            failure = False

            if item.bias == "Bullish":
                directional_move = item.max_spot - item.spot
                opposite_move = item.spot - item.min_spot
                target_hit = item.target1 is not None and item.max_spot >= item.target1
                if target_hit or directional_move >= required_move:
                    success = True
                elif opposite_move >= required_move:
                    failure = True
            elif item.bias == "Bearish":
                directional_move = item.spot - item.min_spot
                opposite_move = item.max_spot - item.spot
                target_hit = item.target1 is not None and item.min_spot <= item.target1
                if target_hit or directional_move >= required_move:
                    success = True
                elif opposite_move >= required_move:
                    failure = True
            else:
                # Neutral calls are excluded from directional scoring.
                item.evaluated = True
                continue

            if success or failure:
                stats.bias_total_evaluated += 1
                if success:
                    stats.bias_success += 1
                    item.bias_result = "success"
                else:
                    item.bias_result = "failure"

            reversed_against_bias = opposite_move >= required_move
            if item.trap_risk > 40:
                stats.trap_total += 1
                item.trap_success = reversed_against_bias
                if item.trap_success:
                    stats.trap_success += 1

            if item.exit_signal:
                stats.exit_total += 1
                # Exit is considered correct if target or stop context was respected quickly.
                item.exit_success = bool(success or reversed_against_bias)
                if item.exit_success:
                    stats.exit_success += 1

            item.evaluated = True
            evaluated_any = True

        metrics = self.get_daily_metrics(key)
        if signals or evaluated_any:
            logger.info(
                "Performance[%s] day=%s logged=%d bias=%.2f trap=%.2f exit=%.2f signals=%d",
                key,
                stats.day.isoformat(),
                len(signals),
                metrics["bias_accuracy_percent"],
                metrics["trap_accuracy_percent"],
                metrics["exit_accuracy_percent"],
                metrics["total_signals_logged"],
            )

        return metrics

    def get_daily_metrics(self, key: str) -> dict[str, Any]:
        stats = self._get_stats(key)
        return {
            "bias_accuracy_percent": self._pct(stats.bias_success, stats.bias_total_evaluated),
            "trap_accuracy_percent": self._pct(stats.trap_success, stats.trap_total),
            "exit_accuracy_percent": self._pct(stats.exit_success, stats.exit_total),
            "total_signals_logged": stats.total_signals_logged,
        }


tracker = IntradayPerformanceTracker()
