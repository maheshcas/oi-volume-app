import os
import threading
import time
from typing import Optional
import requests

BASE_URL = "https://www.nseindia.com/api/option-chain-v3"
INDEX_URL = "https://www.nseindia.com/api/NextApi/apiClient"
CONTRACT_INFO_URL = "https://www.nseindia.com/api/option-chain-contract-info"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:147.0) Gecko/20100101 Firefox/147.0",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Referer": "https://www.nseindia.com/option-chain",
}

API_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "X-Requested-With": "XMLHttpRequest",
}

_SESSION_LOCK = threading.Lock()
_SESSION: requests.Session | None = None
_SESSION_LAST_PRIME_TS = 0.0
_SESSION_PRIME_INTERVAL_SEC = 600
_LAST_GOOD_CACHE: dict[str, tuple[float, dict]] = {}
_LAST_GOOD_CACHE_TTL_SEC = 120


def _create_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS)
    cookie = os.getenv("NSE_COOKIE")
    if cookie:
        # Optional override, but session cookies will still auto-refresh.
        session.headers["Cookie"] = cookie
    return session


def _ensure_session(force_new: bool = False) -> requests.Session:
    global _SESSION
    with _SESSION_LOCK:
        if force_new or _SESSION is None:
            _SESSION = _create_session()
        return _SESSION


def _prime_session(session: requests.Session, force: bool = False) -> None:
    global _SESSION_LAST_PRIME_TS
    now = time.time()
    if not force and (now - _SESSION_LAST_PRIME_TS) < _SESSION_PRIME_INTERVAL_SEC:
        return
    # Prime Akamai cookies before API calls.
    session.get("https://www.nseindia.com", timeout=10)
    session.get("https://www.nseindia.com/option-chain", timeout=10)
    _SESSION_LAST_PRIME_TS = now


def _cache_key(url: str, params: dict) -> str:
    parts = [f"{k}={params[k]}" for k in sorted(params.keys())]
    return f"{url}?{'&'.join(parts)}"


def _request_json(url: str, params: dict, context: str) -> dict:
    key = _cache_key(url, params)
    last_error = "Unknown error"

    for attempt in range(3):
        force_new = attempt > 0
        session = _ensure_session(force_new=force_new)
        try:
            _prime_session(session, force=force_new)
            response = session.get(url, params=params, timeout=10, headers=API_HEADERS)
            if response.status_code in (401, 403):
                last_error = f"HTTP {response.status_code}"
                continue
            response.raise_for_status()
            payload = response.json()
            if not payload:
                last_error = "Empty JSON payload"
                continue
            _LAST_GOOD_CACHE[key] = (time.time(), payload)
            return payload
        except Exception as exc:
            last_error = str(exc)
            time.sleep(0.5)

    cached = _LAST_GOOD_CACHE.get(key)
    if cached and (time.time() - cached[0]) <= _LAST_GOOD_CACHE_TTL_SEC:
        return cached[1]

    raise ValueError(f"NSE {context} failed after retries: {last_error}")


def fetch_option_chain(symbol: str, expiry: Optional[str] = None, instrument_type: str = "Indices"):
    """
    Fetch NSE option chain JSON for given symbol and expiry (optional)
    """
    params = {
        "type": instrument_type,
        "symbol": symbol,
    }
    if expiry:
        params["expiry"] = expiry

    return _request_json(BASE_URL, params, "option chain")


def fetch_index_data():
    """
    Fetch live NSE index data (All)
    """
    params = {"functionName": "getIndexData", "type": "All"}
    return _request_json(INDEX_URL, params, "index data")


def fetch_option_chain_contract_info(symbol: str):
    """
    Fetch option chain contract info (expiry dates, strike prices).
    """
    params = {"symbol": symbol}
    return _request_json(CONTRACT_INFO_URL, params, "contract info")
