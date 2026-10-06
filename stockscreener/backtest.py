"""Point-in-time back-test: did high-scoring stocks actually move?

At each month-end we rebuild the score using ONLY information that existed on that date:
  * momentum / trend / RSI            from prices
  * trailing earnings yield + growth  from quarterly EPS reported before that date
  * earnings beat history             from surprises reported before that date
  * analyst target / rating / revisions from each firm's latest action before that date
Then we measure forward 1-month and 3-month returns, and the reaction to the next earnings report.

Known limits (also printed in the report): today's S&P 500 membership is used (survivorship bias),
and free data has no history for Zacks Rank, TipRanks, Finviz, revenue growth or FCF, so those
inputs are validated only indirectly.
"""
from __future__ import annotations

import time

import numpy as np
import pandas as pd
import yfinance as yf
from scipy.stats import spearmanr

from . import features
from .cache import cached
from .config import COMPONENTS, OUTPUT_DIR, TOP_N, WEIGHTS
from .pipeline import _log, _parallel
from .scoring import score_frame
from .universe import get_sp500

COMPS = list(COMPONENTS)


# ------------------------------------------------------------------------------ data
def _ticker_history(tk: str) -> dict:
    t = yf.Ticker(tk)
    out = {"ticker": tk, "ed": None, "ud": None}
    for _ in range(2):
        try:
            out["ed"] = t.get_earnings_dates(limit=60)
            ud, sp = t.upgrades_downgrades, t.splits
            out["ud"] = features.split_adjust_targets(ud, sp)
            break
        except Exception:
            time.sleep(1.0)
    return out


def _load(years: float, refresh: bool):
    univ = get_sp500()
    tickers = univ["ticker"].tolist()

    def dl():
        raw = yf.download(tickers + ["SPY"], period=f"{int(np.ceil(years)) + 2}y", auto_adjust=False, progress=False, threads=True)
        return raw["Close"], raw["Adj Close"]

    _log("Back-test: downloading price history")
    close, adj = cached(f"bt_prices_{years}", 24, dl, refresh)
    _log("Back-test: downloading earnings + analyst history (cached 3 days)")
    hist = cached("bt_hist", 72, lambda: {d["ticker"]: d for d in _parallel(_ticker_history, tickers, 8, "history")}, refresh)
    return univ, close, adj, hist


# ------------------------------------------------------------------------------ snapshots
def _build_snapshots(univ, close, adj, hist, years):
    spy = adj["SPY"]
    adjx, closex = adj.drop(columns="SPY"), close.drop(columns="SPY")
    panel = features.price_feature_panel(adjx, spy)
    fwd = {h: adjx.shift(-h) / adjx - 1 for h in (21, 63)}
    spy_fwd = {h: spy.shift(-h) / spy - 1 for h in (21, 63)}

    idx = adjx.index
    month_ends = pd.Series(idx, index=idx).groupby([idx.year, idx.month]).last()
    cutoff = idx[-1] - pd.Timedelta(days=int(years * 365))
    dates = [d for d in month_ends if d >= cutoff and d <= idx[-64]]
    sector = univ.set_index("ticker")["sector"]
    _log(f"Back-test: scoring {len(dates)} month-ends ({dates[0].date()} -> {dates[-1].date()})")

    frames = []
    for n, t in enumerate(dates, 1):
        base = pd.DataFrame({k: v.loc[t] for k, v in panel.items()})
        price = closex.loc[t]
        base["price"] = price
        base = base[base["price"].notna() & base["ret_6m"].notna()]
        recs = []
        for tk in base.index:
            h = hist.get(tk, {})
            ed, ud = h.get("ed"), h.get("ud")
            r = {"ticker": tk}
            r.update(features.ttm_eps_stats(ed, t))
            r.update(features.surprise_stats(ed, t))
            r.update(features.analyst_action_stats(ud, t))
            r.update(features.pit_consensus(ud, t, float(base.at[tk, "price"])))
            recs.append(r)
        extra = pd.DataFrame(recs).set_index("ticker")
        df = base.join(extra)
        df["sector"] = sector.reindex(df.index)
        df["earn_yield"] = df["ttm_eps"] / df["price"]
        df["adj_upside"] = features.adjusted_upside(df["price"], df["target_mean"], df["n_analysts"].fillna(0), df["target_high"], df["target_low"])
        df["upside"] = df["target_mean"] / df["price"] - 1
        df = score_frame(df)
        df["date"] = t
        for h in (21, 63):
            df[f"fwd_{h}"] = fwd[h].loc[t].reindex(df.index)
            df[f"ex_{h}"] = df[f"fwd_{h}"] - float(spy_fwd[h].loc[t])
            df[f"rel_{h}"] = df[f"fwd_{h}"] - df[f"fwd_{h}"].mean()  # vs equal-weight S&P 500
        df.index.name = "ticker"
        frames.append(df.reset_index())
        if n % 12 == 0:
            _log(f"  scored {n}/{len(dates)} dates")
    return pd.concat(frames, ignore_index=True), dates, adjx, spy


# ------------------------------------------------------------------------------ evaluation
def _combine(S: pd.DataFrame, w: dict[str, float]) -> pd.Series:
    M = S[[f"s_{c}" for c in w]].to_numpy(float)
    W = np.array([w[c] for c in w])
    present = ~np.isnan(M)
    num = np.nansum(M * W, axis=1)
    den = (present * W).sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        return pd.Series(np.where(den > 0, num / den, np.nan), index=S.index)


def _ic(S: pd.DataFrame, score: pd.Series, col: str) -> pd.Series:
    tmp = pd.DataFrame({"date": S["date"], "x": score, "y": S[col]}).dropna()
    return tmp.groupby("date").apply(lambda g: spearmanr(g["x"], g["y"])[0] if len(g) > 20 else np.nan, include_groups=False)


def _top_stats(S: pd.DataFrame, score: pd.Series, n: int, gate: pd.Series | None = None) -> dict:
    tmp = S.assign(_s=score)
    if gate is not None:
        tmp = tmp[gate.reindex(tmp.index).fillna(False)]
    top = tmp.dropna(subset=["_s", "fwd_63"]).sort_values(["date", "_s"], ascending=[True, False]).groupby("date").head(n)
    allr = S.dropna(subset=["fwd_63"])
    by_date = top.groupby("date")
    return {
        "avg 3m return": by_date["fwd_63"].mean().mean(),
        "universe 3m": allr.groupby("date")["fwd_63"].mean().mean(),
        "vs universe": by_date["rel_63"].mean().mean(),
        "vs SPY": by_date["ex_63"].mean().mean(),
        "% beat universe": (top["rel_63"] > 0).mean(),
        "% up >10%": (top["fwd_63"] > 0.10).mean(),
        "base % up >10%": (allr["fwd_63"] > 0.10).mean(),
        "avg picks/date": by_date.size().mean(),
    }


def _variants() -> dict[str, dict[str, float]]:
    eq = {c: 1.0 for c in COMPS}
    return {
        "Current weights": dict(WEIGHTS),
        "Equal weights": eq,
        "Momentum only": {"momentum": 1.0},
        "Analyst upside only": {"upside": 1.0},
        "Value only": {"value": 1.0},
        "Growth only": {"growth": 1.0},
        "Consensus only": {"consensus": 1.0},
        "No analyst upside": {c: WEIGHTS[c] for c in COMPS if c != "upside"},
        "Upside + momentum": {"upside": 0.5, "momentum": 0.5},
    }


def _fmt(df: pd.DataFrame, pct_cols=()) -> str:
    d = df.copy()
    for c in d.columns:
        d[c] = d[c].map(lambda v: f"{v * 100:6.2f}%" if c in pct_cols and pd.notna(v) else (f"{v:7.3f}" if isinstance(v, float) else v))
    return d.to_string()


def _earnings_study(S, dates, adjx, spy, hist) -> pd.DataFrame:
    """Score at the last month-end before each earnings report vs the stock's reaction to that report."""
    idx = adjx.index
    dts = pd.DatetimeIndex(dates)
    sc = S.set_index(["date", "ticker"])["buy_score"]
    rows = []
    for tk, h in hist.items():
        ed = h.get("ed")
        if ed is None or ed.empty or tk not in adjx:
            continue
        rep = ed[ed["Reported EPS"].notna()].copy()
        rep.index = pd.to_datetime(rep.index, utc=True).tz_localize(None).normalize()
        for e, r in rep.iterrows():
            prev = dts[dts < e - pd.Timedelta(days=1)]
            if not len(prev) or (e - prev[-1]).days > 35:
                continue
            t0 = prev[-1]
            i = idx.searchsorted(e)  # first trading day >= e
            if i < 1 or i + 41 >= len(idx):
                continue
            pre, post, drift_end = idx[i - 1], idx[min(i + 1, len(idx) - 1)], idx[i + 40]
            p = adjx[tk]
            if (t0, tk) not in sc.index or np.isnan(p.loc[pre]) or np.isnan(p.loc[post]):
                continue
            react = p.loc[post] / p.loc[pre] - 1 - (spy.loc[post] / spy.loc[pre] - 1)
            drift = p.loc[drift_end] / p.loc[post] - 1 - (spy.loc[drift_end] / spy.loc[post] - 1)
            rows.append({"date": t0, "ticker": tk, "score": sc[(t0, tk)],
                         "react": react, "drift40": drift, "beat": float(r["Surprise(%)"] > 0) if pd.notna(r["Surprise(%)"]) else np.nan})
    ev = pd.DataFrame(rows).dropna(subset=["score", "react"])
    ev["quintile"] = ev.groupby("date")["score"].transform(lambda s: pd.qcut(s.rank(method="first"), 5, labels=False, duplicates="drop") + 1 if len(s) >= 25 else np.nan)
    return ev.dropna(subset=["quintile"])


def run(years: float = 5.0, refresh: bool = False) -> None:
    univ, close, adj, hist = _load(years, refresh)
    S, dates, adjx, spy = _build_snapshots(univ, close, adj, hist, years)
    S = S.reset_index(drop=True)
    out: list[str] = []

    def emit(s: str = ""):
        print(s)
        out.append(s)

    emit(f"# Back-test  ({dates[0].date()} -> {dates[-1].date()}, {len(dates)} monthly snapshots, ~{S.groupby('date').size().mean():.0f} stocks each)")
    cov = S[["earn_yield", "eps_growth", "adj_upside", "rec_score", "net_upgrades", "beat_rate", "ret_12_1"]].notna().mean()
    emit("\nPoint-in-time input coverage: " + ", ".join(f"{k} {v:.0%}" for k, v in cov.items()))

    # 1) Does the score rank-correlate with what happened next?
    emit("\n## 1. Rank correlation (IC) of score vs forward return — >0 means high score => higher return")
    rows = {}
    for name, series in [("BUY SCORE", S["buy_score"])] + [(c, S[f"s_{c}"]) for c in COMPS]:
        i63, i21 = _ic(S, series, "fwd_63"), _ic(S, series, "fwd_21")
        rows[name] = {"IC 1m": i21.mean(), "IC 3m": i63.mean(), "IC 3m t-stat": i63.mean() / (i63.std() / np.sqrt(i63.count())) if i63.count() > 2 else np.nan,
                      "% months IC>0": (i63 > 0).mean()}
    emit(_fmt(pd.DataFrame(rows).T, pct_cols=("% months IC>0",)))
    emit("(|t-stat| > 2 is conventionally significant; monthly samples overlap, so treat it as optimistic.)")

    # 2) Quintiles
    emit("\n## 2. Average 3-month return by Buy Score quintile (5 = highest score)")
    q = S.dropna(subset=["buy_score", "fwd_63"]).copy()
    q["quintile"] = q.groupby("date")["buy_score"].transform(lambda s: pd.qcut(s.rank(method="first"), 5, labels=False) + 1)
    qt = q.groupby("quintile").agg(avg_3m=("fwd_63", "mean"), median_3m=("fwd_63", "median"), vs_universe=("rel_63", "mean"),
                                   pct_up_10=("fwd_63", lambda s: (s > 0.10).mean()), pct_beat_universe=("rel_63", lambda s: (s > 0).mean()))
    emit(_fmt(qt, pct_cols=tuple(qt.columns)))
    spread = qt.loc[5, "avg_3m"] - qt.loc[1, "avg_3m"]
    emit(f"Top-minus-bottom quintile spread: {spread * 100:.2f}% per 3 months")

    # 3) Top-100 portfolio and weight variants
    emit(f"\n## 3. Buy the top {TOP_N} each month (hold 3 months): which weighting works best?")
    res = {}
    for name, w in _variants().items():
        sc = _combine(S, w)
        res[name] = {**_top_stats(S, sc, TOP_N), "IC 3m": _ic(S, sc, "fwd_63").mean()}
    gate_score = S["buy_score"]
    res["Current + momentum gate (>=40)"] = {**_top_stats(S, gate_score, TOP_N, gate=S["s_momentum"] >= 40), "IC 3m": _ic(S, gate_score, "fwd_63").mean()}
    res = pd.DataFrame(res).T.sort_values("vs universe", ascending=False)
    emit(_fmt(res, pct_cols=("avg 3m return", "universe 3m", "vs universe", "vs SPY", "% beat universe", "% up >10%", "base % up >10%")))

    # 4) Stability by year
    emit("\n## 4. Stability: BUY SCORE results by calendar year")
    S["year"] = S["date"].dt.year
    yr = S.dropna(subset=["buy_score", "fwd_63"]).groupby("year").apply(
        lambda g: pd.Series({"IC 3m": np.nanmean([spearmanr(x["buy_score"], x["fwd_63"])[0] for _, x in g.groupby("date") if len(x) > 20]),
                             "top100 vs universe": g.sort_values("buy_score", ascending=False).groupby("date").head(TOP_N)["rel_63"].mean(),
                             "months": float(g["date"].nunique())}), include_groups=False)
    yr["months"] = yr["months"].astype(int)
    emit(_fmt(yr, pct_cols=("top100 vs universe",)))

    # 5) Earnings reactions
    emit("\n## 5. Earnings study: score at last month-end before the report vs the stock's reaction")
    ev = _earnings_study(S, dates, adjx, spy, hist)
    if len(ev):
        g = ev.groupby("quintile").agg(events=("react", "size"), avg_reaction_vs_SPY=("react", "mean"), pct_positive=("react", lambda s: (s > 0).mean()),
                                       beat_rate=("beat", "mean"), avg_40d_drift_vs_SPY=("drift40", "mean"))
        emit(_fmt(g, pct_cols=("avg_reaction_vs_SPY", "pct_positive", "beat_rate", "avg_40d_drift_vs_SPY")))
        emit("(reaction = close before report -> close after report, minus SPY; drift = next 40 trading days)")
    else:
        emit("Not enough earnings events matched.")

    emit("\n## Honest limits")
    emit("- Survivorship bias: today's S&P 500 members only; past losers that were dropped are missing, which flatters every strategy.")
    emit("- Free data has no history of Zacks Rank, TipRanks, Finviz, revenue growth, PEG or FCF, so the back-test scores a subset of the live model.")
    emit("- Weights picked from these tables are in-sample. Prefer variants that win in most years (section 4), not just on average.")
    emit("- Past relationships can disappear. This measures edge in the historical sample, not a guarantee.")

    (OUTPUT_DIR / "backtest.md").write_text("\n".join(out), encoding="utf-8")
    S.to_pickle(OUTPUT_DIR / "backtest_scores.pkl")
    print(f"\nSaved: {OUTPUT_DIR / 'backtest.md'}")
