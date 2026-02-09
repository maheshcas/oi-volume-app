import os
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

    session = requests.Session()
    session.headers.update(HEADERS)

    # Optional cookie override via env var (do not hardcode cookies)
    cookie = os.getenv("NSE_COOKIE")
    if cookie:
        session.headers["Cookie"] = cookie

    # Prime cookies via the homepage first
    session.get("https://www.nseindia.com", timeout=10)

    def _attempt():
        r = session.get(BASE_URL, params=params, timeout=10, headers=API_HEADERS)
        r.raise_for_status()
        try:
            return r.json()
        except Exception:
            return None

    data = _attempt()
    if not data:
        time.sleep(0.8)
        data = _attempt()

    if not data:
        raise ValueError("NSE returned empty or invalid JSON (possibly blocked).")

    return data


def fetch_index_data():
    """
    Fetch live NSE index data (All)
    """
    session = requests.Session()
    session.headers.update(HEADERS)

    cookie = os.getenv("NSE_COOKIE")
    if cookie:
        session.headers["Cookie"] = cookie

    session.get("https://www.nseindia.com", timeout=10)
    params = {"functionName": "getIndexData", "type": "All"}
    r = session.get(INDEX_URL, params=params, timeout=10, headers=API_HEADERS)
    r.raise_for_status()
    try:
        return r.json()
    except Exception:
        raise ValueError("NSE returned empty or invalid JSON (index data).")


def fetch_option_chain_contract_info(symbol: str):
    """
    Fetch option chain contract info (expiry dates, strike prices).
    """
    session = requests.Session()
    session.headers.update(HEADERS)

    cookie = os.getenv("NSE_COOKIE")
    if cookie:
        session.headers["Cookie"] = cookie

    session.get("https://www.nseindia.com/option-chain", timeout=10)
    params = {"symbol": symbol}
    r = session.get(CONTRACT_INFO_URL, params=params, timeout=10, headers=API_HEADERS)
    r.raise_for_status()
    try:
        return r.json()
    except Exception:
        content_type = r.headers.get("Content-Type", "")
        sample = (r.text or "")[:120].replace("\n", " ").strip()
        raise ValueError(
            f"NSE returned empty or invalid JSON (contract info). Content-Type={content_type} Sample={sample}"
        )
