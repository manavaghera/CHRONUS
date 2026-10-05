"""Test natural response mode vs mix_method mode."""
import json
import requests

BASE = "http://127.0.0.1:8000"

def ask(query, mode=None):
    payload = {"query": query}
    if mode:
        payload["mode"] = mode
    r = requests.post(f"{BASE}/chat", json=payload, timeout=300)
    d = r.json()
    print(f"\n{'=' * 60}")
    print(f"QUERY: {query!r}  (mode sent: {mode or 'default'})")
    print(f"STATUS: {r.status_code}")
    print(f"MODE: {d.get('mode')}  CONFIDENCE: {d.get('confidence')}  FALLBACK: {d.get('fallback')}")
    print(f"SOURCES: {len(d.get('sources', []))}")
    if d.get("sources"):
        print(f"SOURCE[0]: {json.dumps(d['sources'][0], ensure_ascii=False)[:200]}")
    print(f"ANSWER:\n{d.get('answer')}")

ask("What is the goal of SpaceX?")                       # natural (default)
ask("What is the goal of SpaceX?", mode="mix_method")    # explicit template mode
ask("What do you think about artificial intelligence?")  # natural, second sample
