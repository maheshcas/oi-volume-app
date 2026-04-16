from typing import Optional

from app.infrastructure.feeds.nse_client import fetch_index_data as _fetch_index_data
from app.infrastructure.feeds.nse_client import fetch_option_chain as _fetch_option_chain


def fetch_option_chain_data(symbol: str, expiry: Optional[str], instrument_type: str) -> dict:
    return _fetch_option_chain(symbol=symbol, expiry=expiry, instrument_type=instrument_type)


def fetch_index_data(names: Optional[str] = None) -> dict:
    raw = _fetch_index_data()
    if not names:
        return raw
    requested = {name.strip().upper() for name in names.split(",") if name.strip()}
    data = raw.get("data", [])
    filtered = [row for row in data if str(row.get("indexName", "")).upper() in requested]
    return {"data": filtered}
