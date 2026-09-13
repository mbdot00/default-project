"""workflow_show.py — Show the PSAR Inverted + Martingale workflow."""

import MetaTrader5 as mt5
import pandas as pd
from ta.trend import PSARIndicator

TERMINAL = r"C:\Program Files\XM Global MT5\terminal64.exe"
ok = mt5.initialize(path=TERMINAL)
if not ok:
    print(f"MT5 init failed: {mt5.last_error()}")
    exit(1)

print("=== PSAR INVERTED + MARTINGALE WORKFLOW ===\n")

# Step 1
print("STEP 1: Fetch M1 data")
rates = mt5.copy_rates_from_pos("JP225Cash", mt5.TIMEFRAME_M1, 0, 500)
df = pd.DataFrame(rates)
df["time"] = pd.to_datetime(df["time"], unit="s")
print(f"  Got {len(df)} M1 candles")
print(f"  Last candle: {df.iloc[-1]['time']}")

# Step 2
print("\nSTEP 2: Calculate PSAR (step=0.01, max=0.05)")
psar = PSARIndicator(high=df["high"], low=df["low"], close=df["close"],
                     step=0.01, max_step=0.05)
df["psar"] = psar.psar()

# Step 3
print("\nSTEP 3: Determine direction from last COMPLETED bar (index -2)")
recent_psar = df["psar"].iloc[-2]
recent_close = df["close"].iloc[-2]
recent_time = df["time"].iloc[-2]
direction = "BULLISH" if recent_psar < recent_close else "BEARISH"
print(f"  Time: {recent_time}")
print(f"  PSAR: {recent_psar:.2f}")
print(f"  Close: {recent_close:.2f}")
pos = "below" if direction == "BULLISH" else "above"
print(f"  Direction: {direction} (PSAR {pos} price)")

# Step 4
print("\nSTEP 4: Apply INVERSION")
inv_action = "SELL" if direction == "BULLISH" else "BUY"
print(f"  PSAR says: {direction}")
print(f"  Inverted action: {inv_action}")

# Step 5
print("\nSTEP 5: Check current position (magic 920902)")
positions = mt5.positions_get()
magic_positions = [p for p in positions if p.magic == 920902]
print(f"  Open positions: {len(magic_positions)}")
for p in magic_positions:
    side = "BUY" if p.type == mt5.POSITION_TYPE_BUY else "SELL"
    print(f"    {side} vol={p.volume} open={p.price_open:.2f} pnl={p.profit:+.2f}")

# Step 6
print("\nSTEP 6: Martingale lot calculation")
if magic_positions:
    curr_pnl = magic_positions[0].profit
    if curr_pnl < 0:
        next_lot = magic_positions[0].volume + 0.1
        print(f"  Current P/L: {curr_pnl:+.2f} (loss)")
        print(f"  Next lot: {next_lot:.1f} (increased by 0.1)")
    else:
        next_lot = 0.1
        print(f"  Current P/L: {curr_pnl:+.2f} (win)")
        print(f"  Next lot: {next_lot:.1f} (reset)")
else:
    print(f"  No position, lot = 0.1")

# Step 7
print("\nSTEP 7: Decision")
if len(magic_positions) == 0:
    print(f"  No position -> OPEN {inv_action} at market")
else:
    curr_side = "BUY" if magic_positions[0].type == mt5.POSITION_TYPE_BUY else "SELL"
    if curr_side == inv_action:
        print(f"  Already holding {curr_side} -> HOLD")
    else:
        print(f"  Holding {curr_side} but signal is {inv_action} -> FLIP")
        print(f"  1. Close {curr_side} at market")
        print(f"  2. Open {inv_action}")

# Step 8
print("\nSTEP 8: Recent PSAR values (last 10 M1)")
print(f"{'Time':<20} {'Close':>8} {'PSAR':>8} {'PSAR Dir':<10} {'Action':<10}")
print("-" * 56)
for i in range(-10, 0):
    row = df.iloc[i]
    d = "BULLISH" if row["psar"] < row["close"] else "BEARISH"
    inv = "SELL" if d == "BULLISH" else "BUY"
    print(f"{str(row['time']):<20} {row['close']:>8.2f} {row['psar']:>8.2f} {d:<10} {inv:<10}")

mt5.shutdown()
