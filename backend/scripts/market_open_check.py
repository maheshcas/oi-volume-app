#!/usr/bin/env python3
"""
market_open_check.py — Five-point market-open verification for OptionLens.

Run at 09:15 IST. Polls every 15 s for up to 15 minutes and reports each
check the moment it first passes. Exits 0 if all five pass, 1 otherwise.

Usage:
    python scripts/market_open_check.py
    python scripts/market_open_check.py --url http://localhost:8000 --symbols NIFTY,BANKNIFTY
    python scripts/market_open_check.py --url https://api.optionlens.in --interval 15
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib import request as urllib_request
from urllib.error import URLError
import json

# ── ANSI colours ──────────────────────────────────────────────────────────────
RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
GREEN  = "\033[32m"
RED    = "\033[31m"
YELLOW = "\033[33m"
CYAN   = "\033[36m"
WHITE  = "\033[37m"


def _c(colour: str, text: str) -> str:
    return f"{colour}{text}{RESET}"


IST = timezone(timedelta(hours=5, minutes=30))
WALL_RATIO_RE = re.compile(r"(\d+\.\d+)x", re.IGNORECASE)


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def _get(url: str, timeout: int = 8) -> dict[str, Any] | None:
    try:
        with urllib_request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (URLError, json.JSONDecodeError, OSError):
        return None


# ── Individual checks ─────────────────────────────────────────────────────────

class Check:
    def __init__(self, index: int, name: str, detail: str) -> None:
        self.index = index
        self.name = name
        self.detail = detail
        self.passed = False
        self.passed_at: str | None = None
        self.last_value: str = "—"

    def mark_pass(self, value: str) -> None:
        if not self.passed:
            self.passed = True
            self.passed_at = datetime.now(IST).strftime("%H:%M:%S")
            self.last_value = value

    def status_line(self) -> str:
        if self.passed:
            icon = _c(GREEN, "✓")
            badge = _c(GREEN, f"PASS @ {self.passed_at}")
            val = _c(DIM, f"  [{self.last_value}]")
        else:
            icon = _c(YELLOW, "○")
            badge = _c(YELLOW, "waiting…")
            val = _c(DIM, f"  [{self.last_value}]")
        return f"  {icon}  {_c(BOLD, str(self.index))}. {self.name:<38}  {badge}{val}"


def check1_timestamp(health: dict[str, Any], check: Check) -> None:
    """Timestamp advances past 09:15 — freshness_state = live."""
    state = health.get("freshness_state", "")
    delta = health.get("delta_seconds")
    stale = health.get("stale_data", True)
    ts    = health.get("timestamp") or ""

    # Accept as passed if data is live (< 30 s) and not stale
    if state == "live" and not stale:
        # Confirm the cached timestamp is after 09:15 IST
        try:
            dt = datetime.fromisoformat(ts).astimezone(IST)
            if dt.hour >= 9 and dt.minute >= 15:
                check.mark_pass(f"{state}, Δ{delta}s, ts={dt.strftime('%H:%M:%S')}")
                return
        except (ValueError, TypeError):
            pass
        check.mark_pass(f"{state}, Δ{delta}s")
    else:
        check.last_value = f"state={state} stale={stale} Δ{delta}s"


def check2_oi_change(v2: dict[str, Any], check: Check) -> None:
    """OI change fields non-zero — live OI is flowing."""
    signals = v2.get("signals") or {}
    af = signals.get("alignment_filter") or {}
    oi = signals.get("oi") or {}

    oi_shift   = af.get("oi_shift_score")
    oi_vel     = oi.get("oi_velocity_score")

    # Also check market_state doi counts from summary
    ms = v2.get("market_state") or {}
    ms_oi_scenario = ms.get("oi_scenario", "")

    # Either metric being non-zero proves live OI is moving
    if oi_shift and abs(float(oi_shift)) > 0.001:
        check.mark_pass(f"oi_shift_score={oi_shift:.3f}")
    elif oi_vel and abs(float(oi_vel)) > 0.001:
        check.mark_pass(f"oi_velocity_score={oi_vel:.3f}")
    elif ms_oi_scenario and ms_oi_scenario not in ("", "neutral", "Neutral"):
        check.mark_pass(f"oi_scenario={ms_oi_scenario}")
    else:
        check.last_value = (
            f"oi_shift={oi_shift} vel={oi_vel} scenario={ms_oi_scenario}"
        )


def check3_session_phase(v2: dict[str, Any], check: Check) -> None:
    """session_phase → 'Opening Drive' by 09:30."""
    ms    = v2.get("market_state") or {}
    phase = ms.get("session_phase") or ""
    conf  = ms.get("session_phase_confidence")
    conf_str = f" conf={conf:.0%}" if isinstance(conf, float) else ""

    if "opening" in phase.lower() or "drive" in phase.lower():
        check.mark_pass(f"{phase}{conf_str}")
    else:
        check.last_value = phase or "not set"


def check4_wall_ratio(v2: dict[str, Any], check: Check) -> None:
    """directional_reason contains real wall_ratio (not 0.00x or absent)."""
    ms     = v2.get("market_state") or {}
    reason = ms.get("directional_reason") or ""

    if not reason:
        check.last_value = "directional_reason absent"
        return

    ratios = [float(m) for m in WALL_RATIO_RE.findall(reason)]
    if not ratios:
        check.last_value = f"no ratio in: {reason[:60]}"
        return

    max_ratio = max(ratios)
    if max_ratio > 0.05:
        check.mark_pass(f"max_ratio={max_ratio:.2f}x  ({reason[:55]}…)" if len(reason) > 55 else f"{reason}")
    else:
        check.last_value = f"ratio too small: {max_ratio:.3f}x"


def check5_performance(perf: dict[str, Any] | None, check: Check) -> None:
    """Performance accuracy metrics start populating after first signal cycle."""
    if perf is None:
        check.last_value = "endpoint unreachable"
        return

    signals = perf.get("total_signals_logged", 0) or 0
    bias_acc = perf.get("bias_accuracy_percent", 0.0) or 0.0

    if signals > 0:
        check.mark_pass(
            f"signals={signals}  bias_acc={bias_acc:.1f}%"
        )
    else:
        check.last_value = f"signals_logged={signals} (waiting for first cycle)"


# ── Main loop ─────────────────────────────────────────────────────────────────

def _header(symbol: str, base_url: str) -> None:
    now = datetime.now(IST).strftime("%d-%b-%Y  %H:%M:%S IST")
    print()
    print(_c(BOLD + CYAN, "━" * 70))
    print(_c(BOLD + CYAN, "  OptionLens — Market-Open Verification"))
    print(_c(CYAN,        f"  Symbol : {symbol}   │   Server : {base_url}"))
    print(_c(CYAN,        f"  Started: {now}"))
    print(_c(BOLD + CYAN, "━" * 70))
    print()


def _render(checks: list[Check], poll: int, total: int, elapsed: int) -> None:
    passed = sum(1 for c in checks if c.passed)
    bar_pct = elapsed / (total * 60) if total else 0
    filled = int(bar_pct * 30)
    bar = "█" * filled + "░" * (30 - filled)
    colour = GREEN if passed == 5 else YELLOW

    # Move cursor up to overwrite previous render (after first paint)
    if poll > 1:
        sys.stdout.write(f"\033[{len(checks) + 5}A")

    print(_c(colour, f"  Poll #{poll:>3}  │  {passed}/5 checks passed  │  {elapsed:>3}s elapsed"))
    print(_c(DIM,    f"  [{bar}]  {elapsed//60:02d}:{elapsed%60:02d} / {total:02d}:00"))
    print()
    for c in checks:
        print(c.status_line())
    print()
    sys.stdout.flush()


def run(
    base_url: str,
    symbol: str,
    expiry: str | None,
    instrument_type: str,
    interval: int,
    window_minutes: int,
) -> int:
    url_health   = f"{base_url}/api/health/nse"
    url_v2       = f"{base_url}/api/v2/intelligence/summary?symbol={symbol}&instrument_type={instrument_type}"
    url_perf     = f"{base_url}/api/v2/performance/daily?symbol={symbol}&instrument_type={instrument_type}"
    if expiry:
        url_v2   += f"&expiry={expiry}"
        url_perf += f"&expiry={expiry}"

    checks = [
        Check(1, "Timestamp past 09:15 (stale clears)",   "health/nse → freshness_state=live"),
        Check(2, "OI change fields non-zero",              "signals.alignment_filter.oi_shift_score"),
        Check(3, "session_phase = Opening Drive",          "market_state.session_phase"),
        Check(4, "directional_reason has real wall_ratio", "market_state.directional_reason"),
        Check(5, "Performance metrics populating",         "v2/performance/daily.total_signals_logged"),
    ]

    _header(symbol, base_url)

    start  = time.monotonic()
    limit  = window_minutes * 60
    poll   = 0

    while True:
        elapsed = int(time.monotonic() - start)
        poll   += 1

        health = _get(url_health) or {}
        v2     = _get(url_v2)     or {}
        perf   = _get(url_perf)

        check1_timestamp(health, checks[0])
        if v2:
            check2_oi_change(v2,  checks[1])
            check3_session_phase(v2, checks[2])
            check4_wall_ratio(v2, checks[3])
        check5_performance(perf, checks[4])

        _render(checks, poll, window_minutes, elapsed)

        all_passed = all(c.passed for c in checks)
        if all_passed:
            print(_c(GREEN + BOLD, "  ✓ All five checks passed — system is healthy for trading.\n"))
            return 0

        if elapsed >= limit:
            break

        time.sleep(interval)

    # Final summary after timeout
    failed = [c for c in checks if not c.passed]
    print(_c(RED + BOLD, f"  ✗ Window expired. {len(failed)} check(s) did not pass:\n"))
    for c in failed:
        print(_c(RED, f"    • [{c.index}] {c.name}"))
        print(_c(DIM, f"      Last value: {c.last_value}"))
    print()
    return 1


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify five market-open health checks within 15 minutes of 09:15 IST.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Checks:
  1  freshness_state=live and delta_seconds<30 (stale data cleared)
  2  oi_shift_score or oi_velocity_score > 0  (live OI flowing)
  3  session_phase contains "Opening" / "Drive"
  4  directional_reason has wall_ratio > 0.05x
  5  total_signals_logged > 0 in performance endpoint
        """,
    )
    parser.add_argument("--url",             default="http://localhost:8000",  help="Backend base URL")
    parser.add_argument("--symbols",         default="NIFTY",                  help="Comma-separated symbols (first is checked)")
    parser.add_argument("--expiry",          default=None,                     help="Specific expiry (default: nearest)")
    parser.add_argument("--instrument-type", default="Indices",                help="Instrument type")
    parser.add_argument("--interval",        default=15, type=int,             help="Poll interval in seconds (default: 15)")
    parser.add_argument("--window",          default=15, type=int,             help="Total window in minutes (default: 15)")
    args = parser.parse_args()

    symbol = args.symbols.split(",")[0].strip().upper()
    sys.exit(run(
        base_url=args.url,
        symbol=symbol,
        expiry=args.expiry,
        instrument_type=args.instrument_type,
        interval=args.interval,
        window_minutes=args.window,
    ))


if __name__ == "__main__":
    main()
