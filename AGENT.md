# JP225Cash MT5 Trading Project

**Platform:** MetaTrader 5 (XM Global)  
**Terminal:** `C:\Program Files\XM Global MT5\terminal64.exe`  
**Account:** 334072459 on XMGlobal-MT5 9  
**Location:** `C:\Users\x\Documents\Default Project`

---

## Active Strategy: PSAR Flip (M1)

**Script:** `psar_trader.py`  
**Status:** Running (session `proc_f4a82bf9bd53`)

### Strategy Rules

- **Indicator:** Parabolic SAR on M1 candles (step=0.01, max_step=0.05)
- **Signal:** PSAR below price → **BUY** | PSAR above price → **SELL**
- **Execution:** Close current position before opening new one
- **Timing:** Check at :55 each minute (5-second poll)
- **Lot size:** 0.1 (margin ~$0.08)
- **Magic number:** 920901

### Position Management

- Always exactly 1 position (or zero during flip)
- `close_all_positions()` then `open_trade(new_direction)`
- No TP/SL — exit only on PSAR flip

### Run Command

```bash
cd "C:\Users\x\Documents\Default Project"
uv run --with metatrader5 python psar_trader.py
```

### Env Overrides

```bash
MT_LOT=0.1                # lot size
MT_SAR_STEP=0.01          # PSAR acceleration start
MT_SAR_MAX=0.05           # PSAR acceleration max
MT_POLL_SECONDS=5         # poll cadence
MT_DATA_BARS=500          # bars for PSAR calc
```

---

## Project Files

| File | Description |
|---|---|
| `psar_trader.py` | Active PSAR flip strategy (M1) |
| `donchian_session9.py` | Previous PSAR strategy (M15) — not running |
| `donchian_session8.py` | Previous Donchian flip strategy — not running |
| `btc_donchian_m5.py` | BTCUSD Donchian strategy — not running |
| `jp225_donchian_m5.py` | JP225 Donchian strategy — not running |
| `ha_btc_m5.py` | BTCUSD Heikin-Ashi strategy — not running |
| `trade_auto.py` | JP225 Donchian mean-reversion (older) |
| `logs/` | Session logs and `session_results.csv` |

---

## Inactive Magic Numbers

| Magic | Strategy | Status |
|---|---|---|
| 920001 | trade_auto.py (Donchian reversion) | Not running |
| 920008 | "flip-flop" EA — unknown origin | **Active elsewhere** |
| 920101-920401 | Older strategies | Not running |
| 920801 | donchian_session8/9.py | Not running |
| 920901 | **psar_trader.py** | **Running** |

---

## Known Issues & Fixes

### 2026-09-09: Multiple Zombie Instances
**Problem:** Killing background processes left orphans. Multiple instances of same script fought each other.  
**Fix:** Before starting, always `tasklist` and kill all `python.exe` running scripts. Single instance only.

### 2026-09-09: 5-Second Poll Skipping :57
**Problem:** Poll at :50→:55→:00→:05 missed the :57 trigger.  
**Fix:** Use `second < 55` with per-minute guard (`last_trade_minute`).

### 2026-09-09: Magic 920008 "Flip-Flop" Conflict
**Problem:** Unknown EA running elsewhere on the account closing positions at :57 every minute.  
**Status:** Unresolved — not on this machine.

---

## PSAR Calculation (ta library)

```python
from ta.trend import PSARIndicator
import pandas as pd

rates = mt5.copy_rates_from_pos('JP225Cash', mt5.TIMEFRAME_M1, 0, 500)
df = pd.DataFrame(rates)
psar = PSARIndicator(high=df['high'], low=df['low'], close=df['close'],
                     step=0.01, max_step=0.05)
df['psar'] = psar.psar()

direction = 'bullish' if df['psar'].iloc[-2] < df['close'].iloc[-2] else 'bearish'
```

---

## Session Logs

- `logs/psar_trader_YYYYMMDD_HHMMSS_DURATION_OUTCOME.log`
- `logs/session_results.csv` — aggregated across all sessions

---

## Account Notes

- **Equity (2026-09-10):** ~$12.86 (recovering from earlier session losses)
- **Margin per 0.1 lot JP225Cash:** ~$0.08
- **Risk:** No hard stop-loss. Relies entirely on PSAR flip to exit.
