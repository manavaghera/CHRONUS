"""CHRONUS Phase 6 Test Suite — runs tests 6.1-6.4, 6.6 against the live API
and 6.3 via direct classify_theme() calls."""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import chromadb
import requests

from config import config

BASE = f"http://{config.HOST}:{config.PORT}"
# These tests check Mix Method structure (verbatim Part 1 quote etc.), so pin
# the mode — the API default is "natural", which calls an external LLM.
MODE = "mix_method"
FALLBACK_MSG = "I don't have any documented information about that in my available records."

results = {}


def show(title, **kv):
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")
    for k, v in kv.items():
        print(f"  {k}: {v}")


# --- Test 6.1: High-confidence query ---
r = requests.post(f"{BASE}/chat", json={"query": "What is the goal of SpaceX?", "mode": MODE}, timeout=60)
d = r.json()
show("TEST 6.1: High-Confidence Query — 'What is the goal of SpaceX?'",
     status=r.status_code, confidence=d.get("confidence"), fallback=d.get("fallback"),
     faithfulness=d.get("faithfulness"),
     response_first_200=d["answer"][:200],
     n_sources=len(d.get("sources", [])),
     source0_citation=d["sources"][0].get("citation") if d.get("sources") else None)
p = (r.status_code == 200 and not d.get("fallback") and d.get("confidence") in ("high", "medium")
     and d.get("sources"))
results["6.1"] = "PASS" if p else "FAIL"

# --- Test 6.2: Low-confidence fallback ---
# A clearly unanswerable question (best match 0.70 vs threshold 0.58). The
# original pizza question sits in the calibrated grey zone (0.51: he tweets
# about food) and is answered with medium confidence; see evaluation/run_eval.py.
# This script needs a live server; tests/test_api.py runs the same checks without one.
r = requests.post(f"{BASE}/chat", json={"query": "How do I descale a kettle?", "mode": MODE}, timeout=60)
d = r.json()
exact = d.get("answer") == FALLBACK_MSG
show("TEST 6.2: Low-Confidence Fallback — 'How do I descale a kettle?'",
     status=r.status_code, answer=d.get("answer"), exact_match=exact,
     fallback=d.get("fallback"), confidence=d.get("confidence"),
     sources_count=len(d.get("sources", [])))
p = (r.status_code == 200 and d.get("fallback") is True and d.get("confidence") == "low"
     and exact and len(d.get("sources", [])) == 0)
results["6.2"] = "PASS" if p else "FAIL"

# --- Test 6.3: Theme classification (direct classify_theme calls) ---
from services.theme_classifier import classify_theme

theme_cases = [
    ("Tell me about your kids", "love_relationships"),
    ("What's the mission of Tesla?", "work_purpose"),
    ("What scares you the most?", "fear_resilience"),
    ("What is the meaning of life?", "meaning"),
    ("What was your biggest mistake?", "failure_growth"),
    ("Why did you buy Twitter?", "change_decisions"),
    ("Will humanity survive?", "humanity_society"),
]
theme_hits = 0
show("TEST 6.3: Theme Classification (direct classify_theme)")
for q, expected in theme_cases:
    actual = classify_theme(q)["theme"]
    ok = actual == expected
    theme_hits += ok
    print(f"  {'MATCH   ' if ok else 'MISMATCH'} | {q!r}: expected={expected}, actual={actual}")
results["6.3"] = f"{theme_hits}/7"

# --- Test 6.4: Source provenance ---
r = requests.post(f"{BASE}/chat", json={"query": "What do you think about artificial intelligence?", "mode": MODE}, timeout=60)
d = r.json()
srcs = d.get("sources", [])
s0 = srcs[0] if srcs else {}


def _norm(text):
    return re.sub(r"\s+", " ", text).strip().lower()


# Part 1 quotes sources[0]: check the quoted text against the FULL memory
# (looked up by memory_id), not the 150-char preview returned in the API.
part1 = d.get("answer", "").split("\n\n")[0]
part1_quote = part1[part1.find('"') + 1: part1.rfind('"')].rstrip("…") if part1.count('"') >= 2 else ""
full_doc = ""
if s0.get("memory_id"):
    got = chromadb.PersistentClient(path=config.CHROMA_PATH).get_collection(config.COLLECTION_NAME).get(
        ids=[s0["memory_id"]])
    full_doc = got["documents"][0] if got["documents"] else ""
checks = {
    "sources not empty": bool(srcs),
    "source[0].citation present": bool(s0.get("citation")),
    "source[0].quote present": bool(s0.get("quote")),
    "source[0].source_type present": bool(s0.get("source_type")),
    "source[0].source_file present": bool(s0.get("source_file")),
    "source[0].voice/memory_id/distance present": all(s0.get(k) is not None for k in ("voice", "memory_id", "distance")),
    "Part 1 quote is verbatim from source[0]": bool(part1_quote) and _norm(part1_quote) in _norm(full_doc),
}
show("TEST 6.4: Source Provenance — 'What do you think about artificial intelligence?'",
     status=r.status_code,
     source0=json.dumps(s0, ensure_ascii=False)[:400],
     **{k.replace(" ", "_"): v for k, v in checks.items()})
p = all(checks.values())
results["6.4"] = "PASS" if p else "FAIL"

# --- Test 6.6: Interview responses in retrieval ---
r = requests.post(f"{BASE}/chat", json={"query": "How would you describe your personality?", "mode": MODE}, timeout=60)
d = r.json()
interview_srcs = [s for s in d.get("sources", []) if s.get("source_type") == "interview_protocol"]
show("TEST 6.6: Interview Retrieval — 'How would you describe your personality?'",
     status=r.status_code, confidence=d.get("confidence"), fallback=d.get("fallback"),
     interview_sources_found=len(interview_srcs),
     response_first_200=d["answer"][:200],
     all_source_types=[s.get("source_type") for s in d.get("sources", [])])
p = bool(interview_srcs) and d.get("confidence") in ("medium", "high")
results["6.6"] = "PASS" if p else "FAIL"

print(f"\n{'=' * 60}\nSUMMARY\n{'=' * 60}")
for k, v in results.items():
    print(f"  Test {k}: {v}")
