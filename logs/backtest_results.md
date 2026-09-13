# Backtest Results: PSAR Flip Strategy (M1)

**Script:** `psar_backtest.py`  
**Date:** 2026-09-10

## Parameters

| Parameter | Value |
|---|---|
| Symbol | JP225Cash |
| Timeframe | M1 |
| PSAR step | 0.01 |
| PSAR max | 0.05 |
| Lot size | 0.1 |
| Period | 2026-08-31 to 2026-09-10 (9 days) |
| Data points | 10,000 M1 bars |

## Summary

| Metric | Value |
|---|---|
| Total trades | 432 |
| BUY trades | 216 |
| SELL trades | 216 |
| Win rate | 39.4% |
| Total P/L | **+$176.80** |
| Avg P/L per trade | +$0.41 |
| Max win | +$93.70 |
| Max loss | -$24.10 |
| Max drawdown | $265.90 |

## Daily P/L

| Date | P/L |
|---|---|
| 2026-08-31 | -$10.50 |
| 2026-09-01 | +$174.60 |
| 2026-09-02 | -$71.70 |
| 2026-09-03 | -$131.90 |
| 2026-09-04 | +$96.40 |
| 2026-09-07 | +$62.30 |
| 2026-09-08 | +$26.40 |
| 2026-09-09 | +$6.40 |
| 2026-09-10 | +$24.80 |

## Per-Direction

| Direction | Trades | P/L | Win Rate |
|---|---|---|---|
| BUY | 216 | +$46.10 | 38.9% |
| SELL | 216 | +$130.70 | 39.8% |

## Analysis

- Strategy is profitable over the test period
- Low win rate (39.4%) but winners are larger than losers
- SELL trades significantly more profitable than BUYs (+$130.70 vs +$46.10)
- Best day Sep 1 (+$174.60), worst day Sep 3 (-$131.90)
- Max drawdown $265.90 — significant relative to profits

## Important Caveats

1. **Spread not included** — JP225Cash spread ~40 pts = $0.04/trade. 432 trades ≈ $17 cost
2. **Commission not included** — XM may charge commission
3. **Swap not included** — overnight rollover costs
4. **Slippage not included** — execution at open price is idealized
5. **Limited data** — only 9 days, ~10k bars
6. **Survivorship** — Sep 1 outlier skews results

## Verdict

Strategy shows **positive expectancy** on M1 but with:
- High trade frequency (~48 trades/day)
- Low win rate (needs strong trend capture)
- Significant drawdown risk

Live results may vary significantly from backtest due to spread, slippage, and the unknown "flip-flop" EA interfering.
