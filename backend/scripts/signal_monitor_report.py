import json
import math
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean


ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = ROOT / "backend" / "logs"
TODAY = "20260428"


def _load_jsonl(path: Path):
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def _r50(v):
    try:
        return int(round(float(v) / 50.0) * 50)
    except Exception:
        return 0


def _bucket_rr(v):
    if v < 1:
        return "<1"
    if v < 1.5:
        return "1-1.5"
    if v < 2:
        return "1.5-2"
    if v < 3:
        return "2-3"
    if v < 5:
        return "3-5"
    return ">5"


def _bucket_trap(v):
    if v < 35:
        return "<35"
    if v < 45:
        return "35-45"
    if v < 55:
        return "45-55"
    if v < 65:
        return "55-65"
    if v < 75:
        return "65-75"
    return ">75"


def generate_report():
    signals = _load_jsonl(LOG_DIR / f"signals_{TODAY}.jsonl")
    stability = _load_jsonl(LOG_DIR / f"stability_{TODAY}.jsonl")

    out = []
    out.append(f"DAILY STABILITY REPORT AUTO-RUN | {datetime.now().isoformat(timespec='seconds')}")
    out.append("=" * 90)

    # Analysis 1
    total_signals = len(signals)
    by_type = Counter(s.get("signal_type", "UNKNOWN") for s in signals)
    by_symbol = Counter(s.get("symbol", "UNKNOWN") for s in signals)
    setup_counter = defaultdict(int)
    for s in signals:
        key = (
            s.get("signal_type", "UNKNOWN"),
            s.get("symbol", "UNKNOWN"),
            _r50(s.get("support_at_fire", 0)),
            _r50(s.get("resistance_at_fire", 0)),
        )
        setup_counter[key] += 1
    max_fires = max(setup_counter.values()) if setup_counter else 0
    status_1 = "PASS" if max_fires <= 13 else ("WARN" if max_fires <= 20 else "FAIL")
    out.append(f"[ANALYSIS 1] {status_1} | total_signals={total_signals} max_fires_per_setup={max_fires}")
    out.append(f"  by_type={dict(by_type)}")
    out.append(f"  by_symbol={dict(by_symbol)}")

    # Analysis 2
    entry_eq_stop = sum(
        1 for s in signals if s.get("entry_underlying") is not None and s.get("entry_underlying") == s.get("stop_underlying")
    )
    rr_vals = [float(s.get("rr_t1")) for s in signals if isinstance(s.get("rr_t1"), (int, float))]
    rr_bucket = Counter(_bucket_rr(v) for v in rr_vals)
    rr_lt_1 = sum(1 for v in rr_vals if v < 1)
    rr_gt_5 = sum(1 for v in rr_vals if v > 5)
    status_2 = "PASS" if entry_eq_stop == 0 and rr_lt_1 == 0 else "FAIL"
    out.append(f"[ANALYSIS 2] {status_2} | entry_eq_stop={entry_eq_stop} rr_lt_1={rr_lt_1} rr_gt_5={rr_gt_5}")
    if rr_vals:
        out.append(
            f"  rr_stats=min:{min(rr_vals):.2f} mean:{mean(rr_vals):.2f} max:{max(rr_vals):.2f} buckets:{dict(rr_bucket)}"
        )

    # Analysis 3
    action_dist = Counter(s.get("trade_action_at_fire", "UNKNOWN") for s in signals)
    wait_signals = action_dist.get("WAIT", 0)
    status_3 = "PASS" if wait_signals == 0 else "FAIL"
    out.append(f"[ANALYSIS 3] {status_3} | trade_action_dist={dict(action_dist)}")
    if total_signals == 0:
        out.append("  INFO: zero signals; likely range-conflict day gating.")

    # Analysis 4
    traps = []
    absorption_true = 0
    disagree_true = 0
    primary_confirmed_true = 0
    absorption_with_trap_gt55 = 0
    for r in stability:
        t = r.get("trap_probability")
        if isinstance(t, (int, float)):
            traps.append(float(t))
        abs_det = r.get("absorption_detected")
        if abs_det is True:
            absorption_true += 1
            if isinstance(t, (int, float)) and float(t) > 55:
                absorption_with_trap_gt55 += 1
        tm_abs = r.get("tm_absorption", {}) if isinstance(r.get("tm_absorption"), dict) else {}
        if tm_abs.get("disagree") is True:
            disagree_true += 1
        if tm_abs.get("primary_confirmed") is True:
            primary_confirmed_true += 1
    total_cycles = len(stability)
    trap_buckets = Counter(_bucket_trap(v) for v in traps)
    status_4 = "PASS" if absorption_with_trap_gt55 == 0 else "WARN"
    out.append(
        f"[ANALYSIS 4] {status_4} | cycles={total_cycles} absorption_rate={absorption_true/max(total_cycles,1):.2%} disagree_rate={disagree_true/max(total_cycles,1):.2%}"
    )
    out.append(
        f"  primary_confirmed_rate={primary_confirmed_true/max(total_cycles,1):.2%} absorption_with_trap_gt55={absorption_with_trap_gt55}"
    )
    if traps:
        out.append(f"  trap_range={min(traps):.1f}-{max(traps):.1f} buckets={dict(trap_buckets)}")

    # Analysis 5
    mp_rows = []
    for r in stability:
        spot = r.get("spot_price") or r.get("spot")
        mp = r.get("max_pain_strike") or r.get("max_pain")
        trap = r.get("trap_probability")
        ts = r.get("ts") or r.get("timestamp")
        if isinstance(spot, (int, float)) and isinstance(mp, (int, float)):
            mp_rows.append((ts, float(spot), float(mp), float(spot) - float(mp), trap))
    status_5 = "INFO"
    if mp_rows:
        closest = min(mp_rows, key=lambda x: abs(x[3]))
        out.append(f"[ANALYSIS 5] {status_5} | closest_to_max_pain dist={closest[3]:.1f} at {closest[0]}")
    else:
        out.append(f"[ANALYSIS 5] {status_5} | max pain/spot rows unavailable")

    # Analysis 6
    sup_seq = [r.get("support_strike") or r.get("support") for r in stability]
    res_seq = [r.get("resistance_strike") or r.get("resistance") for r in stability]
    sup_trans = sum(1 for i in range(1, len(sup_seq)) if sup_seq[i] != sup_seq[i - 1] and sup_seq[i] is not None)
    res_trans = sum(1 for i in range(1, len(res_seq)) if res_seq[i] != res_seq[i - 1] and res_seq[i] is not None)
    status_6 = "PASS" if sup_trans < 5 and res_trans < 5 else "WARN"
    out.append(f"[ANALYSIS 6] {status_6} | support_transitions={sup_trans} resistance_transitions={res_trans}")

    # Analysis 7
    straddles = [s for s in signals if str(s.get("signal_type", "")).upper() == "SELL_STRADDLE"]
    ivr_vals = [float(s.get("iv_rank_at_fire")) for s in straddles if isinstance(s.get("iv_rank_at_fire"), (int, float))]
    ivr_lt_50 = sum(1 for v in ivr_vals if v < 50)
    status_7 = "PASS" if ivr_lt_50 == 0 else "WARN"
    out.append(f"[ANALYSIS 7] {status_7} | straddle_count={len(straddles)} ivr_lt_50={ivr_lt_50}")
    if ivr_vals:
        out.append(f"  ivr_range={min(ivr_vals):.1f}-{max(ivr_vals):.1f} mean={mean(ivr_vals):.1f}")

    out.append("-" * 90)
    out.append(
        f"Summary: signals={total_signals}, max_fires={max_fires}, entry_eq_stop={entry_eq_stop}, cycles={total_cycles}"
    )
    out.append("=" * 90)
    return "\n".join(out)


if __name__ == "__main__":
    print(generate_report())
