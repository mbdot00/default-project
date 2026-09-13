"""
psar_backtest.py — Vectorized backtest of PSAR flip strategy on M1.
"""

import MetaTrader5 as mt5
import pandas as pd
from ta.trend import PSARIndicator
import numpy as np
from datetime import datetime

TERMINAL = r"C:\Program Files\XM Global MT5\terminal64.exe"
SYMBOL = "JP225Cash"
LOT = 0.1
SAR_STEP = 0.01
SAR_MAX = 0.05
PIP_VALUE = 0.10  # $0.10 per point for 0.1 lot on JP225Cash

ok = mt5.initialize(path=TERMINAL)
if not ok:
    print(f"MT5 init failed: {mt5.last_error()}")
    exit(1)

rates = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M1, 0, 10000)
if rates is None or len(rates) < 100:
    print("Not enough data")
    mt5.shutdown()
    exit(1)

df = pd.DataFrame(rates)
df['time'] = pd.to_datetime(df['time'], unit='s')
df = df.sort_values('time').reset_index(drop=True)

print(f"Data: {len(df)} M1 bars from {df['time'].iloc[0]} to {df['time'].iloc[-1]}")
print(f"Period: {(df['time'].iloc[-1] - df['time'].iloc[0]).days} days")

# Vectorized PSAR calculation (whole dataset at once)
psar = PSARIndicator(high=df['high'], low=df['low'], close=df['close'],
                     step=SAR_STEP, max_step=SAR_MAX)
df['psar'] = psar.psar()
df['direction'] = np.where(df['psar'] < df['close'], 'bullish', 'bearish')

# Shift direction by 1 (use prev bar's direction to trade current bar)
df['prev_direction'] = df['direction'].shift(1)

# Backtest: iterate through bars and trade
trades = []
current_pos = None
entry_price = None
entry_time = None
entry_bar = None
equity = 0

for i in range(50, len(df)):
    bar = df.iloc[i]
    prev_dir = bar['prev_direction']
    
    if pd.isna(prev_dir):
        continue
    
    if current_pos is None:
        current_pos = 'BUY' if prev_dir == 'bullish' else 'SELL'
        entry_price = bar['open']
        entry_time = bar['time']
        entry_bar = i
    else:
        flip = (current_pos == 'BUY' and prev_dir == 'bearish') or (current_pos == 'SELL' and prev_dir == 'bullish')
        
        if flip:
            exit_price = bar['open']
            pnl = (exit_price - entry_price) * PIP_VALUE if current_pos == 'BUY' else (entry_price - exit_price) * PIP_VALUE
            trades.append({
                'entry_time': entry_time,
                'exit_time': bar['time'],
                'position': current_pos,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'pnl': pnl,
                'bars_held': i - entry_bar
            })
            equity += pnl
            current_pos = 'BUY' if prev_dir == 'bullish' else 'SELL'
            entry_price = bar['open']
            entry_time = bar['time']
            entry_bar = i

# Close final position
if current_pos is not None:
    last_bar = df.iloc[-1]
    exit_price = last_bar['close']
    pnl = (exit_price - entry_price) * PIP_VALUE if current_pos == 'BUY' else (entry_price - exit_price) * PIP_VALUE
    trades.append({
        'entry_time': entry_time,
        'exit_time': last_bar['time'],
        'position': current_pos,
        'entry_price': entry_price,
        'exit_price': exit_price,
        'pnl': pnl,
        'bars_held': len(df) - entry_bar
    })
    equity += pnl

# Results
print(f"\n{'='*80}")
print(f"BACKTEST: PSAR Flip (step={SAR_STEP}, max={SAR_MAX}) on M1 | Lot {LOT}")
print(f"{'='*80}")

if trades:
    buys = [t for t in trades if t['position'] == 'BUY']
    sells = [t for t in trades if t['position'] == 'SELL']
    winning = [t for t in trades if t['pnl'] > 0]
    losing = [t for t in trades if t['pnl'] < 0]
    
    total_pnl = sum(t['pnl'] for t in trades)
    avg_pnl = total_pnl / len(trades)
    
    # Max drawdown from equity curve
    running_eq = 0
    peak = 0
    max_dd = 0
    for i in range(50, len(df)):
        # Find trades up to this bar
        bar_time = df.iloc[i]['time']
        eq_at_bar = sum(t['pnl'] for t in trades if t['exit_time'] <= bar_time)
        if eq_at_bar > peak:
            peak = eq_at_bar
        dd = peak - eq_at_bar
        if dd > max_dd:
            max_dd = dd
    
    print(f"Total trades: {len(trades)}")
    print(f"  BUYs: {len(buys)}, SELLs: {len(sells)}")
    print(f"Winning: {len(winning)} ({len(winning)/len(trades)*100:.1f}%)")
    print(f"Losing: {len(losing)} ({len(losing)/len(trades)*100:.1f}%)")
    print(f"Total P/L: ${total_pnl:+.2f}")
    print(f"Avg P/L per trade: ${avg_pnl:+.2f}")
    print(f"Max win: ${max(t['pnl'] for t in trades):+.2f}")
    print(f"Max loss: ${min(t['pnl'] for t in trades):+.2f}")
    print(f"Max drawdown: ${max_dd:.2f}")
    print(f"Final equity change: ${equity:+.2f}")
    
    if buys:
        buy_pnl = sum(t['pnl'] for t in buys)
        buy_win = len([t for t in buys if t['pnl'] > 0])
        print(f"\nBUY trades: {len(buys)}, P/L: ${buy_pnl:+.2f}, Win: {buy_win/len(buys)*100:.1f}%")
    if sells:
        sell_pnl = sum(t['pnl'] for t in sells)
        sell_win = len([t for t in sells if t['pnl'] > 0])
        print(f"SELL trades: {len(sells)}, P/L: ${sell_pnl:+.2f}, Win: {sell_win/len(sells)*100:.1f}%")
    
    print(f"\nFirst 5 trades:")
    for t in trades[:5]:
        print(f"  {t['entry_time']} -> {t['exit_time']} {t['position']} {t['entry_price']:.2f} -> {t['exit_price']:.2f} P/L=${t['pnl']:+.2f} ({t['bars_held']} bars)")
    
    print(f"\nLast 5 trades:")
    for t in trades[-5:]:
        print(f"  {t['entry_time']} -> {t['exit_time']} {t['position']} {t['entry_price']:.2f} -> {t['exit_price']:.2f} P/L=${t['pnl']:+.2f} ({t['bars_held']} bars)")
    
    # Daily breakdown
    print(f"\nDaily P/L:")
    daily = {}
    for t in trades:
        day = t['exit_time'].strftime('%Y-%m-%d')
        daily[day] = daily.get(day, 0) + t['pnl']
    for day in sorted(daily):
        print(f"  {day}: ${daily[day]:+.2f}")

mt5.shutdown()
