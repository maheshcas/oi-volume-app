from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

import requests

logger = logging.getLogger(__name__)

BSE_BASE = "https://api.bseindia.com/BseIndiaAPI/api"
EXPIRY_URL = f"{BSE_BASE}/ddlExpiry_New/w?scrip_cd=1"
CHAIN_URL = f"{BSE_BASE}/DerivOptionChain_IV/w"
SCRIP_CD = "1"
REQUEST_TIMEOUT = 10

# BSE blocks bare requests. Keep these browser-like.
BSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:148.0) "
        "Gecko/20100101 Firefox/148.0"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.bseindia.com",
    "Referer": "https://www.bseindia.com/",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
}


@dataclass
class StrikeData:
    strike_price: float
    ce_oi: int = 0
    pe_oi: int = 0
    ce_change_oi: int = 0
    pe_change_oi: int = 0
    ce_ltp: float = 0.0
    pe_ltp: float = 0.0
    ce_iv: float = 0.0
    pe_iv: float = 0.0
    ce_volume: int = 0
    pe_volume: int = 0


@dataclass
class OptionChainData:
    symbol: str = "SENSEX"
    spot_price: float = 0.0
    expiry_date: str = ""
    timestamp: str = ""
    strikes: list[StrikeData] = field(default_factory=list)
    total_ce_oi: int = 0
    total_pe_oi: int = 0
    total_ce_volume: int = 0
    total_pe_volume: int = 0
    fetch_error: Optional[str] = None


def _parse_int(value: str) -> int:
    if not value or not str(value).strip():
        return 0
    try:
        return int(str(value).replace(",", "").replace(" ", "").split(".")[0])
    except (TypeError, ValueError, AttributeError):
        return 0


def _parse_float(value: str) -> float:
    if not value or not str(value).strip():
        return 0.0
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError, AttributeError):
        return 0.0


def _nearest_expiry(expiry_list: list[dict]) -> Optional[str]:
    today = date.today()
    upcoming: list[tuple[date, str]] = []
    for row in expiry_list:
        raw = str(row.get("ORDERDTTM") or "")
        try:
            dt = datetime.strptime(raw.split()[0], "%m/%d/%Y").date()
            label = str(row.get("ExpiryDate") or "").strip()
            if label:
                upcoming.append((dt, label))
        except (ValueError, IndexError):
            continue

    future = [(dt, label) for dt, label in upcoming if dt >= today]
    if future:
        return min(future, key=lambda item: item[0])[1]
    if upcoming:
        return upcoming[0][1]
    return None


def _format_expiry_for_url(expiry_label: str) -> str:
    return str(expiry_label or "").strip().replace(" ", "+")


def _parse_timestamp(ason: dict) -> str:
    raw = str((ason or {}).get("DT_TM") or "").strip()
    try:
        cleaned = raw.replace("|", "").strip()
        dt = datetime.strptime(cleaned, "%d %b %Y  %H:%M")
        return dt.strftime("%Y-%m-%dT%H:%M:00")
    except ValueError:
        return raw


def fetch_expiry_and_spot(session: requests.Session) -> tuple[list[dict], float, list[dict]]:
    response = session.get(EXPIRY_URL, headers=BSE_HEADERS, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    payload = response.json()

    expiry_list = payload.get("Table1", [])
    spot_price = _parse_float(((payload.get("Table2") or [{}])[0]).get("UlaValue", "0"))
    strike_list = payload.get("Table", [])
    return expiry_list, spot_price, strike_list


def fetch_option_chain(session: requests.Session, expiry_label: str) -> dict:
    expiry_param = _format_expiry_for_url(expiry_label)
    url = f"{CHAIN_URL}?Expiry={expiry_param}&scrip_cd={SCRIP_CD}&strprice=0"
    response = session.get(url, headers=BSE_HEADERS, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.json()


def normalise_chain(raw_chain: dict, spot_price: float, expiry_label: str) -> OptionChainData:
    result = OptionChainData(
        spot_price=spot_price,
        expiry_date=expiry_label,
        timestamp=_parse_timestamp(raw_chain.get("ASON", {})),
    )

    rows = raw_chain.get("Table", [])
    strikes: list[StrikeData] = []
    for row in rows:
        strike = _parse_float(row.get("Strike_Price1", "0"))
        if strike <= 0:
            continue

        strikes.append(
            StrikeData(
                strike_price=strike,
                ce_oi=_parse_int(row.get("C_Open_Interest", "")),
                pe_oi=_parse_int(row.get("Open_Interest", "")),
                ce_change_oi=_parse_int(row.get("C_Absolute_Change_OI", "")),
                pe_change_oi=_parse_int(row.get("Absolute_Change_OI", "")),
                ce_ltp=_parse_float(row.get("C_Last_Trd_Price", "")),
                pe_ltp=_parse_float(row.get("Last_Trd_Price", "")),
                ce_iv=_parse_float(row.get("C_IV", "")),
                pe_iv=_parse_float(row.get("IV", "")),
                ce_volume=_parse_int(row.get("C_Vol_Traded", "")),
                pe_volume=_parse_int(row.get("Vol_Traded", "")),
            )
        )

    strikes.sort(key=lambda item: item.strike_price)
    result.strikes = strikes
    result.total_ce_oi = _parse_int(raw_chain.get("tot_C_Open_Interest", "")) or sum(item.ce_oi for item in strikes)
    result.total_pe_oi = _parse_int(raw_chain.get("tot_Open_Interest", "")) or sum(item.pe_oi for item in strikes)
    result.total_ce_volume = _parse_int(raw_chain.get("tot_C_Vol_Traded", "")) or sum(item.ce_volume for item in strikes)
    result.total_pe_volume = _parse_int(raw_chain.get("tot_Vol_Traded", "")) or sum(item.pe_volume for item in strikes)
    return result


def get_sensex_option_chain(expiry_override: Optional[str] = None) -> OptionChainData:
    session = requests.Session()
    try:
        expiry_list, spot_price, _ = fetch_expiry_and_spot(session)
        if not expiry_list:
            return OptionChainData(fetch_error="BSE returned empty expiry list")

        expiry_label = expiry_override or _nearest_expiry(expiry_list)
        if not expiry_label:
            return OptionChainData(fetch_error="Could not determine nearest expiry")

        raw_chain = fetch_option_chain(session, expiry_label)
        chain = normalise_chain(raw_chain, spot_price, expiry_label)
        logger.info(
            "SENSEX chain fetched: expiry=%s spot=%.2f strikes=%d ce_oi=%d pe_oi=%d",
            expiry_label,
            spot_price,
            len(chain.strikes),
            chain.total_ce_oi,
            chain.total_pe_oi,
        )
        return chain
    except requests.exceptions.Timeout:
        return OptionChainData(fetch_error="BSE API timed out")
    except requests.exceptions.HTTPError as exc:
        status_code = getattr(exc.response, "status_code", "unknown")
        return OptionChainData(fetch_error=f"BSE API HTTP error: {status_code}")
    except requests.exceptions.RequestException as exc:
        return OptionChainData(fetch_error=f"BSE API network error: {exc}")
    except (KeyError, TypeError, ValueError) as exc:
        logger.error("BSE response parse error: %s", exc, exc_info=True)
        return OptionChainData(fetch_error=f"BSE response parse error: {exc}")
    finally:
        session.close()


def chain_to_sr_input(chain: OptionChainData) -> dict:
    if chain.fetch_error:
        return {"error": chain.fetch_error}

    return {
        "symbol": chain.symbol,
        "spot_price": chain.spot_price,
        "expiry_date": chain.expiry_date,
        "timestamp": chain.timestamp,
        "total_ce_oi": chain.total_ce_oi,
        "total_pe_oi": chain.total_pe_oi,
        "total_ce_volume": chain.total_ce_volume,
        "total_pe_volume": chain.total_pe_volume,
        "strikes": [
            {
                "strike": item.strike_price,
                "ce_oi": item.ce_oi,
                "pe_oi": item.pe_oi,
                "ce_change_oi": item.ce_change_oi,
                "pe_change_oi": item.pe_change_oi,
                "ce_ltp": item.ce_ltp,
                "pe_ltp": item.pe_ltp,
                "ce_iv": item.ce_iv,
                "pe_iv": item.pe_iv,
                "ce_volume": item.ce_volume,
                "pe_volume": item.pe_volume,
            }
            for item in chain.strikes
        ],
    }
