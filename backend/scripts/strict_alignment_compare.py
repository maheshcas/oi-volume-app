from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen


DEFAULT_LOCAL_BASE = "http://127.0.0.1:8000"
DEFAULT_PROD_BASE = "https://oi-volume-backend-production.up.railway.app"


def _fetch_json(base: str, symbol: str) -> dict[str, Any]:
    query = urlencode({"symbol": symbol})
    url = f"{base.rstrip('/')}/api/v2/intelligence/summary?{query}"
    with urlopen(url, timeout=20) as response:  # noqa: S310 - controlled internal/prod URLs
        return json.loads(response.read().decode("utf-8"))


def _pick(payload: dict[str, Any]) -> dict[str, Any]:
    market_state = payload.get("market_state", {}) if isinstance(payload.get("market_state"), dict) else {}
    strike_intelligence = (
        market_state.get("strike_intelligence", {})
        if isinstance(market_state.get("strike_intelligence"), dict)
        else {}
    )
    return {
        "meta": payload.get("meta", {}),
        "market_state": {
            "support": market_state.get("support"),
            "resistance": market_state.get("resistance"),
            "previous_support": market_state.get("previous_support"),
            "current_support": market_state.get("current_support"),
            "previous_resistance": market_state.get("previous_resistance"),
            "current_resistance": market_state.get("current_resistance"),
            "sr_previous_support_anchor_used": market_state.get("sr_previous_support_anchor_used"),
            "sr_previous_support_anchor_source": market_state.get("sr_previous_support_anchor_source"),
            "sr_previous_resistance_anchor_used": market_state.get("sr_previous_resistance_anchor_used"),
            "sr_previous_resistance_anchor_source": market_state.get("sr_previous_resistance_anchor_source"),
            "sr_anchor_age_seconds": market_state.get("sr_anchor_age_seconds"),
            "seeded_flush_last_fired_at": market_state.get("seeded_flush_last_fired_at"),
            "cycle_count_since_flush": market_state.get("cycle_count_since_flush"),
            "support_transition_badge": market_state.get("support_transition_badge"),
            "resistance_transition_badge": market_state.get("resistance_transition_badge"),
            "session_phase": market_state.get("session_phase"),
            "trade_readiness_v2": market_state.get("trade_readiness_v2"),
            "readiness_state_v2": market_state.get("readiness_state_v2"),
        },
        "strike_intelligence": {
            "entry_signal": strike_intelligence.get("entry_signal"),
            "directional_signal": strike_intelligence.get("directional_signal"),
            "price_magnet_strike": strike_intelligence.get("price_magnet_strike"),
            "max_pain_strike": strike_intelligence.get("max_pain_strike"),
        },
    }


def _diff(a: Any, b: Any, path: str = "") -> list[dict[str, Any]]:
    diffs: list[dict[str, Any]] = []
    if isinstance(a, dict) and isinstance(b, dict):
        keys = sorted(set(a.keys()) | set(b.keys()))
        for key in keys:
            child = f"{path}.{key}" if path else key
            diffs.extend(_diff(a.get(key), b.get(key), child))
        return diffs
    if a != b:
        diffs.append({"field": path, "local": a, "prod": b})
    return diffs


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare local vs prod intelligence anchors.")
    parser.add_argument("--symbol", default="NIFTY")
    parser.add_argument("--local-base", default=DEFAULT_LOCAL_BASE)
    parser.add_argument("--prod-base", default=DEFAULT_PROD_BASE)
    parser.add_argument("--out-dir", default="logs")
    args = parser.parse_args()

    local = _fetch_json(args.local_base, args.symbol.upper())
    prod = _fetch_json(args.prod_base, args.symbol.upper())

    local_compact = _pick(local)
    prod_compact = _pick(prod)
    diffs = _diff(local_compact, prod_compact)

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "symbol": args.symbol.upper(),
        "local_base": args.local_base,
        "prod_base": args.prod_base,
        "diff_count": len(diffs),
        "diffs": diffs,
        "local": local_compact,
        "prod": prod_compact,
    }

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = out_dir / f"alignment_diff_{args.symbol.upper()}_{timestamp}.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"diff_count={len(diffs)}")
    print(f"report={out_path}")
    if diffs:
        for item in diffs[:30]:
            print(f"{item['field']}: local={item['local']} prod={item['prod']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

