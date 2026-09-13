"""
simulate.py — Simulate alternative strategies on PSAR trade data.
"""

import MetaTrader5 as mt5
from datetime import datetime, timedelta

TERMINAL = r"C:\Program Files\XM Global MT5\terminal64.exe"
ok = mt5.initialize(path=TERMINAL)
if not ok:
    print(f"MT5 init failed: {mt5.last_error()}")
    exit(1)

# Get all PSAR trades
deals = mt5.history_deals_get(datetime.now() - timedelta(hours=24), datetime.now())
psar_deals = [d for d in deals if d.magic == 920901]

# Build closed trades from the sequence
trades = []
current_side = None
entry_price = None
entry_time = None

for d in psar_deals:
    side = 'BUY' if d.type == mt5.DEAL_TYPE_BUY else 'SELL'
    if current_side is None:
        current_side = side
        entry_price = d.price
        entry_time = datetime.fromtimestamp(d.time)
    elif side != current_side:
        exit_price = d.price
        exit_time = datetime.fromtimestamp(d.time)
        pnl = (exit_price - entry_price) * 0.1 if current_side == 'BUY' else (entry_price - exit_price) * 0.1
        trades.append({
            'side': current_side,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'pnl': pnl,
            'entry_time': entry_time,
            'exit_time': exit_time
        })
        current_side = side
        entry_price = d.price
        entry_time = exit_time

total_original = sum(t['pnl'] for t in trades)
print(f"Total closed trades: {len(trades)}")
print(f"Original strategy P/L: ${total_original:+.2f}")

# Sim 1: Inverted strategy (BUY->SELL, SELL->BUY)
print(f"\n{'='*60}")
print(f"SIM 1: INVERTED STRATEGY (Buy when PSAR says Sell)")
print(f"{'='*60}")
inv_pnl = 0
for t in trades:
    inv_pnl_trade = -t['pnl']
    inv_pnl += inv_pnl_trade

print(f"Inverted P/L: ${inv_pnl:+.2f}")
print(f"Difference: ${inv_pnl - total_original:+.2f}")

# Sim 2: Martingale (lot +0.1 per loss, reset on win)
print(f"\n{'='*60}")
print(f"SIM 2: MARTINGALE LOT (0.1 + 0.1 per loss, reset on win)")
print(f"{'='*60}")
mart_pnl = 0
current_lot = 0.1
max_lot = 0
for t in trades:
    lot = current_lot
    mart_trade_pnl = t['pnl'] * (lot / 0.1)
    mart_pnl += mart_trade_pnl

    if mart_trade_pnl < 0:
        current_lot += 0.1
    else:
        current_lot = 0.1

    if lot > max_lot:
        max_lot = lot

print(f"Martingale P/L: ${mart_pnl:+.2f}")
print(f"Max lot used: {max_lot:.1f}")

# Sim 3: Inverted + Martingale
print(f"\n{'='*60}")
print(f"SIM 3: INVERTED + MARTINGALE")
print(f"{'='*60}")
inv_mart_pnl = 0
current_lot = 0.1
max_lot = 0
for t in trades:
    lot = current_lot
    inv_pnl_trade = -t['pnl']
    scaled = inv_pnl_trade * (lot / 0.1)
    inv_mart_pnl += scaled

    if scaled < 0:
        current_lot += 0.1
    else:
        current_lot = 0.1

    if lot > max_lot:
        max_lot = lot

print(f"Inverted + Martingale P/L: ${inv_mart_pnl:+.2f}")
print(f"Max lot used: {max_lot:.1f}")

# Summary
print(f"\n{'='*60}")
print(f"SIMULATION SUMMARY")
print(f"{'='*60}")
print(f"{'Strategy':<35} {'P/L':>10} {'Max Lot':>10}")
print("-" * 55)
print(f"{'Original':<35} {total_original:>+10.2f} {'0.1':>10}")
print(f"{'Inverted':<35} {inv_pnl:>+10.2f} {'0.1':>10}")
print(f"{'Martingale':<35} {mart_pnl:>+10.2f} {max_lot:>10.1f}")
print(f"{'Inverted + Martingale':<35} {inv_mart_pnl:>+10.2f} {max_lot:>10.1f}")

mt5.shutdown()
