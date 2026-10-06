"""Live pipeline: universe -> stage 1 (everyone, Yahoo) -> stage 2 (shortlist, deep) -> final scores."""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd
import yfinance as yf

from . import features, sources
from .cache import cached
from .config import MAG7, MIN_ANALYSTS, STAGE2_POOL, TOP_N
from .scoring import score_frame
from .universe import get_sp500

INFO_FIELDS = {
    "currentPrice": "price", "regularMarketPrice": "price_alt", "trailingPE": "pe", "forwardPE": "fwd_pe",
    "trailingEps": "eps", "forwardEps": "fwd_eps", "targetMeanPrice": "target_mean", "targetHighPrice": "target_high",
    "targetLowPrice": "target_low", "numberOfAnalystOpinions": "n_analysts", "recommendationMean": "rec_mean",
    "revenueGrowth": "rev_growth", "earningsGrowth": "eps_growth", "trailingPegRatio": "peg", "pegRatio": "peg_alt",
    "freeCashflow": "fcf", "marketCap": "mcap", "operatingMargins": "op_margin", "totalRevenue": "revenue",
    "fiftyTwoWeekHigh": "hi52", "fiftyTwoWeekLow": "lo52",
}


def _log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def _fetch_info(ticker: str) -> dict:
    for attempt in range(3):
        try:
            info = yf.Ticker(ticker).info
            if info and len(info) > 5:
                row = {new: info.get(old) for old, new in INFO_FIELDS.items()}
                row["ticker"] = ticker
                return row
        except Exception:
            pass
        time.sleep(1.0 * (attempt + 1))
    return {"ticker": ticker}


def _parallel(fn, items, workers: int, label: str) -> list[dict]:
    out, done = [], 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(fn, i): i for i in items}
        for f in as_completed(futs):
            try:
                out.append(f.result())
            except Exception as e:  # one bad ticker must not kill the run
                out.append({"ticker": futs[f]})
                _log(f"  {label} failed for {futs[f]}: {e}")
            done += 1
            if done % 50 == 0 or done == len(items):
                _log(f"  {label}: {done}/{len(items)}")
    return out


def _stage1(universe: pd.DataFrame, refresh: bool) -> pd.DataFrame:
    tickers = universe["ticker"].tolist()

    _log(f"Stage 1: fundamentals + analyst targets for {len(tickers)} stocks")
    info = pd.DataFrame(cached("stage1_info", 6, lambda: _parallel(_fetch_info, tickers, 8, "info"), refresh))

    _log("Stage 1: price history for momentum")
    def _prices():
        raw = yf.download(tickers + ["SPY"], period="2y", auto_adjust=True, progress=False, threads=True)
        return raw["Close"]
    px = cached("stage1_prices", 6, _prices, refresh)
    bench = px["SPY"]
    px = px.drop(columns=["SPY"]).dropna(how="all", axis=1)
    panel = features.price_feature_panel(px, bench)
    last = pd.DataFrame({k: v.iloc[-1] for k, v in panel.items()})
    last["last_close"] = px.ffill().iloc[-1]
    last.index.name = "ticker"

    df = universe.merge(info, on="ticker", how="left").merge(last.reset_index(), on="ticker", how="left")
    df["price"] = df["price"].fillna(df["price_alt"]).fillna(df["last_close"])
    df["peg"] = df["peg"].fillna(df["peg_alt"])
    for c in ("pe", "fwd_pe", "eps", "fwd_eps", "target_mean", "target_high", "target_low", "n_analysts", "rec_mean",
              "rev_growth", "eps_growth", "peg", "fcf", "mcap", "op_margin", "revenue", "hi52", "lo52"):
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df["upside"] = df["target_mean"] / df["price"] - 1
    df["adj_upside"] = features.adjusted_upside(df["price"], df["target_mean"], df["n_analysts"].fillna(0), df["target_high"], df["target_low"])
    base_eps = df["fwd_eps"].where(df["fwd_eps"].notna(), df["eps"])
    df["earn_yield"] = base_eps / df["price"]
    df["fcf_yield"] = df["fcf"] / df["mcap"]
    df["fwd_eps_growth"] = ((df["fwd_eps"] / df["eps"] - 1).where(df["eps"] > 0)).clip(-1, 3)
    df["rev_growth"] = df["rev_growth"].clip(-0.5, 2.0)
    df["eps_growth"] = df["eps_growth"].clip(-1.0, 3.0)
    df["rec_score"] = 5.0 - df["rec_mean"]
    return df


def _stage2(df: pd.DataFrame, refresh: bool) -> pd.DataFrame:
    pool = df.sort_values("buy_score", ascending=False)
    pool = pool[pool["n_analysts"].fillna(0) >= 3].head(STAGE2_POOL)
    tickers = sorted(set(pool["ticker"]) | set(MAG7))
    _log(f"Stage 2: Zacks, Finviz, estimate revisions, upgrades, earnings surprises for {len(tickers)} leaders")
    extra = pd.DataFrame(cached("stage2_extra", 6, lambda: _parallel(sources.enrich, tickers, 6, "enrich"), refresh))
    extra = extra[extra["ticker"].isin(tickers)]

    df = df.drop(columns=[c for c in extra.columns if c != "ticker" and c in df.columns]).merge(extra, on="ticker", how="left")
    df["stage2"] = df["ticker"].isin(tickers)

    # Second consensus opinion: blend Finviz target / recommendation with Yahoo's when available.
    t = df[["target_mean", "fv_target"]].apply(pd.to_numeric, errors="coerce")
    df["target_avg"] = t.mean(axis=1)
    df["target_avg"] = df["target_avg"].fillna(df["target_mean"])
    df["upside"] = df["target_avg"] / df["price"] - 1
    df["adj_upside"] = features.adjusted_upside(df["price"], df["target_avg"], df["n_analysts"].fillna(0), df["target_high"], df["target_low"])
    df["rec_score"] = 5.0 - df[["rec_mean", "fv_recom"]].apply(pd.to_numeric, errors="coerce").mean(axis=1)
    return df


def run(refresh: bool = False) -> pd.DataFrame:
    universe = get_sp500()
    df = _stage1(universe, refresh)
    df = score_frame(df)           # preliminary score from Yahoo data only (all ~500)
    df = _stage2(df, refresh)      # deep data for the leaders + Mag 7
    df["target_avg"] = df.get("target_avg", df["target_mean"])
    df = score_frame(df)           # final score; stage-2 fields use fixed scales so ranks are unbiased

    # Only stocks that went through stage 2 (or Mag 7) are eligible for the final list.
    enriched = df["zacks"].notna() | df["fv_target"].notna() | df["ticker"].isin(MAG7) if "zacks" in df else df["ticker"].isin(MAG7)
    df["eligible"] = enriched & (df["n_analysts"].fillna(0) >= MIN_ANALYSTS) & (df["target_avg"] > 0)

    df["section"] = np.where(df["is_mag7"], "MAG7", "OTHER")
    others = df[(df["section"] == "OTHER") & df["eligible"]].sort_values("buy_score", ascending=False).head(TOP_N)
    df["in_top"] = df["ticker"].isin(others["ticker"])
    df["score_rank"] = df["buy_score"].rank(ascending=False, method="min")
    _log(f"Done. {len(others)} stocks selected + {int(df['is_mag7'].sum())} Mag 7.")
    return df
