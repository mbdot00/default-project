"""
ha_btc_m5.py

Heikin-Ashi candle color follower for BTCUSD (MT5).

Strategy:
  On each NEW M5 candle, calculate the Heikin-Ashi candle:
    - GREEN (HA close > HA open)  -> open a BUY  0.01 lot
    - RED   (HA close < HA open)  -> open a SELL 0.01 lot
    - DOJI (HA close ~= HA open)  -> no trade
  Keeps stacking one position per candle until 100 open positions.

No exit rules -- positions stay open until you stop the script (Ctrl+C),
which bulk-closes everything.

Runtime tuning (env vars):
  MT_LOT          lot size (default 0.01)
  MT_MAX_POS      max open positions (default 100)
  MT_POLL_SECONDS poll cadence, seconds (default 5)
  MT_HA_BARS      bars to fetch for HA calc (default 10)
"""
import datetime
import os
import time
import sys

import MetaTrader5 as mt5

SYMBOL = "BTCUSD"
LOT = float(os.environ.get("MT_LOT", "0.01"))
MAGIC = 920201
MAX_POSITIONS = int(os.environ.get("MT_MAX_POS", "100"))
POLL_SECONDS = int(os.environ.get("MT_POLL_SECONDS", "5"))
HA_BARS = int(os.environ.get("MT_HA_BARS", "10"))

SCRIPT_NAME = "ha_btc_m5"
TERMINAL = r"C:\Program Files\XM Global MT5\terminal64.exe"
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")

START_TIME = datetime.datetime.now()
LAST_SIGNAL_KEY = None
LAST_SNAPSHOT = 0
SESSION_GAP = 60  # seconds between snapshot logs

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
            "comment": "close all",
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


def calc_ha_candles(rates):
    """Calculate Heikin-Ashi candles from raw OHLC rates.

    HA_Close = (Open + High + Low + Close) / 4
    HA_Open  = (prev_HA_Open + prev_HA_Close) / 2
    HA_High  = max(High, HA_Open, HA_Close)
    HA_Low   = min(Low, HA_Open, HA_Close)
    """
    if rates is None or len(rates) == 0:
        return []

    ha_candles = []
    ha_open = None

    for r in rates:
        o, h, l, c = float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"])
        ha_close = (o + h + l + c) / 4.0

        if ha_open is None:
            ha_open = o  # seed first bar with regular open
        else:
            ha_open = (ha_candles[-1]["ha_open"] + ha_candles[-1]["ha_close"]) / 2.0

        ha_high = max(h, ha_open, ha_close)
        ha_low = min(l, ha_open, ha_close)

        ha_candles.append({
            "time": r["time"],
            "ha_open": ha_open,
            "ha_close": ha_close,
            "ha_high": ha_high,
            "ha_low": ha_low,
        })

    return ha_candles


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
        "comment": f"ha {side.lower()}",
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
    log(f"SNAPSHOT equity={equity:.2f} P/L={pnl:+.2f} longs={buys} shorts={sells} total={total}/{MAX_POSITIONS}")


def write_log(interrupted=False):
    end = datetime.datetime.now()
    duration = (end - START_TIME).total_seconds()
    outcome = "INTERRUPTED" if interrupted else "STOPPED"
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
            f"Max positions: {MAX_POSITIONS}",
            f"Strategy     : M5 Heikin-Ashi candle color follower",
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
    log(f"Symbol {SYMBOL}, lot {LOT}. M5 HA color follower. Max {MAX_POSITIONS} positions.")
    log(f"No exit rules -- press Ctrl+C to close everything and stop")

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

            # Get M5 rates for HA calculation
            rates = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M5, 0, HA_BARS)
            if rates is None or len(rates) < 2:
                log("M5 data not ready, waiting...")
                time.sleep(POLL_SECONDS)
                continue

            # Calculate HA candles
            ha_candles = calc_ha_candles(rates)
            if not ha_candles:
                log("HA calculation failed, waiting...")
                time.sleep(POLL_SECONDS)
                continue

            # Current (most recent) HA candle
            current_ha = ha_candles[-1]
            is_green = current_ha["ha_close"] > current_ha["ha_open"]
            is_red = current_ha["ha_close"] < current_ha["ha_open"]

            # Count current positions
            _, _, total = get_position_counts()

            # New candle detection
            signal_key = str(rates[-1]["time"])

            if total >= MAX_POSITIONS:
                if signal_key != LAST_SIGNAL_KEY:
                    log(f"MAX POSITIONS ({MAX_POSITIONS}) reached, no new trades.")
                    LAST_SIGNAL_KEY = signal_key
                time.sleep(POLL_SECONDS)
                continue

            if is_green:
                if signal_key != LAST_SIGNAL_KEY:
                    log(f"M5 HA GREEN: ha_open={current_ha['ha_open']:.2f} ha_close={current_ha['ha_close']:.2f} -> BUY 0.01 (total={total}/{MAX_POSITIONS})")
                    si = mt5.symbol_info(SYMBOL)
                    if si:
                        if open_trade(mt5.ORDER_TYPE_BUY, si.ask):
                            LAST_SIGNAL_KEY = signal_key
            elif is_red:
                if signal_key != LAST_SIGNAL_KEY:
                    log(f"M5 HA RED: ha_open={current_ha['ha_open']:.2f} ha_close={current_ha['ha_close']:.2f} -> SELL 0.01 (total={total}/{MAX_POSITIONS})")
                    si = mt5.symbol_info(SYMBOL)
                    if si:
                        if open_trade(mt5.ORDER_TYPE_SELL, si.bid):
                            LAST_SIGNAL_KEY = signal_key
            else:
                if signal_key != LAST_SIGNAL_KEY:
                    log(f"M5 HA neutral (doji): ha_open={current_ha['ha_open']:.2f} ha_close={current_ha['ha_close']:.2f} -> no trade")
                    LAST_SIGNAL_KEY = signal_key

            time.sleep(POLL_SECONDS)

    except KeyboardInterrupt:
        log("Interrupted by user. Closing all positions.")
        close_all_positions()
    finally:
        try:
            write_log(interrupted=sys.exc_info()[0] is KeyboardInterrupt)
        finally:
            mt5.shutdown()
            log("Stopped.")


if __name__ == "__main__":
    main()
