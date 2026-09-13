"""
trade_auto.py

Donchian hedge strategy for JP225Cash (MT5).

Each M5 candle:
  - RED near lower Donchian band → open a BUY (mean-reversion buy dip)
  - GREEN near upper Donchian band → open a SELL (mean-reversion sell rally)
  - Both directions can exist simultaneously (hedge)

No exit rules — positions stay open until you stop the script (Ctrl+C),
which bulk-closes everything.

Runtime tuning (env vars):
  MT_LOT                      lot size (default 0.1)
  MT_SESSION_GAP              seconds between log snapshots (default 60)
  MT_POLL_SECONDS             decision cadence (default 5)
  MT_DONCHIAN_PERIOD          Donchian channel period in M5 bars (default 20)
  MT_DONCHIAN_NEAR_PIPS       how many points from band counts as "near" (default 15)
"""
import datetime
import os
import time

import MetaTrader5 as mt5

SYMBOL = "JP225Cash"
LOT = float(os.environ.get("MT_LOT", "0.1"))
MAGIC = 920001
SESSION_GAP = int(os.environ.get("MT_SESSION_GAP", "60"))   # seconds between snapshot logs
POLL_SECONDS = int(os.environ.get("MT_POLL_SECONDS", "5"))

# --- Donchian channel --------------------------------------------------------
DONCHIAN_PERIOD = int(os.environ.get("MT_DONCHIAN_PERIOD", "20"))
DONCHIAN_NEAR_PIPS = float(os.environ.get("MT_DONCHIAN_NEAR_PIPS", "15.0"))
DONCHIAN_BARS = DONCHIAN_PERIOD + 1

SCRIPT_NAME = "trade_auto"

TERMINAL = r"C:\Program Files\XM Global MT5\terminal64.exe"
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")

START_TIME = datetime.datetime.now()
LAST_SIGNAL_KEY = None
LAST_SNAPSHOT = 0


def log(msg):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)


def get_equity():
    info = mt5.account_info()
    return info.equity if info is not None else None


def get_position_counts():
    positions = mt5.positions_get()
    if not positions:
        return 0, 0
    buys = sum(1 for p in positions if p.type == mt5.POSITION_TYPE_BUY)
    sells = sum(1 for p in positions if p.type == mt5.POSITION_TYPE_SELL)
    return buys, sells


def get_total_pnl():
    positions = mt5.positions_get()
    if not positions:
        return 0.0
    return sum(p.profit for p in positions)


def close_all_positions():
    positions = mt5.positions_get()
    if not positions:
        log("no open positions to close")
        return
    closed = 0
    for pos in positions:
        si = mt5.symbol_info(pos.symbol)
        if si is None:
            continue
        is_buy = pos.type == mt5.POSITION_TYPE_BUY
        price = si.bid if is_buy else si.ask
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": pos.symbol,
            "volume": pos.volume,
            "type": mt5.ORDER_TYPE_SELL if is_buy else mt5.ORDER_TYPE_BUY,
            "position": pos.ticket,
            "price": price,
            "deviation": 50,
            "magic": MAGIC,
            "comment": "close all",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        if result is not None and result.retcode == mt5.TRADE_RETCODE_DONE:
            closed += 1
    log(f"closed {closed}/{len(positions)} positions")


def close_stale_magic_positions():
    positions = mt5.positions_get()
    if not positions:
        return
    stale = [p for p in positions if p.magic == MAGIC]
    if not stale:
        return
    log(f"Found {len(stale)} stale position(s) from previous run; closing.")
    for pos in stale:
        si = mt5.symbol_info(pos.symbol)
        if si is None:
            continue
        price = si.bid if pos.type == mt5.POSITION_TYPE_BUY else si.ask
        ot = mt5.ORDER_TYPE_SELL if pos.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
        req = {"action": mt5.TRADE_ACTION_DEAL, "symbol": pos.symbol, "volume": pos.volume,
               "type": ot, "position": pos.ticket, "price": price, "deviation": 50,
               "magic": MAGIC, "comment": "stale flush",
               "type_time": mt5.ORDER_TIME_GTC, "type_filling": mt5.ORDER_FILLING_IOC}
        mt5.order_send(req)


def donchian_channel():
    """Return (upper, lower, mid) from Donchian(DONCHIAN_PERIOD) on M5 closes."""
    rates = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M5, 0, DONCHIAN_BARS)
    if rates is None or len(rates) < DONCHIAN_PERIOD:
        return None, None, None
    highs = [float(r["high"]) for r in rates[1:DONCHIAN_PERIOD + 1]]
    lows = [float(r["low"]) for r in rates[1:DONCHIAN_PERIOD + 1]]
    if len(highs) < DONCHIAN_PERIOD:
        return None, None, None
    upper = max(highs)
    lower = min(lows)
    mid = (upper + lower) / 2.0
    return upper, lower, mid


def current_m5_candle():
    """Return the most recently completed M5 candle (dict) or None."""
    rates = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M5, 1, 1)
    if rates is None or len(rates) == 0:
        return None
    r = rates[0]
    return {
        "time": r["time"],
        "open": float(r["open"]),
        "close": float(r["close"]),
        "high": float(r["high"]),
        "low": float(r["low"]),
    }


def open_trade(order_type, price):
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": SYMBOL,
        "volume": LOT,
        "type": order_type,
        "price": price,
        "deviation": 50,
        "magic": MAGIC,
        "comment": "donchian hedge",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    result = mt5.order_send(request)
    if result is not None and result.retcode == mt5.TRADE_RETCODE_DONE:
        log(f"{'BUY' if order_type == mt5.ORDER_TYPE_BUY else 'SELL'} opened. "
            f"ticket={result.order}, price={result.price}")
    else:
        log(f"order failed. retcode={result.retcode if result else None} {mt5.last_error()}")


def log_snapshot():
    equity = get_equity()
    buys, sells = get_position_counts()
    pnl = get_total_pnl()
    log(f"SNAPSHOT equity={equity:.2f} P/L={pnl:+.2f} longs={buys} shorts={sells} total={buys+sells}")


def main():
    global LAST_SIGNAL_KEY, LAST_SNAPSHOT

    ok = mt5.initialize(path=TERMINAL)
    if not ok:
        log(f"MT5 initialize failed: {mt5.last_error()}")
        return
    log(f"MT5 initialized: {mt5.version()}")
    info = mt5.account_info()
    if info is None:
        log(f"account_info failed: {mt5.last_error()}")
        mt5.shutdown()
        return
    log(f"Account {info.login} on {info.server}, starting equity = {info.equity:.2f} {info.currency}")
    log(f"Symbol {SYMBOL}, lot {LOT}. Donchian({DONCHIAN_PERIOD}) M5, near={DONCHIAN_NEAR_PIPS} pips")
    log(f"HEDGE MODE: buy dips near lower band, sell rallies near upper band, both run simultaneously")
    log(f"No exit rules — press Ctrl+C to close everything and stop")

    mt5.symbol_select(SYMBOL, True)
    close_stale_magic_positions()

    LAST_SNAPSHOT = time.time()

    try:
        while True:
            now = time.time()

            # Periodic snapshot log
            if now - LAST_SNAPSHOT >= SESSION_GAP:
                log_snapshot()
                LAST_SNAPSHOT = now

            # --- Signal detection ---
            upper, lower, mid = donchian_channel()
            if upper is None:
                log("Donchian channel not ready (need more bars), waiting...")
                time.sleep(POLL_SECONDS)
                continue

            candle = current_m5_candle()
            if candle is None:
                log("no M5 data")
                time.sleep(POLL_SECONDS)
                continue

            candle_time = candle["time"]
            is_green = candle["close"] > candle["open"]
            is_red = candle["close"] < candle["open"]

            dist_to_lower = candle["close"] - lower
            dist_to_upper = upper - candle["close"]
            near_lower = dist_to_lower <= DONCHIAN_NEAR_PIPS
            near_upper = dist_to_upper <= DONCHIAN_NEAR_PIPS

            signal_key = f"{candle_time}"

            if is_red and near_lower:
                if signal_key != LAST_SIGNAL_KEY:
                    log(f"M5 red near LOW band: close={candle['close']:.2f} donchian_low={lower:.2f} dist={dist_to_lower:.1f} -> BUY")
                    si = mt5.symbol_info(SYMBOL)
                    if si:
                        open_trade(mt5.ORDER_TYPE_BUY, si.ask)
                        LAST_SIGNAL_KEY = signal_key
            elif is_green and near_upper:
                if signal_key != LAST_SIGNAL_KEY:
                    log(f"M5 green near HIGH band: close={candle['close']:.2f} donchian_high={upper:.2f} dist={dist_to_upper:.1f} -> SELL")
                    si = mt5.symbol_info(SYMBOL)
                    if si:
                        open_trade(mt5.ORDER_TYPE_SELL, si.bid)
                        LAST_SIGNAL_KEY = signal_key
            else:
                color = "green" if is_green else "red"
                log(f"M5 {color} mid-channel: close={candle['close']:.2f} lower={lower:.2f} upper={upper:.2f} -> no signal")

            time.sleep(POLL_SECONDS)

    except KeyboardInterrupt:
        log("Interrupted by user. Closing all positions.")
        close_all_positions()
    finally:
        mt5.shutdown()
        log("Stopped.")


if __name__ == "__main__":
    main()
