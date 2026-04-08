from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Any


@dataclass(slots=True)
class DailyCandle:
    date: str
    open: float
    high: float
    low: float
    close: float


@dataclass(slots=True)
class HistoricalZone:
    zone_low: float
    zone_high: float
    mid: float
    tests: int
    is_support: bool
    start_date: str
    end_date: str
    broken: bool
    merge_count: int
    width: float


@dataclass(slots=True)
class RetracementZone:
    zone_low: float
    zone_high: float
    center: float
    score: float
    touches: int
    close_accepts: int
    support_rejections: int
    resistance_rejections: int
    role: str
    first_date: str
    last_date: str


@dataclass(slots=True)
class _WorkingZone:
    top: float
    bottom: float
    test_count: int
    is_support: bool
    start_index: int
    last_index: int
    is_broken: bool = False
    merge_count: int = 0


def _to_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def normalize_daily_candles(rows: list[dict[str, Any]]) -> list[DailyCandle]:
    candles: list[DailyCandle] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        raw_date = str(row.get("date") or row.get("EOD_TIMESTAMP") or "").strip()
        if not raw_date:
            continue

        parsed_date = raw_date
        if "EOD_TIMESTAMP" in row:
            parsed_date = datetime.strptime(raw_date, "%d-%b-%Y").date().isoformat()

        open_price = _to_float(row.get("open", row.get("EOD_OPEN_INDEX_VAL")))
        high_price = _to_float(row.get("high", row.get("EOD_HIGH_INDEX_VAL")))
        low_price = _to_float(row.get("low", row.get("EOD_LOW_INDEX_VAL")))
        close_price = _to_float(row.get("close", row.get("EOD_CLOSE_INDEX_VAL")))
        if None in {open_price, high_price, low_price, close_price}:
            continue

        candles.append(
            DailyCandle(
                date=parsed_date,
                open=float(open_price),
                high=float(high_price),
                low=float(low_price),
                close=float(close_price),
            )
        )

    candles.sort(key=lambda candle: candle.date)
    return candles


def load_nse_history_file(path: str | Path) -> list[DailyCandle]:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    json_start = text.find('{"data"')
    payload_text = text[json_start:] if json_start >= 0 else text
    payload = json.loads(payload_text)
    rows = payload.get("data", []) if isinstance(payload, dict) else []
    return normalize_daily_candles(rows if isinstance(rows, list) else [])


def _is_pivot_high(candles: list[DailyCandle], pivot_index: int, lookback: int) -> bool:
    center = candles[pivot_index].high
    left = candles[pivot_index - lookback : pivot_index]
    right = candles[pivot_index + 1 : pivot_index + lookback + 1]
    return all(center >= candle.high for candle in left + right)


def _is_pivot_low(candles: list[DailyCandle], pivot_index: int, lookback: int) -> bool:
    center = candles[pivot_index].low
    left = candles[pivot_index - lookback : pivot_index]
    right = candles[pivot_index + 1 : pivot_index + lookback + 1]
    return all(center <= candle.low for candle in left + right)


def _check_break(zones: list[_WorkingZone], close_price: float) -> None:
    kept: list[_WorkingZone] = []
    for zone in zones:
        broken = zone.is_support and close_price < zone.bottom
        broken = broken or ((not zone.is_support) and close_price > zone.top)
        if not broken:
            kept.append(zone)
    zones[:] = kept


def _merge_zones(zones: list[_WorkingZone], max_height: float) -> None:
    index = 0
    while index < len(zones):
        primary = zones[index]
        merged = False
        compare_index = index + 1
        while compare_index < len(zones):
            candidate = zones[compare_index]
            overlaps = not (primary.bottom > candidate.top or primary.top < candidate.bottom)
            if overlaps:
                primary.top = max(primary.top, candidate.top)
                primary.bottom = min(primary.bottom, candidate.bottom)
                primary.test_count += candidate.test_count
                primary.merge_count += candidate.merge_count + 1
                primary.start_index = min(primary.start_index, candidate.start_index)
                primary.last_index = max(primary.last_index, candidate.last_index)
                zones.pop(compare_index)
                merged = True
                continue
            compare_index += 1

        if (primary.top - primary.bottom) > max_height:
            zones.pop(index)
            continue
        if merged:
            continue
        index += 1


def _manage_zone(
    zones: list[_WorkingZone],
    *,
    price: float,
    is_support: bool,
    width: float,
    pivot_index: int,
    max_zones: int,
) -> None:
    for zone in zones:
        if zone.bottom <= price <= zone.top:
            zone.test_count += 1
            zone.last_index = pivot_index
            return

    top = price + (width / 2.0 if is_support else width)
    bottom = price - (width if is_support else width / 2.0)
    zones.insert(
        0,
        _WorkingZone(
            top=top,
            bottom=bottom,
            test_count=1,
            is_support=is_support,
            start_index=pivot_index,
            last_index=pivot_index,
        ),
    )
    if len(zones) > max_zones:
        zones.pop()


def run_pine_style_zone_classifier(
    candles: list[DailyCandle],
    *,
    pivot_lookback: int = 10,
    zone_width_multiplier: float = 2.0,
    min_tests: int = 2,
    max_zones: int = 10,
    max_height_multiplier: float = 10.0,
) -> dict[str, list[dict[str, Any]]]:
    if len(candles) < (pivot_lookback * 2) + 1:
        return {
            "supports": [],
            "resistances": [],
            "historical_supports": [],
            "historical_resistances": [],
        }

    support_zones: list[_WorkingZone] = []
    resistance_zones: list[_WorkingZone] = []
    historical_support_zones: list[_WorkingZone] = []
    historical_resistance_zones: list[_WorkingZone] = []
    cumulative_range = 0.0

    for current_index, candle in enumerate(candles):
        cumulative_range += abs(candle.high - candle.low)
        dist = cumulative_range / float(current_index + 1)
        zone_width = (dist if dist > 0 else candle.close * 0.01) * zone_width_multiplier
        max_height = dist * max_height_multiplier if dist > 0 else zone_width * max_height_multiplier

        pivot_index = current_index - pivot_lookback
        if pivot_index >= pivot_lookback and pivot_index + pivot_lookback < len(candles):
            if _is_pivot_high(candles, pivot_index, pivot_lookback):
                _manage_zone(
                    resistance_zones,
                    price=candles[pivot_index].high,
                    is_support=False,
                    width=zone_width,
                    pivot_index=pivot_index,
                    max_zones=max_zones,
                )
                _merge_zones(resistance_zones, max_height)
                _manage_zone(
                    historical_resistance_zones,
                    price=candles[pivot_index].high,
                    is_support=False,
                    width=zone_width,
                    pivot_index=pivot_index,
                    max_zones=max_zones,
                )
                _merge_zones(historical_resistance_zones, max_height)

            if _is_pivot_low(candles, pivot_index, pivot_lookback):
                _manage_zone(
                    support_zones,
                    price=candles[pivot_index].low,
                    is_support=True,
                    width=zone_width,
                    pivot_index=pivot_index,
                    max_zones=max_zones,
                )
                _merge_zones(support_zones, max_height)
                _manage_zone(
                    historical_support_zones,
                    price=candles[pivot_index].low,
                    is_support=True,
                    width=zone_width,
                    pivot_index=pivot_index,
                    max_zones=max_zones,
                )
                _merge_zones(historical_support_zones, max_height)

        _check_break(support_zones, candle.close)
        _check_break(resistance_zones, candle.close)

    def _serialize(zones: list[_WorkingZone]) -> list[dict[str, Any]]:
        serialized: list[dict[str, Any]] = []
        for zone in zones:
            result = HistoricalZone(
                zone_low=round(zone.bottom, 2),
                zone_high=round(zone.top, 2),
                mid=round((zone.top + zone.bottom) / 2.0, 2),
                tests=zone.test_count,
                is_support=zone.is_support,
                start_date=candles[zone.start_index].date,
                end_date=candles[zone.last_index].date,
                broken=zone.is_broken,
                merge_count=zone.merge_count,
                width=round(zone.top - zone.bottom, 2),
            )
            if result.tests >= min_tests:
                serialized.append(asdict(result))
        return serialized

    return {
        "supports": _serialize(sorted(support_zones, key=lambda zone: zone.test_count, reverse=True)),
        "resistances": _serialize(sorted(resistance_zones, key=lambda zone: zone.test_count, reverse=True)),
        "historical_supports": _serialize(
            sorted(historical_support_zones, key=lambda zone: zone.test_count, reverse=True)
        ),
        "historical_resistances": _serialize(
            sorted(historical_resistance_zones, key=lambda zone: zone.test_count, reverse=True)
        ),
    }


def _auto_price_step(candles: list[DailyCandle]) -> float:
    ranges = [abs(candle.high - candle.low) for candle in candles if candle.high > candle.low]
    if not ranges:
        return 100.0
    median_range = median(ranges)
    raw_step = max(50.0, min(200.0, (median_range * 0.5)))
    return max(50.0, round(raw_step / 50.0) * 50.0)


def detect_retracement_zones(
    candles: list[DailyCandle],
    *,
    price_step: float | None = None,
    top_n: int = 8,
    recent_window: int | None = None,
) -> list[dict[str, Any]]:
    if not candles:
        return []

    scope = candles[-recent_window:] if recent_window and recent_window > 0 else candles
    if not scope:
        return []

    step = float(price_step or _auto_price_step(scope))
    min_price = min(candle.low for candle in scope)
    max_price = max(candle.high for candle in scope)
    start_center = math.floor(min_price / step) * step
    end_center = math.ceil(max_price / step) * step
    centers: list[float] = []
    cursor = start_center
    while cursor <= end_center + 1e-9:
        centers.append(round(cursor, 6))
        cursor += step

    center_stats: list[dict[str, Any]] = []
    for center in centers:
        touches = 0
        close_accepts = 0
        support_rejections = 0
        resistance_rejections = 0
        touched_dates: list[str] = []

        for candle in scope:
            if candle.low <= center <= candle.high:
                touches += 1
                touched_dates.append(candle.date)
            if abs(candle.close - center) <= (step * 0.5):
                close_accepts += 1
                touched_dates.append(candle.date)
            if abs(candle.low - center) <= (step * 0.6) and candle.close >= center + (step * 0.8):
                support_rejections += 1
                touched_dates.append(candle.date)
            if abs(candle.high - center) <= (step * 0.6) and candle.close <= center - (step * 0.8):
                resistance_rejections += 1
                touched_dates.append(candle.date)

        score = (
            float(touches)
            + (float(close_accepts) * 1.5)
            + (float(support_rejections) * 2.0)
            + (float(resistance_rejections) * 2.0)
        )
        center_stats.append(
            {
                "center": center,
                "touches": touches,
                "close_accepts": close_accepts,
                "support_rejections": support_rejections,
                "resistance_rejections": resistance_rejections,
                "score": round(score, 2),
                "dates": sorted(set(touched_dates)),
            }
        )

    ranked = sorted(center_stats, key=lambda item: item["score"], reverse=True)
    selected = sorted(ranked[: max(1, top_n)], key=lambda item: item["center"])
    if not selected:
        return []

    clusters: list[list[dict[str, Any]]] = [[selected[0]]]
    for item in selected[1:]:
        previous = clusters[-1][-1]
        if abs(item["center"] - previous["center"]) <= step:
            clusters[-1].append(item)
        else:
            clusters.append([item])

    zones: list[RetracementZone] = []
    for cluster in clusters:
        dominant = max(cluster, key=lambda item: item["score"])
        cluster_dates = sorted({date_text for item in cluster for date_text in item["dates"]})
        support_bias = sum(int(item["support_rejections"]) for item in cluster)
        resistance_bias = sum(int(item["resistance_rejections"]) for item in cluster)
        if support_bias > resistance_bias * 1.25:
            role = "support"
        elif resistance_bias > support_bias * 1.25:
            role = "resistance"
        else:
            role = "acceptance"

        zones.append(
            RetracementZone(
                zone_low=round(cluster[0]["center"] - (step / 2.0), 2),
                zone_high=round(cluster[-1]["center"] + (step / 2.0), 2),
                center=round(dominant["center"], 2),
                score=float(dominant["score"]),
                touches=int(sum(int(item["touches"]) for item in cluster)),
                close_accepts=int(sum(int(item["close_accepts"]) for item in cluster)),
                support_rejections=int(support_bias),
                resistance_rejections=int(resistance_bias),
                role=role,
                first_date=cluster_dates[0] if cluster_dates else scope[0].date,
                last_date=cluster_dates[-1] if cluster_dates else scope[-1].date,
            )
        )

    zones.sort(key=lambda zone: zone.score, reverse=True)
    return [asdict(zone) for zone in zones]


def analyze_historical_sr_zones(
    candles: list[DailyCandle],
    *,
    recent_window: int = 12,
    price_step: float | None = None,
    pivot_lookback: int = 10,
    zone_width_multiplier: float = 2.0,
    min_tests: int = 2,
    max_zones: int = 10,
    max_height_multiplier: float = 5.0,
) -> dict[str, Any]:
    return {
        "pine_style": run_pine_style_zone_classifier(
            candles,
            pivot_lookback=pivot_lookback,
            zone_width_multiplier=zone_width_multiplier,
            min_tests=min_tests,
            max_zones=max_zones,
            max_height_multiplier=max_height_multiplier,
        ),
        "retracement_full_window": detect_retracement_zones(candles, price_step=price_step),
        "retracement_recent_window": detect_retracement_zones(
            candles,
            price_step=price_step,
            recent_window=recent_window,
        ),
    }
