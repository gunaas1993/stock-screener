"""Per-ticker data sources. Each returns a flat dict and never raises (missing -> NaN)."""
from __future__ import annotations

import json
import random
import re
import threading
import time

import numpy as np
import pandas as pd
import requests
import yfinance as yf

from . import features
from .config import PERPLEXITY_API_KEY, USER_AGENT

NaN = float("nan")


class _Throttle:
    """Minimum gap between requests to the same site, shared across threads."""

    def __init__(self, gap: float):
        self.gap, self._next, self._lock = gap, 0.0, threading.Lock()

    def wait(self):
        with self._lock:
            now = time.monotonic()
            delay = max(0.0, self._next - now)
            self._next = max(now, self._next) + self.gap * random.uniform(0.8, 1.3)
        if delay:
            time.sleep(delay)


_ZACKS, _FINVIZ = _Throttle(0.7), _Throttle(0.6)
_HEADERS = {"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}


def _get(url: str, throttle: _Throttle, retries: int = 3) -> str | None:
    for attempt in range(retries):
        throttle.wait()
        try:
            r = requests.get(url, headers=_HEADERS, timeout=20)
            if r.status_code == 200:
                return r.text
            if r.status_code in (403, 429):
                time.sleep(3 * (attempt + 1))
        except requests.RequestException:
            time.sleep(1.5 * (attempt + 1))
    return None


def _num(text: str | None) -> float:
    if not text:
        return NaN
    t = text.strip().replace(",", "").replace("%", "")
    try:
        return float(t)
    except ValueError:
        return NaN


# ---------------------------------------------------------------------------- Zacks
def zacks(ticker: str) -> dict:
    """Zacks Rank: 1 = Strong Buy ... 5 = Strong Sell."""
    html = _get(f"https://www.zacks.com/stock/quote/{ticker}", _ZACKS)
    if not html:
        return {"zacks": NaN}
    m = re.search(r'rank_view">\s*(\d)-', html)
    return {"zacks": float(m.group(1)) if m else NaN}


# ---------------------------------------------------------------------------- Finviz
def finviz(ticker: str) -> dict:
    """Finviz snapshot: consensus target, mean recommendation (1-5), 5y EPS growth estimate."""
    out = {"fv_target": NaN, "fv_recom": NaN, "ltg": NaN}
    html = _get(f"https://finviz.com/quote.ashx?t={ticker}", _FINVIZ)
    if not html:
        return out
    cells = re.findall(r'<td[^>]*class="[^"]*snapshot-td2[^"]*"[^>]*>(.*?)</td>', html, re.S)
    txt = [re.sub(r"<[^>]+>", "", c).strip() for c in cells]
    d = dict(zip(txt[0::2], txt[1::2]))
    out["fv_target"] = _num(d.get("Target Price"))
    out["fv_recom"] = _num(d.get("Recom"))
    ltg = _num(d.get("EPS next 5Y"))
    out["ltg"] = ltg / 100.0 if not np.isnan(ltg) else NaN
    return out


# ---------------------------------------------------------------------------- Yahoo extras
def yahoo_extras(ticker: str) -> dict:
    """Estimate revisions, analyst actions and earnings-surprise history from Yahoo."""
    out = {"eps_rev": NaN, "net_upgrades": NaN, "pt_rev": NaN, "surprise_avg": NaN, "beat_rate": NaN, "next_earnings": pd.NaT}
    t = yf.Ticker(ticker)
    try:
        tr = t.eps_trend
        for period in ("+1y", "0y"):
            if period in tr.index:
                cur, ago = tr.loc[period, "current"], tr.loc[period, "90daysAgo"]
                if pd.notna(cur) and pd.notna(ago) and abs(ago) > 0.01:
                    out["eps_rev"] = float((cur - ago) / abs(ago))
                    break
    except Exception:
        pass
    try:
        out.update(features.analyst_action_stats(t.upgrades_downgrades))
    except Exception:
        pass
    try:
        ed = t.get_earnings_dates(limit=12)
        out.update(features.surprise_stats(ed))
        future = ed[ed["Reported EPS"].isna()].index
        if len(future):
            nxt = pd.Timestamp(min(future))
            out["next_earnings"] = nxt.tz_localize(None) if nxt.tzinfo else nxt
    except Exception:
        pass
    return out


# ---------------------------------------------------------------------------- Perplexity (optional)
def perplexity_smart_score(ticker: str) -> dict:
    """TipRanks Smart Score (1-10) via Perplexity's web-connected API. Needs PERPLEXITY_API_KEY."""
    if not PERPLEXITY_API_KEY:
        return {"smart_score": NaN}
    prompt = (
        f"What is the current TipRanks Smart Score (integer 1-10) for the stock {ticker}? "
        'Reply with ONLY JSON like {"smart_score": 7}. Use null if you cannot find it.'
    )
    try:
        r = requests.post(
            "https://api.perplexity.ai/chat/completions",
            headers={"Authorization": f"Bearer {PERPLEXITY_API_KEY}", "Content-Type": "application/json"},
            json={"model": "sonar", "messages": [{"role": "user", "content": prompt}], "temperature": 0},
            timeout=45,
        )
        text = r.json()["choices"][0]["message"]["content"]
        m = re.search(r'"smart_score"\s*:\s*(\d+)', text)
        if m and 1 <= int(m.group(1)) <= 10:
            return {"smart_score": float(m.group(1))}
    except Exception:
        pass
    return {"smart_score": NaN}


def enrich(ticker: str) -> dict:
    """All stage-2 data for one ticker."""
    row: dict = {"ticker": ticker}
    for fn in (yahoo_extras, zacks, finviz, perplexity_smart_score):
        row.update(fn(ticker))
    return row
