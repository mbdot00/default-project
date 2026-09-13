"""Compact consultation: send a SHORT digested summary of the MT5 strategy to
multiple free OpenCode Zen models and collect independent reviews.
Small payloads get through the flaky free gateway much more reliably."""
import json
import os
import re
import ssl
import time
import urllib.request

KEY = os.environ.get("AI_API_KEY", "sk-WTbMvkka8Asv22ZJ4sDH8pwalDPA780O3y3TLAvyZBZPe6Q5Gf86lAaoe9XqLmDS")
URL = "https://opencode.ai/zen/v1/chat/completions"
HERE = os.path.dirname(os.path.abspath(__file__))

CTX = ssl.create_default_context()


def read(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def digest():
    """Extract the hard facts from the two losing logs into a short summary."""
    facts = []
    for log, side, n, trend, pnl in [
        ("trade_sell_green_20260902_120814_01h02m48s_LOSS.log", "SELL", 33, "UPTREND (Nikkei rose ~64,247 -> ~64,340)", "lose $1.34"),
        ("trade_buy_red_20260902_135312_00h29m47s_LOSS.log", "BUY", 19, "DOWNTREND (Nikkei fell ~64,462 -> ~64,298)", "lose $1.24"),
    ]:
        txt = read(os.path.join(HERE, "logs", log))
        opens = len(re.findall(r"open (BUY|SELL)", txt))
        stop = "hit -$1 stop-loss (equity band)" if "STOP" in txt else "no stop hit"
        facts.append(
            f"- {side}-per-candle session, 63 min on JP225Cash (Nikkei 225) at 0.1 lot: "
            f"opened {opens} positions ALL STACKED, went {stop}, net {pnl}, exited by bulk-closing all. "
            f"Market was in a {trend} all session."
        )
    summary = "\n".join(facts)
    summary += (
        "\n- Strategy rule: buy near EVERY RED M1 candle, or sell near EVERY GREEN M1 candle at :57, "
        "stack all positions, NO per-trade stop/take-profit; only bulk-close all when total equity "
        "moves -$1 (loss) or +$5 (win) from session start. Account is a demo, trade.P/L per point is "
        "tiny (~$0.005/pt) so positions must run far to move equity."
    )
    return summary


QUESTIONS = {
    "edge": "Is this 'trade every same-colored M1 candle and stack' a real statistical edge or a coin-flip "
            "that only wins on lucky trend days? Use the numbers. Be blunt and specific.",
    "flaw": "Name the single most damaging design flaw visible in these sessions and why it loses money.",
    "fix": "Give the top 3 highest-leverage changes to give it a genuine positive edge. Be concrete and quantifiable.",
}


def call(model, question, digest_text, max_attempts=4, timeout=120):
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Expert futures/CFD trader and quant strategy reviewer. Honest, specific, quantitative. Critique, do not flatter. Answer in plain ASCII."},
            {"role": "user", "content": f"Trade evidence:\n{digest_text}\n\n" + question},
        ],
        "temperature": 0.3,
        "max_tokens": 900,
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
            time.sleep(8 + 6 * attempt)
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=CTX) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            last = e
            print(f"    (attempt {attempt + 1}: {e})")
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
            out = call(m, q, digest_text)
            reports[m][key] = out
            try:
                print(out, flush=True)
            except UnicodeEncodeError:
                print(out.encode("ascii", "replace").decode("ascii"), flush=True)
            time.sleep(4)
    with open(os.path.join(HERE, "free_model_reviews.md"), "w", encoding="utf-8") as f:
        f.write("# Independent Free-Model Strategy Reviews\n\n")
        for m in models:
            f.write(f"## {m}\n\n")
            for key, out in reports[m].items():
                f.write(f"### {key}\n\n{out}\n\n")


if __name__ == "__main__":
    main()