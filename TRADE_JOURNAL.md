# JPCash225 Trade Journal & Strategy Research

> Primary goal: **make a lot of money, trade well, keep improving.**
> Every session, every finding, and every lesson gets recorded here so we get better.

---

## 1. Strategy Being Run

We trade the **JP225Cash** (Nikkei 225 cash CFD) demo account on XM, using two complementary scripts:

| Script | Direction | Signal (every 5s, trend-following) | Goal |
|--------|-----------|------------------------------------|------|
| `trade_buy_trend.py`  | BUY  | M5 **EMA7 > EMA21** (bullish) AND live M1 candle is **green** (rising) | Go long with the uptrend, ride momentum |
| `trade_sell_trend.py` | SELL | M5 **EMA7 < EMA21** (bearish) AND live M1 candle is **red** (falling) | Go short with the downtrend, ride momentum |

**Execution rules (coded and verified):**
- Polls and may act **every 5 seconds** on the **live forming** M1 candle (not a closed candle).
- Uses **live quote** (bid/ask) from `symbol_info` for the order price.
- Lot size: **0.1**.
- **Trend filter:** M5 EMA7 vs EMA21 alignment must agree with trade direction (bullish for buys, bearish for sells).
- **Session stop:** when equity drops to `start − $1` (**LOSS**) **or** rises to `start + $5` (**WIN**), bulk-close ALL positions and exit.
- One `log()` line per new candle records candle color (red/green), M5 EMA values, and whether a trade was **opened** or **held**.
- At session end writes a timestamped `.log` file: `trade_<name>_<YYYYMMDD_HHMMSS>_<HHhMMmSSs>_<WIN|LOSS|STOPPED>.log` into `logs\`.

**Why buy red candles / sell green candles (the edge we believe in):**
This is a **scalp/reversion** style setup. On the 1-minute timeframe, price constantly **overshoots** its mean (microstructure bid-ask bounce + transient order-flow pressure) and snaps back. Buying the micro-dip (red candle) / shorting the micro-rip (green candle) catches the snap-back. This has reportedly been **profitable before — including winning 5 times in a row, with increasing lot sizes.**

**⚠️ Important caution (from research & backtesting literature):**
Blindly buying every red / selling every green across the WHOLE day is not profitable. Naive dip-chasing with marketable orders **pays the spread both ways**, which typically exceeds the micro-reversion captured. This is the classic "buy-the-bounce" mirage. The edge exists only when:
1. We trade in **high-liquidity, low-spread windows** (Tokyo cash hours), and
2. We **filter the setup** — only take the reversion when it's statistically likely (trend reversal / exhaustion), NOT during strong trends or chop.

This is exactly why the next section (timing + trend-reversal detection) matters so much.

---

## 2. When to Execute a Session — Timing Research

### 2.1 JP225 / Nikkei 225 market hours
- **Tokyo Stock Exchange (cash equities):** 09:00–11:30 and 12:30–15:30 JST (with a lunch break).
- **Nikkei 225 futures/CFD** trade for ~24h/weekdays via the futures market.
- **Highest liquidity & tightest spreads = Tokyo cash session:**
  - 09:00–11:30 JST (00:00–02:30 GMT) → **best**
  - 12:30–15:30 JST (03:30–06:30 GMT) → afternoon + closing auction
  - European/US overlap → moderate-to-thin volume, wider spreads, event-driven gaps.

### 2.2 Best windows to run a buy-red / sell-green session
The strategy needs **clean directional movement + liquidity**, not chop:

1. **Tokyo Open (00:00–02:30 GMT ≈ the "8am opening" the user aims for):** The **first 30 minutes** carry the highest volume as overnight news is priced in. This is a prime window to catch a strong directional leg. **Best time to target.**
2. **The first hour after open** during significant data (BoJ announcements, Japanese economic data). Volatility is exceptional here.
3. **London morning / right at the Japan–Europe overlap** (maybe 06:00 GMT area) — secondary, still active.
4. **Avoid:** the Tokyo lunch break (02:30–03:30 GMT), the European afternoon, and weekend/react opens (gaps, wider spreads, choppy).

### 2.3 USD/JPY correlation (a key "candle reversal" filter)
The Nikkei is Japan-focused, so:
- **Yen weakens** (`USDJPY` up) → Japanese exporters' profits look better → **Nikkei tends to rise**.
- **Yen strengthens** (USDJPY down) → Nikkei tends to fall.
This gives us a **secondary confirmation** for reversal detection: if a Nikkei dip lines up with a weak yen, a buy-reversal is more likely to stick.

---

## 3. Finding the "Downtrend → Uptrend Reversal" (the ideal entry)

The core improvement we need: instead of buying any red candle, **buy the red candle at the moment the downtrend is exhausting and about to reverse up.** Research-backed signals for this (and where we can code them):

1. **Rejection wick / lower-shadow candle** — a red candle with a long lower wick means sellers were rejected; buyers stepped in.
2. **RSI(14) oversold + price below lower Bollinger Band(20,2)** — price is statistically stretched below its mean; reversion probability spikes **if the higher timeframe isn't in a strong downtrend**.
3. **Micro-pivot reclaim** — price makes a lower low (LH on M1/5M) then closes back above a prior pivot; this is the classic "turn."
4. **Volume + 20/50 EMA** on a 5-15 minute frame for the *trend filter*: only buy-reversals when the 15-min view is flat-to-up, only sell-reversals when flat-to-down.
5. **ADX(14) filter:** if ADX > 30 (strong trend), reversion scalps FAIL — stand down. If ADX < 20, range → reversion works well.

### Concrete code ideas to add later (stretch goals)
- Add a **trend filter** (e.g., EMA20 vs EMA50 on M5/M15) so the buy script only takes red-candle dips when the higher timeframe is not in a freefall, and the sell script only when not rocketing up.
- Add an **RSI(14)/Bollinger** oversold-overbought check.
- Add a **rejection wick** detector (low > open for the last red candle before buying).
- Add **USDJPY confirmation** (trade with the yen direction).
- Add an **ADX (trendiness) gate** to skip strong-trend days.
- Only run during the **Tokyo-open window** and auto-stop when spreads widen (lunch, EU afternoon).

These are the difference between a profitable filtered edge and the "dip-chase mirage" that loses the spread every time.

---

## 4. Live Logging Conventions (what each session record tells us)

Each `.log` file from a session contains, in order:
- Header: script name, symbol, lot, session start/end, duration, **outcome (WIN/LOSS/STOPPED)**.
- One line per minute: `M1 <time> open=... live=... bid=... ask=... candle=<red|green> -> open BUY/SELL | skip (not ...)`.
- Trade open/fail + equity diff lines throughout.

**When reviewing a log, record in the journal below:**
- Time of day the session ran and whether it hit the ideal window.
- How many minutes were red-as-buy vs skips (are we overtrading?).
- Actual P/L realized vs equity swing.
- Was it a WIN (hit +$5) or a LOSS (hit −$1)?
- Any repeats of runs that won (e.g., the "5 wins in a row").

---

## 5. Coding Experience & Lessons Learned (this project)

Things we learned building and debugging the trading scripts — filed so we don't repeat mistakes:

1. **Timing matters:** the first version fired at :58/:59 because the sleep math was wrong (`(60-seconds)-1`). Fixed to sleep precisely to the next :57 boundary. Lesson: compute `sleep_to = (57 - seconds + extra*60) - microseconds/1e6`, guard `<=0`.
2. **Busy-spin bug:** when already past :57, the old sleep returned 0 and the loop spun, spamming equity lines. The guard `if sleep_to <= 0: sleep_to = 1.0` fixes it.
3. **Per-point P/L on JP225Cash is tiny.** Measured ~$0.006/pt at 1.0 lot. `order_calc_profit` returned unreliable ~0 values for this CFD; `trade_tick_value` (1.0) is NOT a reliable basis. On 0.1 lot a single trade only moves equity by fractions of a cent — the ±$1/+$5 band only fires after many accumulated trades. **So lot size vs target band is a real tension on this instrument.** Consider: to make meaningful money, either raise lot or restrict to high-quality entries so fewer, bigger moves are taken.
4. **`trade_tick_value` ≠ real P/L for this CFD** — always verify per-lot P/L empirically before trusting sizing math.
5. **The MCP endpoint of build 6140 is buggy** (401 on every key variant). The standalone `MetaTrader5` Python API + our own scripts are the reliable path.
6. **Order_check is the friend** — validate order parameters before sending; it returned "Done" (retcode 0) confirming our requests were fine when order placement was suspected broken (it wasn't — the script just *skipped* on non-matching candle colors).
7. **Don't blindly buy every red / sell every green** — filter on window + reversal signals or the spreads eat us (research-backed, see §2–3).
8. **Bulk-close before exit** so we never leave stacked positions after a session.
9. **Log to timestamped files** with outcome + duration in the name → gives us a self-archiving performance record to review and tune.

---

## 6. Can It Run Anytime? Multiple Times a Day? (Tested)

### Can it run at any time?
- **Technically yes.** JP225Cash quotes ~24h on weekdays (futures-driven), and the scripts have no hour-gate — they work any time the terminal is connected.
- **But strategically, no — not optimally.** Outside Tokyo cash hours the spread widens, volume thins, and blindly buying red / selling green becomes an overtrading chore that pays the spread repeatedly. The journal's core point stands: the edge needs the right window + filters.

### Multi-session runner (built & working)
Created **`run_sessions.py`** to fire N capped sessions back-to-back:

```bash
python run_sessions.py --script trade_sell_trend --sessions 4 --gap 60 --max-min 30
python run_sessions.py --script trade_buy_trend  --sessions 3 --gap 30 --max-min 20
```

- Each session runs the chosen script as a subprocess; results (start time, duration, script, outcome) append to `session_results.csv`.
- **New: every session now has a `MAX_MINUTES` cap** (settable via `MT_MAX_MINUTES` env or script constant). On expiry the script bulk-closes everything and exits with outcome `TIME`, so a session can no longer run forever piling up positions.
- Override the per-session cap from the runner: `--max-min N`.

### Empirical result (live demo test)
- Ran 2-minute capped sessions of the sell script. Each hit the **TIME** stop (~2 min), bulk-closed (e.g. Session 2 "closed 1/1 positions"), wrote a `..._TIME.log`, advanced to the next session on the gap.
- **Key finding: the accumulation problem was reproducing real-world harm.** Before the cap, a stale `trade_sell_green.py` instance (PID 2456, *now renamed `trade_sell_trend.py`*) left running for hours stacked **29+ sell positions** because it never reached the ±$1/+$5 band. Lesson buried in code: **without a time stop, a low-per-trade-P/L CFD session can run indefinitely and rack up dozens of tiny positions.** The cap fixes this and is now mandatory for multi-run testing.
- CSV results so far:
  ```
  session_start            duration script  outcome
  2026-09-02 17:06:49      127      sell    TIME
  2026-09-02 17:09:07      170      sell    TIME
  ```

### Bottom line on "any time / multiple times a day"
- Multiple sessions a day is **fully supported** now (runner + time cap). Use it to sample different hours.
- Run it **often** to gather data, but expect black-and-white answers: sessions in the Tokyo-open window should fare better; sessions in chop/lunch are where TIME stops bleed the spread.
- **Treat the runner as a data-collection tool:** sample hours, log outcomes, then feed those results back into the journal so we converge on the winning windows.

---

## 6b. Consulting Free AI Models on the Strategy

Tool provided: **`ai_consult.py`** — feeds this journal + `session_results.csv` to a free model over HTTPS (no SDK) and prints back strategy feedback.

Get a free API key (no card) from one of:
- **Groq** → https://console.groq.com (default; `llama-3.3-70b-versatile` is free)
- **OpenRouter** → https://openrouter.ai (`meta-llama/llama-3.3-70b-instruct:free`)
- **Google AI Studio** → https://aistudio.google.com (`gemini-2.0-flash` free tier)

Then run:
```
set AI_PROVIDER=groq            (or openrouter / google)
set AI_API_KEY=sk-your-key
python ai_consult.py "Does my buy-red/sell-green M1 scalp have an edge on JP225Cash, and when is it strongest?"
python ai_consult.py --files my_note.md -- "add this context too"
```

Prompt ideas:
- "Review my session_results.csv and tell me which hour of day won."
- "Give me 3 concrete filters that would turn my candle-color strategy into a real edge."
- "What is my biggest risk of ruin here, and how do I fix it?"

**Rule:** use these as an advisor for ideas and critique, NOT as an unverified auto-trader. Keep the journal as the source of truth.

### Independent 2nd opinions obtained (via OpenCode Zen free models)

`consult_free_models.py` sent the real session evidence to free models over the OpenCode Zen API using a Zen API key. Full verbatim reviews are saved in **`free_model_reviews.md`**. Consensus of **laguna-s-2.1-free** and **nemotron-3-ultra-free** (ling-3.0-flash-fin-free returned no text):

1. **It is NOT an edge — it's a coin-flip that only survives on lucky days.** Both sessions lost while trading *against* the trend (33 sells in an uptrend, 19 buys in a downtrend), 0% win rate. "Real money would be gone in 3–5 sessions."
2. **Most damaging flaws (in order):** (a) counter-trend entries, (b) stacking positions with **no per-trade stop**, (c) a −$1/+$5 equity band that is mathematically impossible to reach profitably at $0.005/pt — +$5 needs ~1,000 points of favorable aggregate move; −$1 needs only ~200 adverse points (trivial intraday noise).
3. **Highest-leverage fixes (both models agree):**
   - **Flip to trend-following + trend filter:** BUY on GREEN M1 / SELL on RED M1, gated by an M5 EMA(50) slope filter (long only when slope > 0, short only when < 0).
   - **Per-trade SL/TP + hard position cap:** e.g. max 3 concurrent positions, SL = 1.5×ATR(14) M1, TP = 2×SL — removes the "bulk-close-only lottery ticket."
   - **Scale the equity target to volatility** instead of fixed +$5 (untouchable), and use a size where the risk/reward is actually reachable.

This matches my own review exactly.

### v2: Trend-following (implemented 2026-09-02)

Based on the independent model consensus, both scripts were rewritten to **trade WITH the trend** instead of counter-trend:

- **Poll every 5 seconds** (was :57 once per minute).
- **M5 EMA trend filter**: buy only when `EMA7 > EMA21` (bullish) ; sell only when `EMA7 < EMA21` (bearish). Values logged each new candle as `BULL`/`BEAR`/`FLAT`. (Note: Nikkei ~64k means literal "EMA > 0" is always true, so this uses the meaningful alignment interpretation.)
- **Follow the candle**: BUY while the M1 candle is GREEN (uptrend confirmation); SELL while it is RED (downtrend confirmation). Open again every 5s tick while condition holds.
- Kept: -$1 / +$5 equity stop, MAX_MINUTES TIME cap (default 30 via `MT_MAX_MINUTES`), timestamped `.log` output, magic numbers 900201 (buy) / 900301 (sell).

**Safety warning from the models still applies:** opening every 5 seconds while a candle stays green/red STACKS positions rapidly (up to ~12/min), which is the failure mode that lost money before. The -$1/+$5 bands and MAX_MINUTES cap are the only limit. Consider the per-trade stop / hard position cap fixes next.

### v3: Combined auto-looping script (trade_auto.py)

Replaces running the two scripts one-at-a-time. A single **`trade_auto.py`** runs both directions in an **infinite loop of sessions** (stops only when you close the script):

- Each session picks **ONE** direction at start from M5 EMA filter (EMA7>EMA21 → BUY; EMA7<EMA21 → SELL). Fixed for the whole session — no mid-session flip.
- Trades only that direction every 5s while conditions hold: BUY on green+BULL; SELL on red+BEAR.
- **No time cap** — a session ends ONLY on **WIN (+$5)** or **LOSS (−$1)** (equity vs session start), bulk-closing all. Re-enable a cap with `MT_MAX_MINUTES`.
- On WIN/LOSS: writes the session log (`trade_auto_s<N>_<ts>_<dur>_<WIN|LOSS>.log`), appends a row to `logs\session_results.csv` (`session_start,duration_s,direction,outcome`), waits **15s** gap, then starts the next session (fresh direction + fresh equity baseline).
- At startup, closes any **stale** positions left from a previous aborted run (same magic 920001) to start clean.

Magic number: **920001**. Config via env: `MT_MAX_MINUTES` (0=off), and constants `SESSION_GAP`, `POLL_SECONDS`.

> Starts with `MAX_MINUTES` **OFF** by default — read the risk warning below before any long unattended run.

### v3.1: Configurable EMA trend + env tuning (2026-09-03)

Replaced the fixed `EMA7 vs EMA21` M5 filter with **configurable periods**, defaulting to **`EMA1 vs EMA5`** (faster reaction). All major knobs are now env-overridable so no code edits are needed to tune:

| Env var | Default | Meaning |
|---|---|---|
| `MT_EMA_FAST` | 1 | fast EMA period (M5) |
| `MT_EMA_SLOW` | 5 | slow EMA period (M5) |
| `MT_LOT` | 0.1 | lot size |
| `MT_TARGET_MIN` | -1.0 | session loss threshold ($) |
| `MT_TARGET_MAX` | 5.0 | session win threshold ($) |
| `MT_MAX_MINUTES` | 0 | per-session time cap (min; 0=off) |
| `MT_SESSION_GAP` | 15 | gap between sessions (s) |
| `MT_POLL_SECONDS` | 5 | decision cadence (s) |

Example: `set MT_EMA_FAST=2 & set MT_EMA_SLOW=8 & python trade_auto.py`.

> Note: EMA1 is maximally twitchy (equals last close) — expect more direction flips between sessions versus the old 7/21.

### v4: Quick scalp in consolidation (trade_scalp.py, 2026-09-03)

A new standalone script for **short scalp trades in consolidation**, replacing the win/loss-band session-loop model with a **single continuous run**:

- **Runs until you press Ctrl+C** — no per-session loop, no WIN/LOSS equity bands, no auto-restart.
- **M1 timeframe** condition (re-checked every 5s, `MT_POLL_SECONDS`):
  - **Bull-ish** = `EMA1 > EMA5` **and** the current M1 candle is **green** → open a BUY.
  - **Bear-ish** = `EMA1 < EMA5` **and** the current M1 candle is **red** → open a SELL.
- **Stacks** a new 0.1 lot each poll tick while the condition holds (scaling into the scalp).
- **Every trade carries its own SL/TP** (`MT_SL_PTS` 100, `MT_TP_PTS` 12; JP225 point=1.0, so at 0.1 lot that's ~$10 risk / $1.20 reward per trade) — no more bare stacking.
- On Ctrl+C it **closes all open positions** and writes one summary log to `logs\`.

Config (env, all optional): `MT_LOT`, `MT_TP_PTS` (12), `MT_SL_PTS` (100), `MT_EMA_FAST` (1), `MT_EMA_SLOW` (5), `MT_POLL_SECONDS` (5). Magic: **920101**.

Run: `python trade_scalp.py` (stop with Ctrl+C). Verified live: buys opened with correct SL=price−100 / TP=price+12.

---

## 7. Session Log / Trade Record

All session logs and results are consolidated in the **`logs\`** folder (project root), including the historical logs:
- `logs\` — all timestamped session transcripts: `trade_<name>_<YYYYMMDD_HHMMSS>_<HHhMMmSSs>_<OUTCOME>.log`
- `logs\session_results.csv` — auto script summary (`session_start,duration_s,direction,outcome`)

| # | Date | Time (local/GMT) | Script | Window? | Trades | Net P/L | Outcome | Notes |
|---|------|------------------|--------|---------|--------|---------|---------|-------|
| 1 | 2026-09-02 17:06 | sell_green | chicago-afternoon | 0 | +0.00 | TIME | 2-min capped test |
| 2 | 2026-09-02 17:09 | sell_green | chicago-afternoon | 1 | +0.01 | TIME | 2-min capped test, closed 1/1 |

*(Append a row after every session, using the info from the generated `.log` file.)*

---

## 8. Improvement Roadmap (prioritized)

- [ ] **Filter entries**: only buy-red when higher-timeframe trend is flat/up; only sell-green when flat/down. (Highest value.)
- [ ] **Restrict to optimum window**: run primarily at Tokyo open; auto-skip lunch & EU-afternoon chop.
- [ ] Add **rejection-wick + oversold** confirmation before entering.
- [ ] Add **ADX trendiness gate** (skip strong-trend days).
- [ ] Add **USDJPY/yen correlation** confirmation.
- [ ] **Re-evaluate lot size vs $ band** on JP225Cash — decide whether to size up for real profit or stay micro.
- [ ] Automate **session scheduling** to launch the right script at the ideal window automatically.
- [ ] Use the **runner to sample hours** and converge on the winning windows from real data.
- [ ] Keep appending to this journal and review streaks (study the "5 wins in a row" pattern to reproduce it).

> **Bottom line:** The edge is not "buy every red candle." It's **"buy the red candle when today's move is in our favor, at a high-liquidity time, where the reversal is confirmed by structure."** Find that, size it well, and repeat.