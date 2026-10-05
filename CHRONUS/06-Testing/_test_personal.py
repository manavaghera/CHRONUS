import requests

BASE = "http://127.0.0.1:8001"

for q in [
    "when were you born?",
    "where were you born?",
    "who is your mother?",
    "what did you study at university?",
    "tell me about your childhood",
    "where did you grow up?",
]:
    r = requests.post(f"{BASE}/chat", json={"query": q}, timeout=120)
    d = r.json()
    print(f"\nQ: {q!r}")
    print(f"  mode={d.get('mode')} conf={d.get('confidence')} srcs={len(d.get('sources', []))}")
    print(f"  A: {d.get('answer')}")