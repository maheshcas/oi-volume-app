from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from app.engines.historical_zone_engine import analyze_historical_sr_zones, load_nse_history_file


def _resolve_output_path(raw_out: str) -> Path:
    target = Path(raw_out)
    if target.suffix.lower() == ".json":
        return target

    if target.exists() and target.is_dir():
        stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        return target / f"historical_zones_{stamp}.json"

    if not target.suffix:
        stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        return target / f"historical_zones_{stamp}.json"

    return target


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze historical daily candles for Pine-style and retracement S/R zones.")
    parser.add_argument("--file", required=True, help="Path to raw NSE historical index response text or JSON file.")
    parser.add_argument(
        "--out",
        default=None,
        help="Optional output path. Supports file path (*.json) or a directory path for timestamped snapshots.",
    )
    parser.add_argument("--recent-window", type=int, default=12, help="Number of recent candles to analyze for the recent retracement regime.")
    parser.add_argument("--price-step", type=float, default=None, help="Optional fixed zone step. Defaults to auto.")
    parser.add_argument("--pivot-lookback", type=int, default=10, help="Pine-style pivot lookback.")
    parser.add_argument("--zone-width-multiplier", type=float, default=2.0, help="Pine-style zone width multiplier.")
    parser.add_argument("--min-tests", type=int, default=2, help="Minimum Pine-style tests to keep in output.")
    parser.add_argument("--max-zones", type=int, default=10, help="Maximum active zones per type for the Pine-style classifier.")
    parser.add_argument("--max-height-multiplier", type=float, default=5.0, help="Maximum Pine-style merged zone height multiplier.")
    parser.add_argument("--min-score-gap", type=float, default=1.5, help="Dominance ratio threshold for marking the top zone as dominant.")
    args = parser.parse_args()

    candles = load_nse_history_file(Path(args.file))
    payload = analyze_historical_sr_zones(
        candles,
        recent_window=args.recent_window,
        price_step=args.price_step,
        pivot_lookback=args.pivot_lookback,
        zone_width_multiplier=args.zone_width_multiplier,
        min_tests=args.min_tests,
        max_zones=args.max_zones,
        max_height_multiplier=args.max_height_multiplier,
        min_score_gap=args.min_score_gap,
    )

    output_doc = {
        "meta": {
            "source_file": str(Path(args.file)),
            "generated_at_utc": datetime.now(tz=timezone.utc).isoformat(),
            "candles_count": len(candles),
            "parameters": {
                "recent_window": args.recent_window,
                "price_step": args.price_step,
                "pivot_lookback": args.pivot_lookback,
                "zone_width_multiplier": args.zone_width_multiplier,
                "min_tests": args.min_tests,
                "max_zones": args.max_zones,
                "max_height_multiplier": args.max_height_multiplier,
                "min_score_gap": args.min_score_gap,
            },
        },
        "analysis": payload,
    }

    serialized = json.dumps(output_doc, ensure_ascii=True, indent=2)
    if args.out:
        output_path = _resolve_output_path(args.out)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(serialized, encoding="utf-8")

    print(serialized)


if __name__ == "__main__":
    main()
