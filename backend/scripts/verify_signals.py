import argparse
import datetime as dt
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify daily signal log quality metrics."
    )
    parser.add_argument(
        "--date",
        help="Date in YYYYMMDD format. Defaults to today.",
    )
    return parser.parse_args()


def resolve_date(date_arg: str | None) -> str:
    if not date_arg:
        return dt.date.today().strftime("%Y%m%d")
    if len(date_arg) != 8 or not date_arg.isdigit():
        raise ValueError("--date must be in YYYYMMDD format")
    return date_arg


def load_rows(path: Path) -> list[dict]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def main() -> int:
    args = parse_args()
    day = resolve_date(args.date)
    file_name = f"signals_{day}.jsonl"
    candidates = [
        Path("backend/logs/signals") / file_name,
        Path("logs/signals") / file_name,
    ]
    path = next((p for p in candidates if p.exists()), candidates[0])

    if not any(p.exists() for p in candidates):
        print(f"No signal log file: {candidates[0]} or {candidates[1]}")
        return 0

    rows = load_rows(path)
    print("Total:", len(rows))

    same = sum(
        1
        for row in rows
        if row.get("entry_underlying") == row.get("stop_underlying")
    )
    print("Entry==Stop (must be 0):", same)

    rrs = [row["rr_t1"] for row in rows if row.get("rr_t1") is not None]
    if rrs:
        print(f"RR {min(rrs):.1f}-{max(rrs):.1f} mean={statistics.mean(rrs):.2f}")
    else:
        print("RR: no values")

    key_counts: defaultdict[tuple, int] = defaultdict(int)
    for row in rows:
        support = row.get("support_at_fire") or 0
        rounded_support = round(support / 50) * 50
        key = (row.get("signal_type"), row.get("symbol"), rounded_support)
        key_counts[key] += 1

    print("Max fires/setup:", max(key_counts.values()) if key_counts else 0)
    print(
        "Actions:",
        dict(Counter(row.get("trade_action_at_fire", "?") for row in rows)),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
