"""
psar_inv_mart.py

Inverted PSAR + Martingale strategy for JP225Cash (MT5) using M1 candles.

Strategy:
  - PSAR step=0.01, max_step=0.05 on M1 candles
  - INVERTED: Buy when PSAR is ABOVE price (bearish)
  - INVERTED: Sell when PSAR is BELOW price (bullish)
  - Only 1 trade at a time, close before flip
  - Martingale: lot +0.1 per loss, reset to 0.1 on win
  - No max lot cap

Runtime tuning (env vars):
  MT_LOT              lot size (default 0.1)
  MT_SAR_STEP         PSAR step (default 0.01)
  MT_SAR_MAX          PSAR max step (default 0.05)
  MT_POLL_SECONDS     poll cadence (default 5)
  MT_DATA_BARS        bars for PSAR calc (default 500)
"""
import datetime
import os
import time
import sys

import MetaTrader5 as mt5
import pandas as pd
from ta.trend import PSARIndicator

SYMBOL = "JP225Cash"
BASE_LOT = float(os.environ.get("MT_LOT", "0.1"))
MAGIC = 920902
SAR_STEP = float(os.environ.get("MT_SAR_STEP", "0.01"))
SAR_MAX = float(os.environ.get("MT_SAR_MAX", "0.05"))
POLL_SECONDS = int(os.environ.get("MT_POLL_SECONDS", "5"))
DATA_BARS = int(os.environ.get("MT_DATA_BARS", "500"))
TIMEFRAME = mt5.TIMEFRAME_M1

SCRIPT_NAME = "psar_inv_mart"
TERMINAL = r"C:\Program Files\XM Global MT5\terminal64.exe"
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")

START_TIME = datetime.datetime.now()
LAST_SNAPSHOT = 0
SESSION_GAP = 300

LOG_LINES = []

# Martingale state
current_lot = BASE_LOT
last_trade_pnl = 0.0


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


def get_total_pnl():
    return sum(p.profit for p in get_magic_positions())


def close_all_positions():
    """Close all positions and return the P/L of the closed position."""
    global current_lot
    
    magic_positions = get_magic_positions()
    if not magic_positions:
        return 0.0
    
    total_pnl = 0.0
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
            "comment": "inv mart flip",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        if result is not None and result.retcode == mt5.TRADE_RETCODE_DONE:
            closed += 1
            total_pnl += pos.profit
    
    log(f"closed {closed} position(s), P/L=${total_pnl:+.2f}")
    
    # Martingale logic
    if total_pnl < 0:
        current_lot += 0.1
        log(f"MARTINGALE: loss, lot increased to {current_lot:.1f}")
    else:
        current_lot = BASE_LOT
        log(f"MARTINGALE: win, lot reset to {current_lot:.1f}")
    
    return total_pnl


def close_stale_magic_positions():
    magic_positions = get_magic_positions()
    if not magic_positions:
        return
    log(f"Found {len(magic_positions)} stale position(s); closing.")
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


def calc_psar(df):
    """Calculate PSAR using ta library."""
    psar = PSARIndicator(high=df['high'], low=df['low'], close=df['close'],
                         step=SAR_STEP, max_step=SAR_MAX)
    return psar.psar()


def get_psar_direction():
    """
    Calculate PSAR on M1 candles.
    Returns: 'bullish', 'bearish', or None
    """
    rates = mt5.copy_rates_from_pos(SYMBOL, TIMEFRAME, 0, DATA_BARS)
    if rates is None or len(rates) < 10:
        return None

    df = pd.DataFrame(rates)
    df['psar'] = calc_psar(df)

    # Most recent completed candle
    recent_psar = df['psar'].iloc[-2]
    recent_close = df['close'].iloc[-2]

    return 'bullish' if recent_psar < recent_close else 'bearish'


def open_trade(order_type, price, lot):
    side = "BUY" if order_type == mt5.ORDER_TYPE_BUY else "SELL"
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": SYMBOL,
        "volume": lot,
        "type": order_type,
        "price": price,
        "deviation": 50,
        "magic": MAGIC,
        "comment": f"inv mart {side.lower()}",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    result = mt5.order_send(request)
    if result is not None and result.retcode == mt5.TRADE_RETCODE_DONE:
        log(f"{side} opened. ticket={result.order}, price={result.price:.2f}, lot={lot:.1f}")
        return True
    else:
        log(f"{side} failed. retcode={result.retcode if result else None} {mt5.last_error()}")
        return False


def log_snapshot():
    equity = get_equity()
    magic_positions = get_magic_positions()
    pnl = get_total_pnl()
    longs = sum(1 for p in magic_positions if p.type == mt5.POSITION_TYPE_BUY)
    shorts = sum(1 for p in magic_positions if p.type == mt5.POSITION_TYPE_SELL)
    log(f"SNAPSHOT equity={equity:.2f} P/L={pnl:+.2f} longs={longs} shorts={shorts} total={len(magic_positions)} lot={current_lot:.1f}")


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
        magic_positions = get_magic_positions()
        buys = sum(1 for p in magic_positions if p.type == mt5.POSITION_TYPE_BUY)
        sells = sum(1 for p in magic_positions if p.type == mt5.POSITION_TYPE_SELL)
        header = [
            f"Script       : {SCRIPT_NAME}",
            f"Symbol       : {SYMBOL}",
            f"Base lot     : {BASE_LOT}",
            f"PSAR         : step={SAR_STEP}, max={SAR_MAX} on M1",
            f"Start equity : {info.equity if info else 0:.2f}",
            f"End equity   : {get_equity():.2f}",
            f"Final positions: {len(magic_positions)} (longs={buys}, shorts={sells})",
            f"Session start: {START_TIME.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Session end  : {end.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Duration     : {duration:.1f}s",
            f"Outcome      : {outcome}",
            "-" * 70,
        ]
        with open(path, "w", encoding="utf-8") as f:
            for line in header + LOG_LINES:
                f.write(line + "\n")
        _append_csv(duration, outcome, buys, sells, len(magic_positions))
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
    global LAST_SNAPSHOT, current_lot

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
    log(f"Symbol {SYMBOL}, base lot {BASE_LOT}. INVERTED PSAR + MARTINGALE.")
    log(f"Bearish (PSAR>price) -> BUY. Bullish (PSAR<price) -> SELL.")
    log(f"Lot: +0.1 per loss, reset to {BASE_LOT} on win. No max cap.")

    mt5.symbol_select(SYMBOL, True)
    close_stale_magic_positions()

    LAST_SNAPSHOT = time.time()
    last_direction = None

    try:
        while True:
            now = time.time()
            now_dt = datetime.datetime.now()

            # Periodic snapshot
            if now - LAST_SNAPSHOT >= SESSION_GAP:
                log_snapshot()
                LAST_SNAPSHOT = now

            # Get PSAR direction
            direction = get_psar_direction()
            if direction is None:
                log("PSAR not ready, waiting...")
                time.sleep(POLL_SECONDS)
                continue

            # Check current position
            magic_positions = get_magic_positions()
            holding = None
            for pos in magic_positions:
                holding = pos.type
                break

            si = mt5.symbol_info(SYMBOL)
            if si is None:
                time.sleep(POLL_SECONDS)
                continue

            # INVERTED: trade on direction change
            # PSAR bearish (above price) -> BUY
            # PSAR bullish (below price) -> SELL
            if direction != last_direction:
                if direction == "bearish":
                    if holding != mt5.POSITION_TYPE_BUY:
                        log(f"PSAR BEARISH (inverted): close all, open BUY lot={current_lot:.1f}")
                        close_all_positions()
                        open_trade(mt5.ORDER_TYPE_BUY, si.ask, current_lot)
                    else:
                        log(f"HOLD BUY. PSAR bearish.")
                else:  # bullish
                    if holding != mt5.POSITION_TYPE_SELL:
                        log(f"PSAR BULLISH (inverted): close all, open SELL lot={current_lot:.1f}")
                        close_all_positions()
                        open_trade(mt5.ORDER_TYPE_SELL, si.bid, current_lot)
                    else:
                        log(f"HOLD SELL. PSAR bullish.")

                last_direction = direction
            else:
                if now_dt.second == 0:
                    log(f"HOLD {'BUY' if holding == mt5.POSITION_TYPE_BUY else 'SELL' if holding == mt5.POSITION_TYPE_SELL else 'NONE'}. PSAR {direction}. lot={current_lot:.1f}")

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
