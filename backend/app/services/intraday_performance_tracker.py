from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any


@dataclass
class SignalRecord:
    timestamp: datetime
    spot: float
    bias: str
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

    def _today(self) -> date:
        return datetime.now(timezone.utc).date()

    def _get_stats(self, key: str) -> DayStats:
        today = self._today()
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
        confidence: float,
        target1: float | None,
        target2: float | None,
        trap_risk: float,
        reversal_probability: float,
        exit_signal: bool,
        expected_move: float,
    ) -> dict[str, Any]:
        stats = self._get_stats(key)
        if spot is None:
            return self.get_daily_metrics(key)

        # Update pending logs with latest spot for outcome checks.
        for item in stats.signal_log:
            if item.evaluated:
                continue
            item.max_spot = max(item.max_spot, float(spot))
            item.min_spot = min(item.min_spot, float(spot))

        bias_changed = stats.last_bias is not None and bias != stats.last_bias
        should_log = bias_changed or reversal_probability > 60 or exit_signal
        if should_log:
            rec = SignalRecord(
                timestamp=timestamp,
                spot=float(spot),
                bias=str(bias),
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

        # Evaluate matured logs (30 minutes).
        maturity = timedelta(minutes=30)
        for item in stats.signal_log:
            if item.evaluated or timestamp < (item.timestamp + maturity):
                continue

            adverse_move = 0.5 * item.expected_move
            reversed_by_bias = False
            success = False
            failure = False

            if item.bias == "Bullish":
                if item.target1 is not None and item.max_spot >= item.target1:
                    success = True
                elif item.min_spot <= (item.spot - adverse_move):
                    failure = True
                reversed_by_bias = item.min_spot <= (item.spot - adverse_move)
            elif item.bias == "Bearish":
                if item.target1 is not None and item.min_spot <= item.target1:
                    success = True
                elif item.max_spot >= (item.spot + adverse_move):
                    failure = True
                reversed_by_bias = item.max_spot >= (item.spot + adverse_move)

            if success or failure:
                stats.bias_total_evaluated += 1
                if success:
                    stats.bias_success += 1
                    item.bias_result = "success"
                else:
                    item.bias_result = "failure"

            if item.trap_risk > 40:
                stats.trap_total += 1
                item.trap_success = reversed_by_bias
                if item.trap_success:
                    stats.trap_success += 1

            if item.exit_signal:
                stats.exit_total += 1
                item.exit_success = reversed_by_bias
                if item.exit_success:
                    stats.exit_success += 1

            item.evaluated = True

        return self.get_daily_metrics(key)

    def get_daily_metrics(self, key: str) -> dict[str, Any]:
        stats = self._get_stats(key)
        return {
            "bias_accuracy_percent": self._pct(stats.bias_success, stats.bias_total_evaluated),
            "trap_accuracy_percent": self._pct(stats.trap_success, stats.trap_total),
            "exit_accuracy_percent": self._pct(stats.exit_success, stats.exit_total),
            "total_signals_logged": stats.total_signals_logged,
        }


tracker = IntradayPerformanceTracker()

