"""Turns raw features into 0-100 component scores and one overall Buy Score.

The same function scores live data and historical snapshots in the back-test.
Missing inputs never crash or zero a stock: weights are re-normalised over what exists.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import ABS_SCALES, COMPONENTS, LOWER_IS_BETTER, MIN_ANALYSTS, SIGNALS, WEIGHTS

MIN_COVERAGE = 0.20  # a component needs at least 20% of its input weight present to count


def _pct_rank(s: pd.Series, ascending: bool) -> pd.Series:
    return s.rank(pct=True, ascending=ascending) * 100.0


def _col_score(df: pd.DataFrame, col: str, mode: str) -> pd.Series:
    s = pd.to_numeric(df[col], errors="coerce").replace([np.inf, -np.inf], np.nan)
    if mode == "abs":
        lo, hi = ABS_SCALES[col]
        return ((s - lo) / (hi - lo)).clip(0, 1) * 100.0
    asc = col not in LOWER_IS_BETTER  # ascending rank => high raw value gets high score
    if col == "peg":
        s = s.where(s > 0)  # negative PEG is meaningless, not "cheap"
    universe = _pct_rank(s, asc)
    if mode == "sector" and "sector" in df:
        within = s.groupby(df["sector"]).transform(lambda x: _pct_rank(x, asc) if x.notna().sum() >= 8 else x * np.nan)
        return universe.where(within.isna(), 0.5 * universe + 0.5 * within)
    return universe


def _weighted(parts: list[pd.Series], weights: list[float], total_weight: float) -> pd.Series:
    M = pd.concat(parts, axis=1).to_numpy(dtype=float)
    W = np.asarray(weights, dtype=float)
    present = ~np.isnan(M)
    num = np.nansum(M * W, axis=1)
    den = (present * W).sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        out = np.where(den / total_weight >= MIN_COVERAGE, num / den, np.nan)
    return pd.Series(out, index=parts[0].index)


def score_frame(df: pd.DataFrame, weights: dict[str, float] | None = None) -> pd.DataFrame:
    """Add s_<component> columns, buy_score, and signal to a feature DataFrame (one row per stock)."""
    weights = weights or WEIGHTS
    out = df.copy()

    for comp, spec in COMPONENTS.items():
        parts, ws = [], []
        for col, w, mode in spec:
            if col in df.columns and pd.to_numeric(df[col], errors="coerce").notna().sum() >= 5:
                parts.append(_col_score(df, col, mode))
                ws.append(w)
        out[f"s_{comp}"] = _weighted(parts, ws, sum(w for _, w, _ in spec)) if parts else np.nan

    comps = [c for c in weights if out[f"s_{c}"].notna().any()]
    out["buy_score"] = _weighted([out[f"s_{c}"] for c in comps], [weights[c] for c in comps], sum(weights[c] for c in comps))

    # Guard rails: don't reward a spike or a thinly-covered target.
    if "rsi14" in out:
        out["buy_score"] -= np.where(out["rsi14"] > 80, 3.0, 0.0)
    if "n_analysts" in out:
        out["buy_score"] *= np.where(out["n_analysts"].fillna(0) < MIN_ANALYSTS, 0.9, 1.0)
    out["buy_score"] = out["buy_score"].clip(0, 100)

    out["signal"] = out["buy_score"].map(_signal)
    return out


def _signal(score: float) -> str:
    if pd.isna(score):
        return "N/A"
    for threshold, label in SIGNALS:
        if score >= threshold:
            return label
    return "AVOID"
