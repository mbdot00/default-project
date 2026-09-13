"""Consult the free AI review panel with the ACTUAL 40-session trade_auto.py
test results (win/loss bands, durations, direction mix)."""
import json
import os
import ssl
import time
import urllib.request
import urllib.error

KEY = os.environ.get("AI_API_KEY", "sk-WTbMvkka8Asv22ZJ4sDH8pwalDPA780O3y3TLAvyZBZPe6Q5Gf86lAaoe9XqLmDS")
URL = "https://opencode.ai/zen/v1/chat/completions"
CTX = ssl.create_default_context()


def digest():
    # Hard numbers from logs/session_results.csv (41 tracked sessions, 40 with WIN/LOSS outcome)
    return (
        "Strategy: on XM demo, JP225Cash (Nikkei 225 CFD), 0.1 lot. Script runs an infinite loop of "
        "sessions. Each session picks ONE direction from M5 EMA7-vs-EMA21 (bull->BUY, bear->SELL), then "
        "every 5s opens MORE 0.1 lot buys while the M1 candle is green (sell while red), STACKING positions. "
        "No per-trade stop/take-profit. Each session ends ONLY when total equity since session start falls "
        "-$1 (LOSS) or rises +$5 (WIN); then all positions are bulk-closed and it loops to the next session. "
        "Per-point P/L is tiny (~$0.005/pt at 0.1 lot) so equity moves very slowly.\n\n"
        "REAL TEST RESULTS (40 completed sessions, ~11.5 hours, today):\n"
        "- Total: 3 WINS, 33 LOSSES, 4/noted time-outs.\n"
        "- By direction: BUY sessions = 24 (2 win / 18 loss); SELL sessions = 18 (1 win / 15 loss).\n"
        "- Raw band P/L before spread/costs = +3*$5 - 33*$1 = -$18. After spreads (0.1 lot x17-40 opens/session) it is worse.\n"
        "- Average session duration for WIN/LOSS = ~15.5 min; LONG sessions dominate (many 20-77 min, one 77 min).\n"
        "- Loss ratio 92% (33/36 decisive sessions lost). No sign of separation between directions; most sessions bleed to -$1 rarely reaching +$5."
    )


QUESTIONS = {
    "edge": "Given these exact numbers (3W/33L, -$18 before spread), is the M5-trend-direction + stacking "
            "approach a real statistical edge or a coin-flip that loses to spread/slippage? Be blunt and quantitative.",
    "flaw": "Name the SINGLE most damaging design flaw visible in these 40 sessions and quantify how it erodes the edge.",
    "fix": "Give the top 3 highest-leverage changes that could give this a genuine positive expectancy. Be concrete, "
           "quantifiable, and realistic for a 0.1-lot micro-account. If the strategy is fundamentally bad, say so and give the best alternative.",
}


def call(model, question, digest_text, max_attempts=4, timeout=150):
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Expert futures/CFD trader and quant strategy reviewer. Honest, specific, quantitative. Critique, do not flatter. Answer in plain ASCII."},
            {"role": "user", "content": f"Trade evidence:\n{digest_text}\n\n" + question},
        ],
        "temperature": 0.3,
        "max_tokens": 1000,
    }
    req = urllib.request.Request(
        URL, data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {KEY}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
            "Accept": "application/json",
        },
        method="POST",
    )
    last = None
    for attempt in range(max_attempts):
        if attempt:
            time.sleep(10 + 6 * attempt)
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=CTX) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            last = e
            print(f"    (attempt {attempt + 1}: {e})", flush=True)
    if isinstance(last, (urllib.error.HTTPError,)):
        raise RuntimeError(f"HTTP {last.code}")
    raise RuntimeError(f"failed: {last}")


def main():
    models = ["laguna-s-2.1-free", "ling-3.0-flash-fin-free", "nemotron-3-ultra-free"]
    digest_text = digest()
    reports = {}
    for m in models:
        print(f"\n================= {m} =================", flush=True)
        reports[m] = {}
        for key, q in QUESTIONS.items():
            print(f"  -- {key} --", flush=True)
            try:
                out = call(m, q, digest_text)
            except Exception as e:
                out = f"[model error: {e}]"
                print(out, flush=True)
            reports[m][key] = out
            try:
                print(out, flush=True)
            except UnicodeEncodeError:
                print(out.encode("ascii", "replace").decode("ascii"), flush=True)
            time.sleep(4)
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "panel_review_40sessions.md"), "w", encoding="utf-8") as f:
        f.write("# Independent Free-Model Panel Review — 40 trade_auto Sessions\n\n")
        f.write("Evidence digest supplied to models:\n\n```\n" + digest_text + "\n```\n\n")
        for m in models:
            f.write(f"## {m}\n\n")
            for key, out in reports[m].items():
                f.write(f"### {key}\n\n{out}\n\n")


if __name__ == "__main__":
    main()