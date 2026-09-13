"""
trade_scalp.py

Quick scalper for JP225Cash (MT5) - scope: short scalp trades in consolidation.

Strategy (per poll tick, on the M1 timeframe):
  Bull-ish condition = EMA(1)_M1 > EMA(5)_M1  AND the current M1 candle is GREEN
      -> open/stack a BUY  0.1 lot
  Bear-ish condition = EMA(1)_M1 < EMA(5)_M1  AND the current M1 candle is RED
      -> open/stack a SELL 0.1 lot
  Every trade gets a PER-TRADE stop-loss and take-profit (SL 100 pts, TP 12 pts).

The loop keeps running until you close the script (Ctrl+C). On exit it closes all
open positions and writes one summary log to logs\\.

Runtime tuning (env vars), all optional:
  MT_LOT        lot size (default 0.1)
  MT_TP_PTS     take-profit distance in points  (default 12)
  MT_SL_PTS     stop-loss  distance in points  (default 100)
  MT_POLL_SECONDS  poll cadence, seconds (default 5)
"""
import datetime
import os
import sys
import time

import MetaTrader5 as mt5

SYMBOL = "JP225Cash"
LOT = float(os.environ.get("MT_LOT", "0.1"))
TP_PTS = float(os.environ.get("MT_TP_PTS", "12"))
SL_PTS = float(os.environ.get("MT_SL_PTS", "100"))
POLL_SECONDS = int(os.environ.get("MT_POLL_SECONDS", "5"))
MAGIC = 920101

# EMA periods for the M1 trend filter
EMA_FAST = int(os.environ.get("MT_EMA_FAST", "1"))
EMA_SLOW = int(os.environ.get("MT_EMA_SLOW", "5"))
EMA_BARS = EMA_SLOW + 4

SCRIPT_NAME = "trade_scalp"
TERMINAL = r"C:\Program Files\XM Global MT5\terminal64.exe"
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")

LOG_LINES = []
SESSION_START = datetime.datetime.now()
OPEN_DIRECTION = None  # current detected direction for display/logging


def log(msg):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    LOG_LINES.append(line)


def ema(values, period):
    if not values or len(values) < period:
        return None
    k = 2.0 / (period + 1)
    ema = values[0]
    for price in values[1:]:
        ema = price * k + ema * (1 - k)
    return ema


def m1_condition():
    """Evaluate the M1 scalp condition.

    Returns (long_ok, short_ok, ema_fast, ema_slow, candle_color)
      long_ok  = EMA_FAST > EMA_SLOW and M1 candle is GREEN
      short_ok = EMA_FAST < EMA_SLOW and M1 candle is RED
    """
    rates = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M1, 0, EMA_BARS)
    if rates is None or len(rates) == 0:
        return False, False, None, None, None
    closes = [float(r["close"]) for r in rates]
    last = rates[-1]
    open_price = float(last["open"])
    live_price = float(last["close"])
    green = live_price >= open_price
    candle = "green" if green else "red"

    efast = ema(closes, EMA_FAST)
    eslow = ema(closes, EMA_SLOW)
    if efast is None or eslow is None:
        return False, False, efast, eslow, candle

    long_ok = (efast > eslow) and green
    short_ok = (efast < eslow) and not green
    return long_ok, short_ok, efast, eslow, candle


def open_trade(order_type, price):
    point = mt5.symbol_info(SYMBOL).point
    sl = price - SL_PTS * point if order_type == mt5.ORDER_TYPE_BUY else price + SL_PTS * point
    tp = price + TP_PTS * point if order_type == mt5.ORDER_TYPE_BUY else price - TP_PTS * point
    side = "BUY" if order_type == mt5.ORDER_TYPE_BUY else "SELL"
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": SYMBOL,
        "volume": LOT,
        "type": order_type,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": 50,
        "magic": MAGIC,
        "comment": side.lower(),
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    result = mt5.order_send(request)
    if result is not None and result.retcode == mt5.TRADE_RETCODE_DONE:
        log(f"{side} opened. ticket={result.order}, price={price:.2f}, sl={sl:.2f}, tp={tp:.2f}")
        return True
    log(f"{side} failed. retcode={result.retcode if result else None} msg={mt5.last_error()}")
    return False


def close_all_positions():
    positions = mt5.positions_get(symbol=SYMBOL)
    if not positions:
        log("no open positions to close")
        return
    n = 0
    for pos in positions:
        if pos.magic != MAGIC:
            continue
        si = mt5.symbol_info(pos.symbol)
        is_buy = pos.type == mt5.POSITION_TYPE_BUY
        price = si.bid if is_buy else si.ask
        req = {
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
        r = mt5.order_send(req)
        if r is not None and r.retcode == mt5.TRADE_RETCODE_DONE:
            n += 1
            log(f"closed {pos.ticket} ({'buy' if is_buy else 'sell'}) @ {price:.2f}")
    log(f"closed {n} position(s)")


def write_log(interrupted=False):
    end = datetime.datetime.now()
    duration = (end - SESSION_START).total_seconds()
    outcome = "INTERRUPTED" if interrupted else "STOPPED"
    os.makedirs(LOG_DIR, exist_ok=True)
    dur_str = "%02dh%02dm%02ds" % (int(duration // 3600), int((duration % 3600) // 60), int(duration % 60))
    try:
        path = os.path.join(
            LOG_DIR, f"{SCRIPT_NAME}_{SESSION_START.strftime('%Y%m%d_%H%M%S')}_{dur_str}_{outcome}.log")
        info = mt5.account_info()
        header = [
            f"Script       : {SCRIPT_NAME}",
            f"Symbol       : {SYMBOL}",
            f"Lot          : {LOT}",
            f"TP           : {TP_PTS} pts",
            f"SL           : {SL_PTS} pts",
            f"M1 trend     : EMA{EMA_FAST} vs EMA{EMA_SLOW} + candle color",
            f"Start equity : {info.equity if info else 0:.2f}",
            f"End equity   : {get_equity():.2f}",
            f"Session start: {SESSION_START.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Session end  : {end.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Duration     : {duration:.1f}s",
            f"Outcome      : {outcome}",
            "-" * 70,
        ]
        with open(path, "w", encoding="utf-8") as f:
            for line in header + LOG_LINES:
                f.write(line + "\n")
        _append_csv(duration, outcome)
        print(f"[{time.strftime('%H:%M:%S')}] log written: {path}", flush=True)
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] could not write log: {e}", flush=True)


def _append_csv(duration, outcome):
    try:
        csv_path = os.path.join(LOG_DIR, "session_results.csv")
        os.makedirs(LOG_DIR, exist_ok=True)
        if not os.path.exists(csv_path):
            with open(csv_path, "w", encoding="utf-8") as f:
                f.write("session_start,duration_s,direction,outcome\n")
        row = ",".join([
            SESSION_START.strftime("%Y-%m-%d %H:%M:%S"),
            f"{duration:.0f}",
            OPEN_DIRECTION or "NA",
            outcome,
        ])
        with open(csv_path, "a", encoding="utf-8") as f:
            f.write(row + "\n")
    except OSError as e:
        print(f"[{time.strftime('%H:%M:%S')}] could not append CSV: {e}", flush=True)


def get_equity():
    info = mt5.account_info()
    return info.equity if info is not None else 0.0


def main():
    global OPEN_DIRECTION
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
    log(f"Account {info.login} on {info.server}, equity = {info.equity:.2f} {info.currency}")
    log(f"Symbol {SYMBOL}, lot {LOT}. Per-trade TP {TP_PTS} pts / SL {SL_PTS} pts. Poll {POLL_SECONDS}s.")
    log(f"M1 condition: EMA{EMA_FAST} vs EMA{EMA_SLOW} + candle color. Runs until Ctrl+C.")
    mt5.symbol_select(SYMBOL, True)

    # close any leftover positions from a previous run of this script
    leftover = mt5.positions_get(symbol=SYMBOL)
    stale = [p for p in leftover if p.magic == MAGIC] if leftover else []
    if stale:
        log(f"Found {len(stale)} stale position(s) from a previous run; closing to start clean.")
        for p in stale:
            si = mt5.symbol_info(p.symbol)
            price = si.bid if p.type == mt5.POSITION_TYPE_BUY else si.ask
            ot = mt5.ORDER_TYPE_SELL if p.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
            r = mt5.order_send({"action": mt5.TRADE_ACTION_DEAL, "symbol": p.symbol, "volume": p.volume,
                                "type": ot, "position": p.ticket, "price": price, "deviation": 50,
                                "magic": MAGIC, "comment": "stale flush",
                                "type_time": mt5.ORDER_TIME_GTC, "type_filling": mt5.ORDER_FILLING_IOC})
            if r is not None and r.retcode == mt5.TRADE_RETCODE_DONE:
                log(f"closed stale {p.ticket} @ {price:.2f}")

    last_candle_time = None
    try:
        while True:
            long_ok, short_ok, efast, eslow, candle = m1_condition()
            if efast is None or eslow is None:
                log("M1 EMA not available yet, waiting...")
                time.sleep(POLL_SECONDS)
                continue

            side = "BUY" if long_ok else "SELL" if short_ok else "FLAT"
            OPEN_DIRECTION = side if side != "FLAT" else OPEN_DIRECTION
            ema_str = f"ema{EMA_FAST}={efast:.1f} ema{EMA_SLOW}={eslow:.1f} {'BULL' if long_ok else 'BEAR' if short_ok else 'FLAT'}"

            # log each new M1 candle once
            cd = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M1, 0, 1)
            ct = cd[-1]["time"] if cd is not None and len(cd) else None
            if ct != last_candle_time:
                last_candle_time = ct
                candle_dt = datetime.datetime.fromtimestamp(ct).strftime("%H:%M:%S")
                log(f"M1 {candle_dt} candle={candle} {ema_str} -> {'scalp ' + side if side != 'FLAT' else 'flat'}")

            if long_ok:
                si = mt5.symbol_info(SYMBOL)
                if si is None:
                    log("symbol_info failed")
                    time.sleep(POLL_SECONDS)
                    continue
                open_trade(mt5.ORDER_TYPE_BUY, si.ask)
            elif short_ok:
                si = mt5.symbol_info(SYMBOL)
                if si is None:
                    log("symbol_info failed")
                    time.sleep(POLL_SECONDS)
                    continue
                open_trade(mt5.ORDER_TYPE_SELL, si.bid)
            else:
                log(f"no trade (candle={candle} {ema_str})")

            time.sleep(POLL_SECONDS)
    except KeyboardInterrupt:
        print("[Ctrl+C] stopping...", flush=True)
        LOG_LINES.append("[Ctrl+C] stopping...")
    finally:
        close_all_positions()
        try:
            write_log(interrupted=sys.exc_info()[0] is KeyboardInterrupt)
        finally:
            mt5.shutdown()


if __name__ == "__main__":
    main()