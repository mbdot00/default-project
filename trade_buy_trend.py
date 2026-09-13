import time
import datetime
import os

import MetaTrader5 as mt5

SYMBOL = "JP225Cash"
LOT = 0.1
MAGIC = 900201
TARGET_MIN = -1.0   # loss threshold relative to session-start equity
TARGET_MAX = 5.0    # gain threshold relative to session-start equity
MAX_MINUTES = int(os.environ.get("MT_MAX_MINUTES", "30"))  # 0 = no time cap
SCRIPT_NAME = "trade_buy_trend"

TERMINAL = r"C:\Program Files\XM Global MT5\terminal64.exe"
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")

LOG_LINES = []
SESSION_START = datetime.datetime.now()


def _fmt(ts):
    return ts.strftime("%Y%m%d_%H%M%S")


def _log_name(outcome, dur):
    duration = "%02dh%02dm%02ds" % (int(dur // 3600), int((dur % 3600) // 60), int(dur % 60))
    return f"{SCRIPT_NAME}_{_fmt(SESSION_START)}_{duration}_{outcome}.log"


def write_log(outcome, msg_lines):
    """Write the session transcript to a timestamped log file with outcome."""
    end = datetime.datetime.now()
    duration = (end - SESSION_START).total_seconds()
    os.makedirs(LOG_DIR, exist_ok=True)
    path = os.path.join(LOG_DIR, _log_name(outcome, duration))
    header = [
        f"Script       : {SCRIPT_NAME}",
        f"Symbol       : {SYMBOL}",
        f"Lot          : {LOT}",
        f"Session start: {SESSION_START.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Session end  : {end.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Duration     : {duration:.1f}s",
        f"Outcome      : {outcome}",
        "-" * 70,
    ]
    try:
        with open(path, "w", encoding="utf-8") as f:
            for line in header + msg_lines:
                f.write(line + "\n")
        print(f"[{time.strftime('%H:%M:%S')}] log written: {path}", flush=True)
    except OSError as e:
        print(f"[{time.strftime('%H:%M:%S')}] could not write log: {e}", flush=True)


def log(msg):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    LOG_LINES.append(line)


def get_equity():
    info = mt5.account_info()
    return info.equity if info is not None else None


def close_all_positions():
    positions = mt5.positions_get()
    if not positions:
        log("no open positions to close")
        return True
    closed = 0
    for pos in positions:
        symbol = pos.symbol
        si = mt5.symbol_info(symbol)
        if si is None:
            log(f"cannot close {pos.ticket}: symbol_info failed")
            continue
        is_buy = pos.type == mt5.POSITION_TYPE_BUY
        price = si.bid if is_buy else si.ask
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
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
            log(f"closed {pos.ticket} ({'buy' if is_buy else 'sell'}) @ {price:.2f}")
        else:
            log(f"failed to close {pos.ticket}: r={result.retcode if result else None} {mt5.last_error()}")
    log(f"closed {closed}/{len(positions)} positions")
    return closed == len(positions)


def live_m1():
    """Return the currently-forming M1 bar (open..last) as a dict, or None."""
    rates = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M1, 0, 2)
    if rates is None or len(rates) == 0:
        return None
    last = rates[-1]
    # last['close'] is the live/last traded price of the forming bar
    return {
        "time": last["time"],
        "open": last["open"],
        "close": last["close"],
        "high": last["high"],
        "low": last["low"],
    }


def ema(values, period):
    """Exponential moving average over a list of closing prices."""
    if not values or len(values) < 2:
        return None
    k = 2.0 / (period + 1)
    ema = values[0]
    for price in values[1:]:
        ema = price * k + ema * (1 - k)
    return ema


def m5_ema_filter():
    """Return (buy_ok, sell_ok, ema7, ema21) using M5 closes.

    buy_ok  = EMA7 > EMA21  (bullish alignment, rising trend)
    sell_ok = EMA7 < EMA21  (bearish alignment, falling trend)
    """
    rates = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M5, 0, 22)
    if rates is None or len(rates) == 0:
        return False, False, None, None
    closes = [float(r["close"]) for r in rates]
    ema7 = ema(closes, 7)
    ema21 = ema(closes, 21)
    if ema7 is None or ema21 is None:
        return False, False, ema7, ema21
    return ema7 > ema21, ema7 < ema21, ema7, ema21


def main():
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
    log(f"Account {info.login} on {info.server}, equity start = {info.equity:.2f} {info.currency}")
    start_equity = info.equity

    mt5.symbol_select(SYMBOL, True)
    si = mt5.symbol_info(SYMBOL)
    if si is None:
        log(f"Symbol {SYMBOL} not found")
        mt5.shutdown()
        return
    log(f"Trading {SYMBOL} @ {si.bid:.2f}/{si.ask:.2f}, lot {LOT}")

    last_candle_time = None
    last_candle_logged = None
    outcome = "STOPPED"
    log("Running (trend-follow BUY: M5 EMA7>EMA21 and M1 candle green, every 5s, stop if equity <= %.2f or >= %.2f from start)." % (
        start_equity + TARGET_MIN, start_equity + TARGET_MAX))

    while True:
        equity = get_equity()
        if equity is None:
            log("Cannot read equity, retrying...")
        else:
            diff = equity - start_equity
            log(f"equity {equity:.2f} (diff +{diff:.2f})")

            if diff <= TARGET_MIN:
                outcome = "LOSS"
                log(f"STOP: equity diff {diff:.2f} <= {TARGET_MIN:.2f}. Closing all positions and exiting.")
                close_all_positions()
                break
            if diff >= TARGET_MAX:
                outcome = "WIN"
                log(f"STOP: equity diff {diff:.2f} >= {TARGET_MAX:.2f}. Closing all positions and exiting.")
                close_all_positions()
                break

            if MAX_MINUTES and (datetime.datetime.now() - SESSION_START).total_seconds() >= MAX_MINUTES * 60:
                outcome = "TIME"
                log(f"TIME STOP: reached {MAX_MINUTES} minutes. Closing all positions and exiting.")
                close_all_positions()
                break

        candle = live_m1()
        if candle is None:
            log("no M1 data")
            time.sleep(5)
            continue

        candle_time = candle["time"]
        open_price = candle["open"]
        live_price = candle["close"]
        is_green = live_price > open_price
        color = "green" if is_green else "red"

        buy_ok, sell_ok, ema7, ema21 = m5_ema_filter()
        ema_str = (f"ema7={ema7:.1f} ema21={ema21:.1f} "
                   f"{'BULL' if buy_ok else 'BEAR' if sell_ok else 'FLAT'}")

        if candle_time != last_candle_time:
            last_candle_time = candle_time
            candle_dt = datetime.datetime.fromtimestamp(candle_time).strftime("%H:%M:%S")
            log(f"M1 {candle_dt} open={open_price:.2f} live={live_price:.2f} "
                f"candle={color} {ema_str} -> {'follow BUY' if is_green and buy_ok else 'hold'}")
            last_candle_logged = candle_time

        if is_green and buy_ok:
            si = mt5.symbol_info(SYMBOL)
            if si is None:
                log("symbol_info failed")
                time.sleep(5)
                continue
            live_ask = si.ask
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": SYMBOL,
                "volume": LOT,
                "type": mt5.ORDER_TYPE_BUY,
                "price": live_ask,
                "deviation": 50,
                "magic": MAGIC,
                "comment": "buy trend",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            result = mt5.order_send(request)
            if result is not None and result.retcode == mt5.TRADE_RETCODE_DONE:
                log(f"BUY opened. ticket={result.order}, price={result.price}")
            else:
                log(f"BUY failed. retcode={result.retcode if result else None} "
                    f"msg={mt5.last_error()}")
        elif color == "red":
            log(f"candle is {color} -> no BUY (red, trend down)")

        time.sleep(5)

    mt5.shutdown()
    log("Stopped.")
    write_log(outcome, LOG_LINES)


if __name__ == "__main__":
    main()