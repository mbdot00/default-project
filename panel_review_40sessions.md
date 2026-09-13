# Independent Free-Model Panel Review — 40 trade_auto Sessions

Evidence digest supplied to models:

```
Strategy: on XM demo, JP225Cash (Nikkei 225 CFD), 0.1 lot. Script runs an infinite loop of sessions. Each session picks ONE direction from M5 EMA7-vs-EMA21 (bull->BUY, bear->SELL), then every 5s opens MORE 0.1 lot buys while the M1 candle is green (sell while red), STACKING positions. No per-trade stop/take-profit. Each session ends ONLY when total equity since session start falls -$1 (LOSS) or rises +$5 (WIN); then all positions are bulk-closed and it loops to the next session. Per-point P/L is tiny (~$0.005/pt at 0.1 lot) so equity moves very slowly.

REAL TEST RESULTS (40 completed sessions, ~11.5 hours, today):
- Total: 3 WINS, 33 LOSSES, 4/noted time-outs.
- By direction: BUY sessions = 24 (2 win / 18 loss); SELL sessions = 18 (1 win / 15 loss).
- Raw band P/L before spread/costs = +3*$5 - 33*$1 = -$18. After spreads (0.1 lot x17-40 opens/session) it is worse.
- Average session duration for WIN/LOSS = ~15.5 min; LONG sessions dominate (many 20-77 min, one 77 min).
- Loss ratio 92% (33/36 decisive sessions lost). No sign of separation between directions; most sessions bleed to -$1 rarely reaching +$5.
```

## laguna-s-2.1-free

### edge

**Blunt verdict: This is a coin-flip with negative expectancy, not an edge.**

Here's the quantitative breakdown:

1.  **Win Rate & Expectancy:**
    *   Win Rate = 3 / 36 = **8.3%** (excluding timeouts).
    *   Risk/Reward per session = $1 / $5 = 0.2.
    *   Expectancy (pre-cost) = (0.083 * $5) - (0.917 * $1) = $0.415 - $0.917 = **-$0.502 per session**.
    *   This means, on average, you lose 50 cents for every session attempted, before any costs.

2.  **Impact of Costs:**
    *   You stated spreads make it "worse." With 17-40 opens per session at 0.1 lots, transaction costs are significant relative to the $0.005/pt P&L.
    *   The pre-cost loss of -$18 over 36 sessions is already substantial. Adding spread drag pushes the total loss even deeper into negative territory, likely well below -$20 or -$30.

3.  **Lack of Directional Edge:**
    *   BUY sessions: 2/20 = 10% win rate.
    *   SELL sessions: 1/18 = 5.6% win rate.
    *   These rates are statistically indistinguishable from random chance (e.g., a coin flip would yield ~50% in a fair game; here, both are far below any threshold suggesting skill). The slight difference is noise.

4.  **Flawed Logic ("Stacking"):**
    *   Doubling down (or increasing position size) on a losing trade to recover losses is a classic martingale variant. It does not improve the underlying probability of the next trade winning; it only increases the potential loss if the trend doesn't reverse quickly.
    *   Without a stop-loss, a single adverse move can wipe out multiple winning stacks, which is exactly what the data shows (long sessions bleeding to -$1).

5.  **Session Duration & Drawdown:**
    *   Long sessions (up to 77 minutes) indicate the strategy often fights a losing battle, tying up capital and increasing exposure to unpredictable market swings. This amplifies risk without improving reward.

**Conclusion:**

The numbers are unambiguous. A win rate of 8.3% against a 1:5 risk/reward ratio results in a deeply negative expectancy. The addition of real-world trading costs (spreads, slippage) makes it worse. The performance across BUY and SELL directions is statistically equivalent, proving no directional bias or predictive power from the M5 EMA crossover. This is a losing proposition, not a statistical edge. The core mechanics (martingale-style stacking, no stops, weak trend signal) are fundamentally flawed for generating consistent profits.

### flaw

The single most damaging design flaw is **the absence of any per-trade stop-loss combined with position stacking in the direction of a weak, noisy M1 candle signal**.

Here's the quantitative erosion:

- **No stop-loss per trade**: Each 0.1-lot position is opened every 5 seconds based on a single M1 candle color. There is no mechanism to cut a losing position quickly. With ~17 to 40 positions opened per session, a single adverse move can bleed equity across dozens of open lots simultaneously.
  
- **Stacking amplifies noise**: The M1 candle color is an extremely noisy signal. By stacking 0.1 lots every 5 seconds while the candle remains green/red, the strategy loads up on a signal that has no predictive edge. This turns small adverse moves into large cumulative losses because all stacked positions move together against the trader.

- **Session-level stop only ($1 loss)**: The only risk control is a -$1 session-level stop, which is equivalent to ~200 points against at 0.1 lot (~$0.005/pt). But since positions are stacked, a 200-point adverse move across 20+ lots can result in losses far exceeding $1 before the session closes — except the session *does* close at -$1, meaning the trader is effectively paying the full spread and slippage cost of closing 20+ positions just to realize a $1 loss.

- **Quantifying the damage**:
  - 33 losing sessions × $1 = $33 in nominal losses.
  - But each losing session likely involved 17–40 position opens/closes, each incurring spread cost. At ~$0.5–$1 spread per 0.1 lot round-trip, that’s ~$8.50–$40 in spread cost per losing session.
  - Total spread cost alone: 33 sessions × ~$15 avg = ~$495 in hidden costs.
  - Net result: Even if the raw edge were zero, the strategy loses ~$500+ over 40 sessions purely to transaction costs and uncontrolled exposure.

**Bottom line**: The lack of per-trade stops turns a marginally positive or neutral signal into a guaranteed loss generator due to compounding adverse exposure and massive transaction costs from forced bulk liquidation at arbitrary session boundaries.

### fix

## Top 3 Highest-Leverage Changes

### 1. **Add Directional Filter - Kill 90% of Losing Sessions**
Current: 92% loss rate because it trades every direction blindly
Fix: Only trade when M5 EMA7-EMA21 slope > 0.3% AND M1 candle confirms direction
Quantified impact: Should reduce losing sessions from 33 to ~8-12, improving win rate from 7.5% to 25-35%

### 2. **Implement Time-Based Session Exit - Cut Long Bleeders**
Current: Sessions run 20-77 minutes bleeding to -$1
Fix: Force-close all positions after 8-10 minutes regardless of P/L
Quantified impact: Eliminates 60-70% of current long sessions, reduces average loss per session from $1 to ~$0.40, cuts total session time by 60%

### 3. **Reduce Position Size to 0.02-0.03 Lot - Survive Longer**
Current: 0.1 lot = $0.005/pt moves too slowly, needs huge moves to hit +$5
Fix: Drop to 0.02-0.03 lot, increase win target to +$1.50 (same risk/reward ratio)
Quantified impact: 3-5x more trades before margin issues, faster equity movement, better risk distribution

## Reality Check
This strategy is fundamentally flawed - it's a momentum-following system without proper momentum filters. The core concept of stacking positions in the trend direction has merit, but execution is backwards.

**Best Alternative**: Scrap the infinite loop. Use the same EMA setup but with:
- Fixed 1:2 risk/reward (risk $1 to make $2)
- Hard stop-loss at 20-30 pips
- Take-profit at 40-60 pips
- Maximum 2 concurrent positions
- Daily session cap of 3-4 trades

This would likely produce 40-50% win rate with positive expectancy, vs current 7.5% disaster.

## ling-3.0-flash-fin-free

### edge

None

### flaw

None

### fix

None

## nemotron-3-ultra-free

### edge

The user wants a blunt, quantitative critique of a specific trading strategy based on provided test results.

**Strategy Summary:**
- Instrument: JP225Cash (Nikkei 225 CFD), 0.1 lot.
- Timeframe logic: M5 EMA7 vs EMA21 determines session direction (Bull -> Buy, Bear -> Sell).
- Execution: Every 5s, stack 0.1 lot positions if M1 candle color matches direction (Green for Buy, Red for Sell).
- Exit: Session ends when cumulative session equity hits -$1 (Loss) or +$5 (Win). Bulk close all.
- No per-trade SL/TP.

**Results (40 sessions, ~11.5 hrs):**
- Wins: 3, Losses: 33, Timeouts: 4.
- Direction split: Buy (24 sessions: 2W/18L), Sell (18 sessions: 1W/15L).
- Raw P/L (ex costs): 3 * $5 - 33 * $1 = -$18.
- Avg session duration ~15.5 min.
- Loss rate: 92% (33/36 decisive).
- Per point value: ~$0.005/pt (0.1 lot).

**Analysis Required:** Is this a statistical edge or coin-flip losing to costs?

**Quantitative Assessment:**
1.  **Win Rate:** 3/36 = 8.3%. Required breakeven win rate for 5:1 R:R (Risk $1 to make $5) is 1/(1+5) = 16.7%. Actual win rate (8.3%) is half the breakeven requirement.
2.  **Expectancy (Raw):** (0.083 * $5) - (0.917 * $1) = $0.415 - $0.917 = -$0.502 per session.
3.  **Costs:** "17-40 opens/session". Avg ~28 trades/session. Spread cost per 0.1 lot on JP225Cash. Typical spread ~5-10 pts (0.5 - 1.0 index points? No, Nikkei CFD spreads are usually quoted in index points. 0.1 lot = $0.10/pt? User says $0.005/pt. Wait. Standard Nikkei 225 CFD: 1 lot = 100 JPY/pt? Or 1 JPY/pt?
    - User says: "Per-point P/L is tiny (~$0.005/pt at 0.1 lot)".
    - If 0.1 lot = $0.005/pt, then 1 lot = $0.05/pt. This implies contract size is very small (mini/micro). Or currency conversion JPY->USD.
    - Spread: XM JP225Cash spread typically ~8-15 points (index points).
    - Cost per open: 10 pts * $0.005 = $0.05 per 0.1 lot open.
    - Avg 28 opens/session * $0.05 = $1.40 spread cost per session.
    - Total sessions 36 decisive. Total spread cost ~ 36 * $1.40 = $50.
    - Net P/L = -$18 (raw) - $50 (spread) = -$68.
4.  **Stacking Logic Flaw:** Adding to winners (pyramiding) on M1 candle color while M5 trend holds.
    - M5 trend (EMA 7/21) is slow. M1 noise is high.
    - Stacking 0.1 lot every 5s on M1 color = massive position size accumulation if trend persists.
    - If M5 trend is correct, position grows large -> hits +$5 fast.
    - If M5 trend is wrong (chop/whipsaw), position grows large against you -> hits -$1 fast.
    - Asymmetric payoff ($5 vs $1) requires high win rate (16.7%). Strategy achieves 8.3%.
    - The "stacking" increases variance and position size exactly when the short-term (M1) momentum aligns, but M1 momentum reverts violently in ranging markets (which EMA 7/21 on M5 often signals late).
5.  **Session Duration:** 15 min avg. 5:1 R

### flaw

The user wants me to identify the SINGLE most damaging design flaw from the trade evidence provided. Let me analyze the strategy and results carefully.

Strategy summary:
- JP225Cash CFD, 0.1 lot
- Session picks ONE direction based on M5 EMA7 vs EMA21
- Every 5 seconds, adds 0.1 lot positions while M1 candle is green (buy) or red (sell) - STACKING positions
- No per-trade stop/take-profit
- Session ends when total equity since session start hits -$1 (LOSS) or +$5 (WIN)
- Then bulk closes all positions and loops

Results:
- 40 sessions, ~11.5 hours
- 3 WINS, 33 LOSSES, 4 timeouts
- BUY: 24 sessions (2W/18L), SELL: 18 sessions (1W/15L)
- Raw P/L: +$15 - $33 = -$18 before costs
- After spreads (17-40 opens/session * 0.1 lot), worse
- Avg session duration ~15.5 min for decisive sessions
- Loss ratio 92% (33/36)
- Per-point P/L tiny (~$0.005/pt at 0.1 lot)

Key observations:
1. Stacking positions every 5 seconds while M1 candle is green/red - this means adding to winners AND losers within the same direction
2. No per-trade stops - positions accumulate
3. Session stop at -$1 or +$5 total equity
4. Per-point P/L is $0.005/pt at 0.1 lot
5. Spread cost: 17-40 opens per session at 0.1 lot each

Let me think about the math:
- 0.1 lot, $0.005/pt means 1 point = $0.005
- To make +$5, need 1000 points move in favor (5 / 0.005 = 1000)
- To lose -$1, need 200 points move against (1 / 0.005 = 200)
- But with stacking, the position size grows over time

Wait, the stacking is critical. Every 5 seconds, it adds 0.1 lot if M1 candle is green (for buys) or red (for sells). So position size grows linearly with time during the session.

If a session lasts 15.5 minutes average = 930 seconds. Every 5 seconds = 186 potential additions. But only while M1 candle is favorable. M1 candle changes every minute. So roughly 50% of the time? So ~93 additions average? But the data says 17-40 opens/session. So maybe only ~30 additions average.

With 30 additions of 0.1 lot = 3 lots total position at end.
Average position size over session ~1.5 lots.
Per point P/L at 1.5 lots = $0.075/pt.

But the session stops at -$1 or +$5 TOTAL equity change.

The asymmetry: stop loss at -$1, take profit at +$5. That's 5:1 reward:risk.
But win rate is 3/36 = 8.3%.
Expected value = 0.083 * 5 - 0.917 * 1 = 0.415 - 0.917 = -0.502 per session. Negative expectancy.

But the question is: what is the SINGLE most damaging DESIGN FLAW?

Candidates:
1. Asymmetric session targets (-$1 vs +$5) with low win rate
2. Stacking positions every 5 seconds without per-trade risk control
3. No per-trade stops, only session-level stop
4. M1 candle color as entry trigger for stacking (noise)
5. Spread costs from excessive trading (17-40 opens/session)
6. Tiny per-point value requiring huge moves
7. EMA7 vs EMA21 on M5 for direction (lagging, whipsaw)

Let me quantify the stacking flaw:
- Every 5 seconds adds 0.1 lot while M1 candle favorable
- This creates massive position size risk
- But the session stop is only -$1 total equity
- With growing position size, a small adverse move wipes out the -$1 quickly
-

### fix

**VERDICT: FUNDAMENTALLY BROKEN. DO NOT FIX — REPLACE.**

The math is fatal: you need an **83%+ win rate** just to break even on a +$5/-$1 payoff (before costs). You have **8%**. No parameter tweak bridges a 75-percentage-point gap. The stacking mechanism guarantees you maximize position size at local tops/bottoms, then sit through the pullback with no stop. This is a guaranteed ruin path.

---

### TOP 3 HIGHEST-LEVERAGE CHANGES (if you insist on polishing a turd)

#### 1. INVERT THE PAYOFF ASYMMETRY — TARGET $1, STOP $5 (1:5 R:R → 5:1 R:R)
*   **Why:** Your current +5/-1 requires 83% win rate. Flipping to -$5/+$1 requires only **17% win rate** to break

