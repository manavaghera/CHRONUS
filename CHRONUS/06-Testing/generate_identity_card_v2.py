"""
Generate Elon Musk's identity card (v2 - bulletproof).
Output: 03-Identity-Card/elon_musk.json
"""

import json
import re
import random
import requests
from pathlib import Path

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3:8b-instruct-q4_0"
SAMPLE_SIZE = 60

# --- Load memory units ---
records = []
with open("04-Memory-Units/elon_musk_memory_units.jsonl", encoding="utf-8") as f:
    for line in f:
        records.append(json.loads(line))

quality = [
    r for r in records
    if r.get("source_type") in ("interview", "book")
    and r.get("importance_score", 1) >= 3
    and len(r.get("text", "")) > 200
]
print(f"High-quality long-form units: {len(quality)}")

random.seed(42)
sample = random.sample(quality, min(SAMPLE_SIZE, len(quality)))
print(f"Sampled {len(sample)} passages\n")

# --- Build context (truncate each passage to keep prompt manageable) ---
context_parts = []
for r in sample:
    txt = r["text"].strip()[:400]  # cap each passage at 400 chars
    context_parts.append(f"[{r['source_file']}]\n{txt}")
context = "\n---\n".join(context_parts)

# --- Simpler, flatter prompt the model can actually produce ---
prompt = f"""Analyze these passages from Elon Musk's verified archive. Extract his personality.

Return ONLY a JSON object (no prose, no markdown). Use this flat structure:

{{
  "name": "Elon Musk",
  "one_line_summary": "<one sentence capturing who he is>",
  "communication": {{
    "formality": "<short phrase>",
    "sentence_length": "<short phrase>",
    "humor": "<short phrase>",
    "vocabulary": "<short phrase>",
    "patterns": ["pattern1", "pattern2", "pattern3"]
  }},
  "top_beliefs": [
    "belief 1 in his own words",
    "belief 2 in his own words",
    "belief 3 in his own words",
    "belief 4 in his own words",
    "belief 5 in his own words",
    "belief 6 in his own words",
    "belief 7 in his own words",
    "belief 8 in his own words"
  ],
  "signature_phrases": [
    "phrase 1",
    "phrase 2",
    "phrase 3",
    "phrase 4",
    "phrase 5"
  ],
  "emotional_responses": {{
    "excitement": "<one short phrase>",
    "criticism": "<one short phrase>",
    "failure": "<one short phrase>",
    "disagreement": "<one short phrase>"
  }},
  "thinking": {{
    "reasoning": "<one short phrase>",
    "decisions": "<one short phrase>",
    "worldview": "<one short phrase>"
  }}
}}

PASSAGES:

{context}

Return ONLY the JSON."""

# --- Call Ollama with JSON mode ---
print(f"Calling {MODEL}...")
r = requests.post(
    OLLAMA_URL,
    json={
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.2,
            "num_ctx": 8192,
        },
    },
    timeout=600,
)
r.raise_for_status()
raw = r.json()["response"]

# Save raw for debugging (always)
debug_path = Path("03-Identity-Card/last_raw_response.txt")
debug_path.parent.mkdir(exist_ok=True)
debug_path.write_text(raw)
print(f"Raw response saved to {debug_path} ({len(raw)} chars)")

# --- Multi-strategy parser ---
def parse_llm_json(raw: str) -> dict:
    text = raw.strip()

    # Strip markdown code fences
    if "```" in text:
        m = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if m:
            text = m.group(1).strip()

    # Find balanced JSON object (skip braces in strings)
    start = text.find("{")
    if start == -1:
        return _raw_to_dict_fallback(raw)

    depth = 0
    end = -1
    in_string = False
    escape = False
    for i, c in enumerate(text[start:], start):
        if escape:
            escape = False
            continue
        if c == "\\" and in_string:
            escape = True
            continue
        if c == '"' and not escape:
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                end = i
                break

    if end != -1:
        text = text[start:end + 1]

    # Try direct parse
    for attempt in [text, re.sub(r",(\s*[}\]])", r"\1", text)]:
        try:
            return json.loads(attempt)
        except json.JSONDecodeError:
            continue

    # Last resort: key-value extraction
    return _raw_to_dict_fallback(raw)


def _raw_to_dict_fallback(raw: str) -> dict:
    """Extract key-value pairs from malformed JSON using regex on quoted strings."""
    print("WARNING: Falling back to regex extraction")
    out = {}
    # Match "key": "value" or "key": [...]
    for m in re.finditer(r'"([^"]+)":\s*"([^"]*)"', raw):
        out[m.group(1)] = m.group(2)
    for m in re.finditer(r'"([^"]+)":\s*\[([^\]]*)\]', raw):
        items = re.findall(r'"([^"]+)"', m.group(2))
        out[m.group(1)] = items
    return out


card = parse_llm_json(raw)

if not card:
    raise ValueError(f"Could not extract any data. See {debug_path}")

# --- Save ---
out_path = Path("03-Identity-Card/elon_musk.json")
out_path.parent.mkdir(exist_ok=True)
out_path.write_text(json.dumps(card, indent=2, ensure_ascii=False))

print(f"\n{'='*60}")
print(f"IDENTITY CARD SAVED: {out_path}")
print(f"{'='*60}")
print(f"Keys extracted: {list(card.keys())}")
print(f"Top beliefs: {len(card.get('top_beliefs', []))}")
print(f"Signature phrases: {len(card.get('signature_phrases', []))}")
print(f"\nFirst 3 beliefs:")
for b in (card.get("top_beliefs", []) or [])[:3]:
    print(f"  - {b}")
print(f"\nSignature phrases: {card.get('signature_phrases', [])}")
