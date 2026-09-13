"""
ai_consult.py

Send your TRADE_JOURNAL.md + session_results.csv to a free AI model and get
strategy feedback. No SDK required - uses Python's standard urllib over HTTPS.

Prereq: a FREE API key. Two good free options:

  1. Groq      -> https://console.groq.com  (llama-3.3-70b-versatile, llama-3.1-8b-instant ... most are free)
  2. OpenRouter-> https://openrouter.ai      (models with a tag ":free", e.g. meta-llama/llama-3.3-70b-instruct:free)
  3. Google    -> https://aistudio.google.com (gemini-2.0-flash free tier)

Usage:
    set AI_PROVIDER=groq|openrouter|google   (default: groq)
    set AI_API_KEY=sk-...
    python ai_consult.py "ASK THE MODEL YOUR QUESTION HERE"
    python ai_consult.py --files my_extra_note.md -- "include this too"

Examples:
    python ai_consult.py "Does my buy-red/sell-green M1 scalp have an edge on JP225Cash, and when is it strongest?"
    python ai_consult.py "Review session_results.csv and tell me which hour won."
"""

import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
JOURNAL = os.path.join(HERE, "TRADE_JOURNAL.md")
CSV = os.path.join(HERE, "logs", "session_results.csv")


def read(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return f"[missing: {path}]"


def default_files():
    return [JOURNAL, CSV]


def http_json(url, headers, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def call_groq(api_key, system, user):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "temperature": 0.3,
    }
    data = http_json(url, headers, payload)
    return data["choices"][0]["message"]["content"]


def call_openrouter(api_key, system, user):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}",
               "Content-Type": "application/json",
               "HTTP-Referer": "https://localhost", "X-Title": "trade-consult"}
    payload = {
        "model": "meta-llama/llama-3.3-70b-instruct:free",
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "temperature": 0.3,
    }
    data = http_json(url, headers, payload)
    return data["choices"][0]["message"]["content"]


def call_google(api_key, system, user):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    payload = {"contents": [{"parts": [{"text": system + "\n\n" + user}]}]}
    data = http_json(url, {"Content-Type": "application/json"}, payload)
    return data["candidates"][0]["content"]["parts"][0]["text"]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    files = default_files()
    if "--files" in sys.argv:
        i = sys.argv.index("--files")
        files = [os.path.join(HERE, p) for p in sys.argv[i + 1:i + 4] if not p.startswith("--")]

    question = " ".join(args) if args else "Please review my trading strategy and give focused advice."

    provider = os.environ.get("AI_PROVIDER", "groq")
    api_key = os.environ.get("AI_API_KEY", "")
    if not api_key:
        print("No AI_API_KEY set. Insert a free key (see top of this script).")
        sys.exit(2)
    if provider == "google" and not api_key.isdigit() and "AIza" not in api_key:
        print("Note: Gemini keys usually start with AIza...")

    context = "\n\n".join(f"===== FILE: {p} =====\n{read(p)}" for p in files)

    system = (
        "You are an expert futures/CFD trader and strategy reviewer. "
        "Your job is to give honest, specific, data-driven feedback. "
        "Warn clearly about overfitting, spread costs, and risk of ruin. "
        "Be concise but concrete. Do not just encourage - critique and improve."
    )
    user = f"{context}\n\n===== QUESTION =====\n{question}"

    try:
        if provider == "openrouter":
            print(call_openrouter(api_key, system, user))
        elif provider == "google":
            print(call_google(api_key, system, user))
        else:
            print(call_groq(api_key, system, user))
    except Exception as e:
        print(f"ERROR calling {provider}: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()