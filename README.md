# S&P 500 Opportunity Screener

Ranks every S&P 500 stock, shows the **Magnificent 7 first**, then the **100 best other ideas**
ordered by analyst upside %. Each stock gets a 0-100 **Buy Score**.

```bash
source .venv/bin/activate
python -m stockscreener run --open     # ~3 min first time, seconds when cached (6h)
python -m stockscreener backtest       # replay the model on 5 years of history
```

Outputs: `output/report.html` (sortable, with a "where do I put $10-40k" splitter),
`output/ranked.csv`, `output/backtest.md`.

## What it tracks
Price, P/E, forward P/E, EPS, average analyst target (+ high/low, analyst count), upside %,
revenue/EPS growth, 12-1m / 6m / 3m momentum, analyst rating, Zacks Rank, Finviz consensus,
estimate revisions, upgrades/downgrades, earnings-surprise history, next earnings date.

## Buy Score (weights in `stockscreener/config.py`)
upside 25% · momentum 25% · value 20% · growth 15% · consensus 15%.
Analyst upside is shrunk when few analysts cover the stock or they disagree, and capped at +60%.

## Optional: TipRanks Smart Score via Perplexity
TipRanks renders its score client-side, so it can't be scraped directly.
`export PERPLEXITY_API_KEY=...` before `run` and it will be fetched (and used in the Consensus score).

## Data sources
Yahoo Finance (`yfinance`), Zacks and Finviz pages (scraped politely, throttled; may break if the sites change),
S&P 500 list from Wikipedia.

Research tool only, not financial advice.
