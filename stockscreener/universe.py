"""S&P 500 constituents (from Wikipedia), normalised for Yahoo Finance tickers."""
from __future__ import annotations

import io
from pathlib import Path

import pandas as pd
import requests

from .cache import cached
from .config import DUPLICATE_SHARE_CLASSES, MAG7, USER_AGENT

WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
FALLBACK = Path(__file__).parent / "sp500_fallback.csv"  # committed snapshot, used if Wikipedia is unreachable


def _download() -> pd.DataFrame:
    try:
        resp = requests.get(WIKI_URL, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        table = pd.read_html(io.StringIO(resp.text))[0]
        return pd.DataFrame(
            {
                "ticker": table["Symbol"].str.replace(".", "-", regex=False).str.strip(),
                "name": table["Security"],
                "sector": table["GICS Sector"],
                "industry": table["GICS Sub-Industry"],
            }
        )
    except Exception as e:  # network blocked, page layout changed, ...
        print(f"  universe download failed ({e}); using bundled fallback list")
        return pd.read_csv(FALLBACK)


def get_sp500(refresh: bool = False) -> pd.DataFrame:
    df = cached("sp500_universe", ttl_hours=24 * 7, fn=_download, refresh=refresh)
    df = df[~df["ticker"].isin(DUPLICATE_SHARE_CLASSES)].reset_index(drop=True)
    df["is_mag7"] = df["ticker"].isin(MAG7)
    missing = set(MAG7) - set(df["ticker"])
    if missing:
        raise RuntimeError(f"Mag 7 tickers missing from universe: {missing}")
    return df
