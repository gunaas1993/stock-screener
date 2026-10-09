# Back-test  (2021-10-29 -> 2026-06-30, 57 monthly snapshots, ~491 stocks each)

Point-in-time input coverage: earn_yield 85%, eps_growth 84%, adj_upside 80%, rec_score 80%, net_upgrades 82%, beat_rate 86%, ret_12_1 100%

## 1. Rank correlation (IC) of score vs forward return — >0 means high score => higher return
             IC 1m    IC 3m IC 3m t-stat % months IC>0
BUY SCORE    0.032    0.041        3.213        63.16%
value        0.035    0.040        2.051        63.16%
growth       0.023    0.028        1.694        66.67%
quality      0.021    0.022        2.034        63.16%
upside       0.010    0.029        1.258        54.39%
momentum     0.007    0.006        0.270        52.63%
consensus    0.008    0.014        0.952        57.89%
(|t-stat| > 2 is conventionally significant; monthly samples overlap, so treat it as optimistic.)

## 2. Average 3-month return by Buy Score quintile (5 = highest score)
           avg_3m median_3m vs_universe pct_up_10 pct_beat_universe
quintile                                                           
1           3.22%     2.02%      -0.38%    28.65%            45.50%
2           2.26%     1.42%      -1.33%    26.06%            43.25%
3           3.22%     2.23%      -0.38%    29.09%            45.82%
4           3.77%     2.47%       0.17%    30.65%            46.55%
5           5.50%     3.06%       1.91%    33.84%            49.12%
Top-minus-bottom quintile spread: 2.28% per 3 months

## 3. Buy the top 100 each month (hold 3 months): which weighting works best?
                               avg 3m return universe 3m vs universe   vs SPY % beat universe % up >10% base % up >10% avg picks/date    IC 3m
Growth only                            6.09%       3.59%       2.50%    2.81%          48.95%    35.23%         29.66%        100.000    0.028
No analyst upside                      5.86%       3.59%       2.27%    2.58%          49.18%    33.49%         29.66%        100.000    0.037
Equal weights                          5.75%       3.59%       2.16%    2.47%          49.54%    33.89%         29.66%        100.000    0.041
Current weights                        5.59%       3.59%       2.01%    2.32%          49.54%    33.79%         29.66%        100.000    0.045
Current + momentum gate (>=40)         5.58%       3.59%       1.99%    2.30%          49.35%    33.75%         29.66%        100.000    0.041
Upside + momentum                      5.11%       3.59%       1.52%    1.83%          48.63%    33.00%         29.66%        100.000    0.030
Momentum only                          4.79%       3.59%       1.20%    1.51%          45.65%    30.84%         29.66%        100.000    0.006
Consensus only                         4.56%       3.59%       0.98%    1.28%          47.28%    31.51%         29.66%        100.000    0.014
Analyst upside only                    4.15%       3.59%       0.56%    0.87%          47.42%    32.81%         29.66%        100.000    0.029
Value only                             4.14%       3.59%       0.55%    0.86%          49.16%    33.05%         29.66%        100.000    0.040

## 4. Stability: BUY SCORE results by calendar year
        IC 3m top100 vs universe  months
year                                    
2021   -0.051              1.31%       3
2022   -0.011              0.48%      12
2023    0.081              2.95%      12
2024    0.020              0.55%      12
2025    0.077              3.13%      12
2026    0.080              2.98%       6

## 5. Earnings study: score at last month-end before the report vs the stock's reaction
          events avg_reaction_vs_SPY pct_positive beat_rate avg_40d_drift_vs_SPY
quintile                                                                        
1.0         1614               0.22%       49.44%    70.18%               -0.78%
2.0         1584               0.12%       50.88%    78.37%               -0.68%
3.0         1579               0.29%       50.35%    81.81%               -0.90%
4.0         1584               0.21%       52.27%    83.33%               -0.25%
5.0         1601               0.29%       51.47%    84.13%                0.72%
(reaction = close before report -> close after report, minus SPY; drift = next 40 trading days)

## Honest limits
- Survivorship bias: today's S&P 500 members only; past losers that were dropped are missing, which flatters every strategy.
- Free data has no history of Zacks Rank, TipRanks, Finviz, revenue growth, PEG or FCF, so the back-test scores a subset of the live model.
- Weights picked from these tables are in-sample. Prefer variants that win in most years (section 4), not just on average.
- Past relationships can disappear. This measures edge in the historical sample, not a guarantee.