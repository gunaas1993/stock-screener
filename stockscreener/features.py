"""Feature engineering shared by the live screener and the back-test.

Everything here is a pure function of data available *as of a date*, so the same
code can be replayed historically without look-ahead.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import MAX_UPSIDE_CAP

# ----------------------------------------------------------------------------------
# Price / momentum
# ----------------------------------------------------------------------------------


def price_feature_panel(px: pd.DataFrame, bench: pd.Series) -> dict[str, pd.DataFrame]:
    """px: dates x tickers (split+dividend adjusted close). bench: same index (e.g. SPY).

    Returns a dict of feature-name -> dates x tickers frames.
    """
    bench = bench.reindex(px.index).ffill()
    ret_6m = px / px.shift(126) - 1
    bench_6m = bench / bench.shift(126) - 1
    delta = px.diff()
    up = delta.clip(lower=0).rolling(14).mean()
    down = (-delta.clip(upper=0)).rolling(14).mean()
    rsi = 100 - 100 / (1 + up / down.replace(0, np.nan))
    return {
        "ret_1m": px / px.shift(21) - 1,
        "ret_3m": px / px.shift(63) - 1,
        "ret_6m": ret_6m,
        # classic 12-1 momentum: skip the most recent month (short-term reversal)
        "ret_12_1": px.shift(21) / px.shift(252) - 1,
        "rs_6m": ret_6m.sub(bench_6m, axis=0),
        "near_high": px / px.rolling(252, min_periods=200).max(),
        "trend": px / px.rolling(200, min_periods=150).mean() - 1,
        "rsi14": rsi,
        "vol_3m": px.pct_change().rolling(63).std() * np.sqrt(252),
    }


# ----------------------------------------------------------------------------------
# Analyst upside, adjusted for how much we should trust it
# ----------------------------------------------------------------------------------


def adjusted_upside(price, target, n_analysts, high=None, low=None):
    """Analyst upside shrunk by coverage and disagreement, and capped.

    * coverage: fewer than ~12 analysts -> shrink towards 0 (sqrt scaling)
    * agreement: a wide high/low target spread -> shrink (analysts disagree)
    * cap: upside beyond MAX_UPSIDE_CAP is usually a stale target, not a real signal
    Works on scalars or aligned pandas Series.
    """
    price = pd.Series(price, dtype="float64") if not isinstance(price, pd.Series) else price
    target = pd.Series(target, index=price.index, dtype="float64") if not isinstance(target, pd.Series) else target
    n = pd.Series(n_analysts, index=price.index, dtype="float64") if not isinstance(n_analysts, pd.Series) else n_analysts
    raw = target / price - 1
    coverage = np.sqrt((n / 12.0).clip(0, 1))
    if high is not None and low is not None:
        disp = ((high - low) / target).clip(lower=0).fillna(0.5)
    else:
        disp = pd.Series(0.5, index=price.index)
    agreement = 1.0 / (1.0 + 0.5 * disp)
    return raw.clip(-0.5, MAX_UPSIDE_CAP) * coverage * agreement


# ----------------------------------------------------------------------------------
# Earnings history (Yahoo `get_earnings_dates` frame)
# ----------------------------------------------------------------------------------


def _reported(ed: pd.DataFrame | None, asof: pd.Timestamp | None) -> pd.DataFrame:
    if ed is None or ed.empty:
        return pd.DataFrame(columns=["Reported EPS", "EPS Estimate", "Surprise(%)"])
    rep = ed[ed["Reported EPS"].notna()].copy()
    idx = pd.to_datetime(rep.index, utc=True).tz_localize(None)
    rep.index = idx
    rep = rep.sort_index()
    if asof is not None:
        rep = rep[rep.index.normalize() < pd.Timestamp(asof).normalize()]  # strictly before: no leakage
    return rep


def surprise_stats(ed: pd.DataFrame | None, asof: pd.Timestamp | None = None, n: int = 4) -> dict:
    rep = _reported(ed, asof).tail(n)
    if len(rep) < 2:
        return {"surprise_avg": np.nan, "beat_rate": np.nan, "surprise_last": np.nan}
    s = (rep["Surprise(%)"] / 100.0).clip(-0.5, 0.5)
    return {"surprise_avg": float(s.mean()), "beat_rate": float((s > 0).mean()), "surprise_last": float(s.iloc[-1])}


def ttm_eps_stats(ed: pd.DataFrame | None, asof: pd.Timestamp) -> dict:
    """Trailing-twelve-month EPS and its YoY growth, from reported quarterly EPS."""
    rep = _reported(ed, asof)
    eps = rep["Reported EPS"].astype(float)
    if len(eps) < 4:
        return {"ttm_eps": np.nan, "eps_growth": np.nan}
    ttm = eps.tail(4).sum()
    out = {"ttm_eps": float(ttm), "eps_growth": np.nan}
    if len(eps) >= 8:
        prev = eps.iloc[-8:-4].sum()
        if abs(prev) > 0.05:
            out["eps_growth"] = float(np.clip((ttm - prev) / abs(prev), -1.0, 2.0))
    return out


# ----------------------------------------------------------------------------------
# Analyst actions (Yahoo `upgrades_downgrades` frame: Firm, ToGrade, Action, price targets)
# ----------------------------------------------------------------------------------


def grade_to_score(grade: str | float) -> float:
    """Map an analyst's rating text to 1 (strong buy) .. 5 (sell); NaN if unknown."""
    if not isinstance(grade, str):
        return np.nan
    g = grade.lower()
    if any(k in g for k in ("strong sell",)):
        return 5.0
    if any(k in g for k in ("underperform", "underweight", "sell", "reduce", "negative", "below")):
        return 4.5 if "reduce" in g or "under" in g else 5.0
    if any(k in g for k in ("strong buy", "top pick", "conviction", "focus list")):
        return 1.0
    if any(k in g for k in ("outperform", "overweight", "buy", "positive", "accumulate", "add", "above", "long-term buy")):
        return 2.0
    if any(k in g for k in ("hold", "neutral", "equal", "perform", "in-line", "inline", "market", "sector", "peer", "mixed", "fair")):
        return 3.0
    return np.nan


def _ud_clean(ud: pd.DataFrame | None) -> pd.DataFrame:
    if ud is None or ud.empty:
        return pd.DataFrame()
    d = ud.copy()
    d.index = pd.to_datetime(d.index, utc=True).tz_localize(None)
    return d.sort_index()


def analyst_action_stats(ud: pd.DataFrame | None, asof: pd.Timestamp | None = None, window_days: int = 90) -> dict:
    """Net upgrades and average price-target change in the trailing window."""
    d = _ud_clean(ud)
    out = {"net_upgrades": np.nan, "pt_rev": np.nan}
    if d.empty:
        return out
    end = pd.Timestamp(asof) if asof is not None else pd.Timestamp.now()
    d = d[(d.index < end) & (d.index >= end - pd.Timedelta(days=window_days))]
    if d.empty:
        return out
    act = d["Action"].astype(str).str.lower()
    ups, downs = int((act == "up").sum()), int((act == "down").sum())
    out["net_upgrades"] = (ups - downs) / max(3, len(d))
    cur = pd.to_numeric(d.get("currentPriceTarget"), errors="coerce")
    pri = pd.to_numeric(d.get("priorPriceTarget"), errors="coerce")
    ok = (cur > 0) & (pri > 0)
    if ok.sum() >= 2:
        out["pt_rev"] = float((cur[ok] / pri[ok] - 1).clip(-0.5, 0.5).mean())
    return out


def split_adjust_targets(ud: pd.DataFrame | None, splits: pd.Series | None) -> pd.DataFrame | None:
    """Yahoo stores historical price targets as quoted at the time (NOT split-adjusted).

    Divide each target by the product of all split ratios that happened after it was issued.
    """
    if ud is None or ud.empty:
        return ud
    d = ud.copy()
    d.index = pd.to_datetime(d.index, utc=True).tz_localize(None)
    if splits is not None and len(splits):
        sp = splits[splits > 0].copy()
        sp.index = pd.to_datetime(sp.index, utc=True).tz_localize(None)
        factor = pd.Series(1.0, index=d.index)
        for dt, ratio in sp.items():
            factor[d.index < dt] *= ratio
        for col in ("currentPriceTarget", "priorPriceTarget"):
            if col in d:
                d[col] = pd.to_numeric(d[col], errors="coerce") / factor
    return d.sort_index()


def pit_consensus(ud: pd.DataFrame | None, asof: pd.Timestamp, price: float | None = None,
                  lookback_days: int = 180, min_firms: int = 3) -> dict:
    """Rebuild the analyst consensus *as it was* on `asof` from each firm's latest action.

    Used only by the back-test (live runs use Yahoo's current consensus numbers).
    Targets further than 0.3x-4x from the then-price are discarded as bad data.
    """
    empty = {"target_mean": np.nan, "target_high": np.nan, "target_low": np.nan, "n_analysts": 0, "rec_score": np.nan}
    d = _ud_clean(ud)
    if d.empty:
        return empty
    d = d[(d.index < asof) & (d.index >= asof - pd.Timedelta(days=lookback_days))]
    if d.empty:
        return empty
    latest = d.groupby("Firm").tail(1)
    tgt = pd.to_numeric(latest["currentPriceTarget"], errors="coerce")
    tgt = tgt[tgt > 0]
    if price and price > 0:
        tgt = tgt[(tgt > 0.3 * price) & (tgt < 4.0 * price)]
    grades = latest["ToGrade"].map(grade_to_score).dropna()
    out = dict(empty)
    if len(tgt) >= min_firms:
        out.update(target_mean=float(tgt.mean()), target_high=float(tgt.max()), target_low=float(tgt.min()), n_analysts=int(len(tgt)))
    if len(grades) >= min_firms:
        out["rec_score"] = float(5.0 - grades.mean())
    return out
