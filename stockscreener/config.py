"""Central configuration: paths, universe rules, and scoring weights."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "data" / "cache"
OUTPUT_DIR = ROOT / "output"
for _d in (CACHE_DIR, OUTPUT_DIR):
    _d.mkdir(parents=True, exist_ok=True)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

# The "Magnificent 7" always get their own section at the top of the report.
MAG7 = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"]

# Second share classes of the same company: drop so one company is not counted twice.
DUPLICATE_SHARE_CLASSES = {"GOOG", "FOX", "NWS"}

TOP_N = 100            # size of the "valuable stocks" list shown after the Mag 7
STAGE2_POOL = 150      # how many stage-1 leaders get the (slower) deep enrichment
MIN_ANALYSTS = 5       # fewer analysts than this -> target price is not trustworthy
MAX_UPSIDE_CAP = 0.60  # analyst upside beyond +60% is treated as +60% (targets get stale)

# Component weights for the final Buy Score. They are re-normalised per stock if a
# component is entirely missing. Tune these using the back-test's per-factor IC table.
WEIGHTS = {
    "upside": 0.25,     # reliable analyst upside (coverage- and agreement-adjusted)
    "momentum": 0.25,   # price trend strength
    "value": 0.20,      # cheapness (earnings yield, PEG, FCF yield)
    "growth": 0.15,     # revenue / earnings growth
    "consensus": 0.15,  # analyst ratings, Zacks Rank, estimate revisions, surprises
}

# Which raw columns feed each component: (column, weight, mode)
#   rank   -> percentile rank across the whole S&P 500 (0-100)
#   sector -> 50% universe rank + 50% rank inside the GICS sector (fair to cheap-by-nature sectors)
#   abs    -> fixed linear scale from ABS_SCALES (used for fields that only exist for the shortlist,
#             so ranks are not distorted by who happened to be enriched)
COMPONENTS: dict[str, list[tuple[str, float, str]]] = {
    "value": [
        ("earn_yield", 0.45, "sector"),
        ("peg", 0.20, "sector"),
        ("fcf_yield", 0.35, "sector"),
    ],
    "growth": [
        ("rev_growth", 0.35, "rank"),
        ("eps_growth", 0.25, "rank"),
        ("fwd_eps_growth", 0.25, "rank"),
        ("ltg", 0.15, "rank"),
    ],
    "upside": [
        ("adj_upside", 1.0, "rank"),
    ],
    "momentum": [
        ("ret_12_1", 0.30, "rank"),
        ("ret_6m", 0.25, "rank"),
        ("ret_3m", 0.15, "rank"),
        ("rs_6m", 0.10, "rank"),
        ("near_high", 0.10, "rank"),
        ("trend", 0.10, "rank"),
    ],
    "consensus": [
        ("rec_score", 0.22, "rank"),
        ("zacks", 0.22, "abs"),
        ("eps_rev", 0.16, "abs"),
        ("net_upgrades", 0.08, "abs"),
        ("pt_rev", 0.10, "abs"),
        ("surprise_avg", 0.10, "abs"),
        ("beat_rate", 0.06, "abs"),
        ("smart_score", 0.06, "abs"),
    ],
}

# column -> (value that maps to 0, value that maps to 100); linear in between, clipped.
ABS_SCALES: dict[str, tuple[float, float]] = {
    "zacks": (5.0, 1.0),          # Zacks Rank 1 (Strong Buy) = 100, 5 (Strong Sell) = 0
    "eps_rev": (-0.08, 0.08),     # 90-day change in forward EPS estimate
    "net_upgrades": (-1.0, 1.0),  # (upgrades - downgrades) over last 90 days
    "pt_rev": (-0.20, 0.20),      # average analyst price-target change over last 90 days
    "surprise_avg": (-0.10, 0.15),  # mean EPS surprise over last 4 quarters
    "beat_rate": (0.25, 1.0),     # share of last 4 quarters that beat estimates
    "smart_score": (1.0, 10.0),   # TipRanks Smart Score
}

LOWER_IS_BETTER = {"peg"}

SIGNALS = [(72, "STRONG BUY"), (62, "BUY"), (52, "WATCH"), (0, "AVOID")]

PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY", "")
