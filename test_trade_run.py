"""
test_trade_run.py
Run a short test of trade_auto sessions with a small time cap to generate
real logs for review. Each session has MAX_MINUTES=3 cap and SESSION_GAP=10s.
"""
import datetime
import os
import sys
import time

import MetaTrader5 as mt5

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# Import the trade_auto module to reuse its logic
import trade_auto as ta

# Override for a quick test
ta.MAX_MINUTES = 3          # 3 min cap per session
ta.SESSION_GAP = 10         # 10s gap between sessions
ta.LOG_DIR = os.path.join(HERE, "logs")

TERMINAL = r"C:\Program Files\XM Global MT5\terminal64.exe"


def main():
    ok = mt5.initialize(path=TERMINAL)
    if not ok:
        print(f"MT5 initialize failed: {mt5.last_error()}")
        return
    print(f"MT5 initialized: {mt5.version()}")
    info = mt5.account_info()
    if info is None:
        print(f"account_info failed: {mt5.last_error()}")
        mt5.shutdown()
        return
    print(f"Account {info.login}, starting equity = {info.equity:.2f} {info.currency}")
    print(f"Symbol {ta.SYMBOL}, lot {ta.LOT}")
    print(f"Session config: MAX_MINUTES={ta.MAX_MINUTES}, SESSION_GAP={ta.SESSION_GAP}s")
    print(f"M5 trend: EMA{ta.EMA_FAST} vs EMA{ta.EMA_SLOW}")
    print("=" * 70)

    mt5.symbol_select(ta.SYMBOL, True)
    ta.close_stale_magic_positions()

    NUM_TEST_SESSIONS = 5
    outcomes = []

    try:
        for i in range(1, NUM_TEST_SESSIONS + 1):
            ta.SESSION_NUMBER = i
            outcome = ta.run_session()
            outcomes.append(outcome)
            ta.write_log(outcome, ta.LOG_LINES)
            print(f"--- Session {i} finished: {outcome} ---")
            if i < NUM_TEST_SESSIONS:
                print(f"Waiting {ta.SESSION_GAP}s before next session...")
                time.sleep(ta.SESSION_GAP)
    except KeyboardInterrupt:
        print("Interrupted by user.")
        ta.close_all_positions()
    finally:
        mt5.shutdown()
        print("=" * 70)
        print(f"Test complete. Ran {len(outcomes)} sessions.")
        print(f"Outcomes: {outcomes}")
        wins = outcomes.count("WIN")
        losses = outcomes.count("LOSS")
        times = outcomes.count("TIME")
        print(f"  WIN: {wins}  LOSS: {losses}  TIME: {times}")
        info = mt5.account_info()
        if info:
            print(f"Final equity: {info.equity:.2f} {info.currency}")


if __name__ == "__main__":
    main()
