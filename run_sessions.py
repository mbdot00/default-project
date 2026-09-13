"""
run_sessions.py

Launch multiple capped trading sessions in sequence to test running the
buy-red / sell-green strategy multiple times per day.

Each session runs the chosen script as a subprocess. Because each script now
has a MAX_MINUTES time-cap, it is guaranteed to terminate (WIN, LOSS, or TIME),
so this runner can fire session after session and record per-session results.

Usage:
    python run_sessions.py --script trade_buy_trend  --sessions 4 --gap 60 --max-min 30
    python run_sessions.py --script trade_sell_trend --sessions 3 --gap 30 --max-min 20
"""

import argparse
import datetime
import os
import subprocess
import sys
import time

PY = r"C:\Users\x\AppData\Local\Programs\Python\Python312\python.exe"
HERE = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(HERE, "logs")
RESULTS_LOG = os.path.join(LOG_DIR, "session_results.csv")


def parse_args():
    p = argparse.ArgumentParser(description="Run multiple MT5 trading sessions in sequence.")
    p.add_argument("--script", required=True, choices=["trade_buy_trend", "trade_sell_trend"])
    p.add_argument("--sessions", type=int, default=4, help="number of back-to-back sessions")
    p.add_argument("--gap", type=int, default=60, help="seconds to wait between sessions")
    p.add_argument("--max-min", type=int, default=30, help="per-session max minutes (override)")
    return p.parse_args()


def ts():
    return datetime.datetime.now().strftime("%H:%M:%S")


def log(msg):
    print(f"[{ts()}] {msg}", flush=True)


def main():
    args = parse_args()
    script = args.script
    py_file = os.path.join(HERE, f"{script}.py")

    for i in range(1, args.sessions + 1):
        start_time = datetime.datetime.now()
        log(f"=== Session {i}/{args.sessions} ({script}) starting ===")

        cmd = [PY, py_file]
        env = os.environ.copy()
        if args.max_min:
            env["MT_MAX_MINUTES"] = str(args.max_min)

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding="utf-8", errors="replace",
                                env=env)
        output, _ = proc.communicate()

        end_time = datetime.datetime.now()
        duration = (end_time - start_time).total_seconds()

        # Determine outcome from the script's stdout (the last relevant marker)
        outcome = "UNKNOWN"
        tail = output.splitlines()
        for line in reversed(tail):
            low = line.lower()
            if "time stop:" in low:
                outcome = "TIME"
                break
            if "outcome" in low and ":" in low:
                outcome = line.split(":", 1)[-1].strip()
                break
            if "stop:" in low:
                outcome = "WIN" if ">=" in low else "LOSS"
                break

        log(f"=== Session {i} finished in {duration:.0f}s -> outcome [{outcome}] ===")

        # write result row
        row = ",".join([
            start_time.strftime("%Y-%m-%d %H:%M:%S"),
            f"{duration:.0f}",
            script,
            outcome,
        ])
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(RESULTS_LOG, "a", encoding="utf-8") as f:
            f.write(row + "\n")

        # print the tail of the session output for quick review
        print("  --- last lines from session ---")
        for line in tail[-8:]:
            print("   ", line)

        if i < args.sessions:
            log(f"waiting {args.gap}s before next session...")
            time.sleep(args.gap)

    log(f"Done. Results appended to {RESULTS_LOG}")
    if os.path.exists(RESULTS_LOG):
        with open(RESULTS_LOG, encoding="utf-8") as f:
            content = f.read()
        log("CSV so far:")
        sys.stdout.write(content.encode("ascii", "replace").decode("ascii") + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()