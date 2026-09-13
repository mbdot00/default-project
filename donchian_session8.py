"""
donchian_session8.py

Donchian channel flip strategy for JP225Cash (MT5).

Strategy:
  - Fixed lot 0.1, no TP, no SL.
  - Start with a BUY position.
  - Flip logic:
      * Holding BUY + price near upper band (within 20 pts) -> close BUY, open SELL
      * Holding SELL + price near lower band (within 20 pts) -> close SELL, open BUY
  - "Near" = within 20 points of the Donchian band edge.
  - Trade timing: acts on the 57th second of each minute.
  - Runs indefinitely until Ctrl+C / kill.

Runtime tuning (env vars):
  MT_LOT              lot size (default 0.1)
  MT_DONCHIAN_PERIOD  Donchian period in M5 bars (default 20)
  MT_NEAR_PIPS        points from band edge to count as "near" (default 20)
  MT_POLL_SECONDS     poll cadence (default 5)
"""
import datetime
import os
import time
import sys

import MetaTrader5 as mt5

SYMBOL = "JP225Cash"
LOT = float(os.environ.get("MT_LOT", "100"))
MAGIC = 920801
DONCHIAN_PERIOD = int(os.environ.get("MT_DONCHIAN_PERIOD", "20"))
NEAR_PIPS = float(os.environ.get("MT_NEAR_PIPS", "20.0"))
POLL_SECONDS = int(os.environ.get("MT_POLL_SECONDS", "5"))
DONCHIAN_BARS = DONCHIAN_PERIOD + 1

SCRIPT_NAME = "donchian_session8"
TERMINAL = r"C:\Program Files\XM Global MT5\terminal64.exe"
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")

START_TIME = datetime.datetime.now()
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


def get_magic_positions():
    positions = mt5.positions_get()
    if not positions:
        return []
    return [p for p in positions if p.magic == MAGIC]


def get_position_counts():
    magic_positions = get_magic_positions()
    buys = sum(1 for p in magic_positions if p.type == mt5.POSITION_TYPE_BUY)
    sells = sum(1 for p in magic_positions if p.type == mt5.POSITION_TYPE_SELL)
    return buys, sells, len(magic_positions)


def get_total_pnl():
    magic_positions = get_magic_positions()
    return sum(p.profit for p in magic_positions)


def close_all_positions():
    magic_positions = get_magic_positions()
    if not magic_positions:
        log("no open positions to close")
        return
    closed = 0
    for pos in magic_positions:
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
            "comment": "flip close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        if result is not None and result.retcode == mt5.TRADE_RETCODE_DONE:
            closed += 1
    log(f"closed {closed} position(s)")


def close_stale_magic_positions():
    magic_positions = get_magic_positions()
    if not magic_positions:
        return
    log(f"Found {len(magic_positions)} stale position(s) from previous run; closing.")
    for pos in magic_positions:
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
        "comment": f"flip {side.lower()}",
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
    log(f"SNAPSHOT equity={equity:.2f} P/L={pnl:+.2f} longs={buys} shorts={sells} total={total}")


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
            f"Donchian     : {DONCHIAN_PERIOD} M5 bars, near={NEAR_PIPS} pips",
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
    global LAST_SNAPSHOT

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
    log(f"Symbol {SYMBOL}, lot {LOT}. Donchian({DONCHIAN_PERIOD}) M5, near={NEAR_PIPS} pips.")
    log(f"Flip strategy: BUY -> flip to SELL near upper band, SELL -> flip to BUY near lower band.")

    mt5.symbol_select(SYMBOL, True)
    close_stale_magic_positions()

    LAST_SNAPSHOT = time.time()

    try:
        while True:
            now = time.time()
            now_dt = datetime.datetime.now()

            # Trade once per minute in the 55-59s window (poll hits it at :58)
            if now_dt.second < 55:
                time.sleep(POLL_SECONDS)
                continue

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

            # Get current price
            si = mt5.symbol_info(SYMBOL)
            if si is None:
                time.sleep(POLL_SECONDS)
                continue
            price = si.bid  # use bid for distance calc

            # Check current position
            magic_positions = get_magic_positions()
            holding = None
            for pos in magic_positions:
                if pos.magic == MAGIC:
                    holding = pos.type
                    break

            dist_to_upper = upper - price
            dist_to_lower = price - lower

            near_upper = dist_to_upper <= NEAR_PIPS
            near_lower = dist_to_lower <= NEAR_PIPS

            if near_lower:
                # Price near lower band -> ensure BUY
                if holding != mt5.POSITION_TYPE_BUY:
                    log(f"LOWER BAND: price={price:.2f} lower={lower:.2f} dist={dist_to_lower:.1f} -> close all, open BUY")
                    close_all_positions()
                    open_trade(mt5.ORDER_TYPE_BUY, si.ask)
                else:
                    log(f"HOLD BUY. at lower band. dist_lower={dist_to_lower:.1f}")
            elif near_upper:
                # Price near upper band -> ensure SELL
                if holding != mt5.POSITION_TYPE_SELL:
                    log(f"UPPER BAND: price={price:.2f} upper={upper:.2f} dist={dist_to_upper:.1f} -> close all, open SELL")
                    close_all_positions()
                    open_trade(mt5.ORDER_TYPE_SELL, si.bid)
                else:
                    log(f"HOLD SELL. at upper band. dist_upper={dist_to_upper:.1f}")
            else:
                dist_str = f"dist_upper={dist_to_upper:.1f} dist_lower={dist_to_lower:.1f}"
                log(f"HOLD {'BUY' if holding == mt5.POSITION_TYPE_BUY else 'SELL' if holding == mt5.POSITION_TYPE_SELL else 'NONE'}. {dist_str}")

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
