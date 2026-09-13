"""
btc_donchian_m5.py

Donchian channel strategy for BTCUSD (MT5).

Strategy:
  On each NEW M5 candle, check where price sits in the Donchian channel:
    - Lower half (close < midline)  -> BUY 0.01
    - Upper half (close > midline)  -> SELL 0.01
    - On midline                   -> no trade

  Donchian channel:
    Upper = highest high over N M5 bars
    Lower = lowest low over N M5 bars
    Midline = (Upper + Lower) / 2

  Runs for 2 hours, then auto-closes all positions and exits.

Runtime tuning (env vars):
  MT_LOT            lot size (default 0.01)
  MT_DONCHIAN_PERIOD Donchian period in M5 bars (default 20)
  MT_SESSION_MINUTES session length in minutes (default 120)
  MT_POLL_SECONDS   poll cadence (default 5)
"""
import datetime
import os
import time
import sys

import MetaTrader5 as mt5

SYMBOL = "BTCUSD"
LOT = float(os.environ.get("MT_LOT", "0.01"))
MAGIC = 920301
DONCHIAN_PERIOD = int(os.environ.get("MT_DONCHIAN_PERIOD", "20"))
SESSION_MINUTES = int(os.environ.get("MT_SESSION_MINUTES", "120"))
POLL_SECONDS = int(os.environ.get("MT_POLL_SECONDS", "5"))
DONCHIAN_BARS = DONCHIAN_PERIOD + 1

SCRIPT_NAME = "btc_donchian_m5"
TERMINAL = r"C:\Program Files\XM Global MT5\terminal64.exe"
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")

START_TIME = datetime.datetime.now()
END_TIME = START_TIME + datetime.timedelta(minutes=SESSION_MINUTES)
LAST_SIGNAL_KEY = None
LAST_SNAPSHOT = 0
SESSION_GAP = 300  # seconds between snapshot logs (5 min)

LOG_LINES = []


def log(msg):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    LOG_LINES.append(line)


def get_equity():
    info = mt5.account_info()
    return info.equity if info is not None else None


def get_position_counts():
    positions = mt5.positions_get()
    if not positions:
        return 0, 0, 0
    magic_positions = [p for p in positions if p.magic == MAGIC]
    buys = sum(1 for p in magic_positions if p.type == mt5.POSITION_TYPE_BUY)
    sells = sum(1 for p in magic_positions if p.type == mt5.POSITION_TYPE_SELL)
    return buys, sells, len(magic_positions)


def get_total_pnl():
    positions = mt5.positions_get()
    if not positions:
        return 0.0
    magic_positions = [p for p in positions if p.magic == MAGIC]
    return sum(p.profit for p in magic_positions)


def close_all_positions():
    positions = mt5.positions_get()
    if not positions:
        log("no open positions to close")
        return
    closed = 0
    for pos in positions:
        if pos.magic != MAGIC:
            continue
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
            "comment": "session close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        if result is not None and result.retcode == mt5.TRADE_RETCODE_DONE:
            closed += 1
    log(f"closed {closed} position(s)")


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
    """Return (upper, lower, mid) from Donchian(DONCHIAN_PERIOD) on M5 bars."""
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


def open_trade(order_type, price):
    side = "BUY" if order_type == mt5.ORDER_TYPE_BUY else "SELL"
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": SYMBOL,
        "volume": LOT,
        "type": order_type,
        "price": price,
        "deviation": 50,
        "magic": MAGIC,
        "comment": f"donchian {side.lower()}",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    result = mt5.order_send(request)
    if result is not None and result.retcode == mt5.TRADE_RETCODE_DONE:
        log(f"{side} opened. ticket={result.order}, price={result.price:.2f}")
        return True
    else:
        log(f"{side} failed. retcode={result.retcode if result else None} {mt5.last_error()}")
        return False


def log_snapshot():
    equity = get_equity()
    buys, sells, total = get_position_counts()
    pnl = get_total_pnl()
    remaining = (END_TIME - datetime.datetime.now()).total_seconds()
    rem_str = "%02dm%02ds" % (int(remaining // 60), int(remaining % 60))
    log(f"SNAPSHOT equity={equity:.2f} P/L={pnl:+.2f} longs={buys} shorts={sells} total={total} remaining={rem_str}")


def write_log(outcome):
    end = datetime.datetime.now()
    duration = (end - START_TIME).total_seconds()
    os.makedirs(LOG_DIR, exist_ok=True)
    dur_str = "%02dh%02dm%02ds" % (int(duration // 3600), int((duration % 3600) // 60), int(duration % 60))
    try:
        path = os.path.join(
            LOG_DIR, f"{SCRIPT_NAME}_{START_TIME.strftime('%Y%m%d_%H%M%S')}_{dur_str}_{outcome}.log")
        info = mt5.account_info()
        buys, sells, total = get_position_counts()
        header = [
            f"Script       : {SCRIPT_NAME}",
            f"Symbol       : {SYMBOL}",
            f"Lot          : {LOT}",
            f"Donchian     : {DONCHIAN_PERIOD} M5 bars",
            f"Session      : {SESSION_MINUTES} min",
            f"Start equity : {info.equity if info else 0:.2f}",
            f"End equity   : {get_equity():.2f}",
            f"Final positions: {total} (longs={buys}, shorts={sells})",
            f"Session start: {START_TIME.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Session end  : {end.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Duration     : {duration:.1f}s",
            f"Outcome      : {outcome}",
            "-" * 70,
        ]
        with open(path, "w", encoding="utf-8") as f:
            for line in header + LOG_LINES:
                f.write(line + "\n")
        _append_csv(duration, outcome, buys, sells, total)
        print(f"[{time.strftime('%H:%M:%S')}] log written: {path}", flush=True)
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] could not write log: {e}", flush=True)


def _append_csv(duration, outcome, buys, sells, total):
    try:
        csv_path = os.path.join(LOG_DIR, "session_results.csv")
        os.makedirs(LOG_DIR, exist_ok=True)
        if not os.path.exists(csv_path):
            with open(csv_path, "w", encoding="utf-8") as f:
                f.write("session_start,direction,outcome,duration_s,final_longs,final_shorts,final_total\n")
        row = ",".join([
            START_TIME.strftime("%Y-%m-%d %H:%M:%S"),
            SCRIPT_NAME,
            outcome,
            f"{duration:.0f}",
            str(buys),
            str(sells),
            str(total),
        ])
        with open(csv_path, "a", encoding="utf-8") as f:
            f.write(row + "\n")
    except OSError as e:
        print(f"[{time.strftime('%H:%M:%S')}] could not append CSV: {e}", flush=True)


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
    log(f"Symbol {SYMBOL}, lot {LOT}. Donchian({DONCHIAN_PERIOD}) M5. Session {SESSION_MINUTES} min.")
    log(f"BUY lower half, SELL upper half. Auto-close at {END_TIME.strftime('%H:%M:%S')}")

    mt5.symbol_select(SYMBOL, True)
    close_stale_magic_positions()

    LAST_SNAPSHOT = time.time()
    outcome = "TIME"

    try:
        while True:
            now = time.time()
            now_dt = datetime.datetime.now()

            # Session timeout check
            if now_dt >= END_TIME:
                log(f"Session time ({SESSION_MINUTES} min) reached. Closing all positions.")
                outcome = "TIME"
                break

            # Periodic snapshot log
            if now - LAST_SNAPSHOT >= SESSION_GAP:
                log_snapshot()
                LAST_SNAPSHOT = now

            # Get Donchian channel
            upper, lower, mid = donchian_channel()
            if upper is None:
                log("Donchian channel not ready, waiting...")
                time.sleep(POLL_SECONDS)
                continue

            # Get current M5 candle (most recent completed)
            rates = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M5, 1, 1)
            if rates is None or len(rates) == 0:
                log("M5 data not ready, waiting...")
                time.sleep(POLL_SECONDS)
                continue

            candle = rates[0]
            close_price = float(candle["close"])
            candle_time = candle["time"]

            # Determine position in channel
            channel_height = upper - lower
            if channel_height > 0:
                position_pct = (close_price - lower) / channel_height
            else:
                position_pct = 0.5

            signal_key = str(candle_time)

            if close_price < mid:
                # Lower half -> BUY
                if signal_key != LAST_SIGNAL_KEY:
                    log(f"M5 close={close_price:.2f} in LOWER half (mid={mid:.2f}, lower={lower:.2f}, upper={upper:.2f}) -> BUY")
                    si = mt5.symbol_info(SYMBOL)
                    if si:
                        if open_trade(mt5.ORDER_TYPE_BUY, si.ask):
                            LAST_SIGNAL_KEY = signal_key
            elif close_price > mid:
                # Upper half -> SELL
                if signal_key != LAST_SIGNAL_KEY:
                    log(f"M5 close={close_price:.2f} in UPPER half (mid={mid:.2f}, lower={lower:.2f}, upper={upper:.2f}) -> SELL")
                    si = mt5.symbol_info(SYMBOL)
                    if si:
                        if open_trade(mt5.ORDER_TYPE_SELL, si.bid):
                            LAST_SIGNAL_KEY = signal_key
            else:
                # Exactly on midline
                if signal_key != LAST_SIGNAL_KEY:
                    log(f"M5 close={close_price:.2f} ON midline (mid={mid:.2f}) -> no trade")
                    LAST_SIGNAL_KEY = signal_key

            time.sleep(POLL_SECONDS)

    except KeyboardInterrupt:
        log("Interrupted by user. Closing all positions.")
        outcome = "STOPPED"
    finally:
        close_all_positions()
        try:
            write_log(outcome)
        finally:
            mt5.shutdown()
            log("Stopped.")


if __name__ == "__main__":
    main()
