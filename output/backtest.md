# Back-test  (2021-10-29 -> 2026-06-30, 57 monthly snapshots, ~493 stocks each)

Point-in-time input coverage: earn_yield 85%, eps_growth 84%, adj_upside 79%, rec_score 79%, net_upgrades 81%, beat_rate 85%, ret_12_1 100%

## 1. Rank correlation (IC) of score vs forward return — >0 means high score => higher return
             IC 1m    IC 3m IC 3m t-stat % months IC>0
BUY SCORE    0.031    0.043        3.338        64.91%
value        0.035    0.039        2.046        61.40%
growth       0.024    0.031        1.846        66.67%
upside       0.010    0.029        1.276        56.14%
momentum     0.007    0.008        0.336        54.39%
consensus    0.008    0.015        1.019        59.65%
(|t-stat| > 2 is conventionally significant; monthly samples overlap, so treat it as optimistic.)

## 2. Average 3-month return by Buy Score quintile (5 = highest score)
           avg_3m median_3m vs_universe pct_up_10 pct_beat_universe
quintile                                                           
1           3.19%     1.88%      -0.40%    28.26%            44.78%
2           2.55%     1.62%      -1.03%    26.92%            43.96%
3           3.22%     2.27%      -0.37%    28.40%            45.67%
4           3.43%     2.25%      -0.14%    30.51%            46.14%
5           5.51%     3.21%       1.93%    34.22%            49.56%
Top-minus-bottom quintile spread: 2.33% per 3 months

## 3. Buy the top 100 each month (hold 3 months): which weighting works best?
                               avg 3m return universe 3m vs universe   vs SPY % beat universe % up >10% base % up >10% avg picks/date    IC 3m
Growth only                            6.11%       3.57%       2.54%    2.84%          49.11%    35.25%         29.66%        100.000    0.031
Equal weights                          5.76%       3.57%       2.19%    2.48%          50.00%    34.14%         29.66%        100.000    0.046
Current weights                        5.56%       3.57%       1.99%    2.28%          49.96%    34.02%         29.66%        100.000    0.047
No analyst upside                      5.52%       3.57%       1.95%    2.24%          48.82%    33.42%         29.66%        100.000    0.035
Current + momentum gate (>=40)         5.52%       3.57%       1.95%    2.24%          49.77%    33.93%         29.66%        100.000    0.043
Upside + momentum                      5.17%       3.57%       1.59%    1.89%          48.68%    33.07%         29.66%        100.000    0.032
Momentum only                          4.80%       3.57%       1.22%    1.52%          45.61%    30.82%         29.66%        100.000    0.008
Consensus only                         4.58%       3.57%       1.01%    1.30%          47.33%    31.58%         29.66%        100.000    0.015
Value only                             4.18%       3.57%       0.61%    0.90%          49.33%    33.25%         29.66%        100.000    0.039
Analyst upside only                    4.14%       3.57%       0.57%    0.86%          47.42%    32.77%         29.66%        100.000    0.029

## 4. Stability: BUY SCORE results by calendar year
        IC 3m top100 vs universe   months
year                                     
2021   -0.069              1.60%    3.000
2022   -0.002              0.86%   12.000
2023    0.102              2.84%   12.000
2024    0.014              0.78%   12.000
2025    0.066              2.35%   12.000
2026    0.082              3.41%    6.000

## 5. Earnings study: score at last month-end before the report vs the stock's reaction
          events avg_reaction_vs_SPY pct_positive beat_rate avg_40d_drift_vs_SPY
quintile                                                                        
1.0         1613               0.10%       48.67%    72.78%               -0.42%
2.0         1584               0.48%       52.08%    78.35%               -1.21%
3.0         1581               0.21%       50.22%    82.29%               -0.46%
4.0         1584               0.00%       50.82%    82.94%               -0.75%
5.0         1601               0.31%       52.47%    81.39%                0.89%
(reaction = close before report -> close after report, minus SPY; drift = next 40 trading days)

## Honest limits
- Survivorship bias: today's S&P 500 members only; past losers that were dropped are missing, which flatters every strategy.
- Free data has no history of Zacks Rank, TipRanks, Finviz, revenue growth, PEG or FCF, so the back-test scores a subset of the live model.
- Weights picked from these tables are in-sample. Prefer variants that win in most years (section 4), not just on average.
- Past relationships can disappear. This measures edge in the historical sample, not a guarantee.