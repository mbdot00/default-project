"""Quick smoke test: verify Donchian signal detection works correctly."""
import os
import sys

import MetaTrader5 as mt5

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import trade_auto as ta

TERMINAL = r"C:\Program Files\XM Global MT5\terminal64.exe"

ok = mt5.initialize(path=TERMINAL)
if not ok:
    print(f"MT5 initialize failed: {mt5.last_error()}")
    sys.exit(1)

print(f"MT5 initialized: {mt5.version()}")
info = mt5.account_info()
print(f"Account {info.login}, equity={info.equity:.2f}")

mt5.symbol_select(ta.SYMBOL, True)

# Test Donchian channel calculation
upper, lower, mid = ta.donchian_channel()
if upper is None:
    print("Donchian channel not ready yet (need more bars)")
else:
    print(f"Donchian({ta.DONCHIAN_PERIOD}): upper={upper:.2f} mid={mid:.2f} lower={lower:.2f}")

# Test current M5 candle
candle = ta.current_m5_candle()
if candle:
    print(f"M5 candle: open={candle['open']:.2f} close={candle['close']:.2f} high={candle['high']:.2f} low={candle['low']:.2f}")
    is_green = candle['close'] > candle['open']
    is_red = candle['close'] < candle['open']
    dist_to_lower = candle['close'] - lower if lower else None
    dist_to_upper = upper - candle['close'] if upper else None
    print(f"  is_green={is_green} is_red={is_red}")
    print(f"  dist_to_lower={dist_to_lower:.1f} dist_to_upper={dist_to_upper:.1f}" if dist_to_lower else "  n/a")
    print(f"  near_lower (<={ta.DONCHIAN_NEAR_PIPS}) = {dist_to_lower <= ta.DONCHIAN_NEAR_PIPS if dist_to_lower else False}")
    print(f"  near_upper (<={ta.DONCHIAN_NEAR_PIPS}) = {dist_to_upper <= ta.DONCHIAN_NEAR_PIPS if dist_to_upper else False}")

mt5.shutdown()
print("\nDonchian signal detection verified.")
