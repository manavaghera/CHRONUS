"""
Generate Elon Musk's identity card by analyzing his actual archive with Llama 3.
Output: 03-Identity-Card/elon_musk.json
"""

import json
import re
import random
import requests
from pathlib import Path

# ---------- CONFIG ----------
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3:8b-instruct-q4_0"
SAMPLE_SIZE = 80
RANDOM_SEED = 42
# ----------------------------

# Load all memory units
records = []
with open("04-Memory-Units/elon_musk_memory_units.jsonl", encoding="utf-8") as f:
    for line in f:
        records.append(json.loads(line))

# Filter to high-quality long-form content (interviews + books, importance >= 3)
quality = [
    r for r in records
    if r.get("source_type") in ("interview", "book")
    and r.get("importance_score", 1) >= 3
    and len(r.get("text", "")) > 200
]
print(f"High-quality long-form units available: {len(quality)}")

# Sample
random.seed(RANDOM_SEED)
sample = random.sample(quality, min(SAMPLE_SIZE, len(quality)))
print(f"Sampled {len(sample)} passages for analysis\n")

# Build context block
context_parts = []
for r in sample:
    src = r.get("source_file", "unknown")
    txt = r["text"].strip()
    context_parts.append(f"[SOURCE: {src}]\n{txt}")
context = "\n\n---\n\n".join(context_parts)

# The prompt
prompt = f"""You are an expert personality analyst. Below are {len(sample)} passages sampled from Elon Musk's verified archive (interviews, podcasts, books). Your job is to extract his cognitive fingerprint.

Analyze ONLY the evidence provided. Do not invent traits. Be specific. Use his actual words as evidence.

Return ONLY a valid JSON object with this exact structure. No prose, no markdown code fences, no explanation outside the JSON.

{{
  "name": "Elon Musk",
  "communication_style": {{
    "formality": "<one short phrase>",
    "sentence_length": "<one short phrase>",
    "vocabulary_level": "<one short phrase>",
    "humor_type": "<one short phrase>",
    "explanation_style": "<one short phrase>",
    "common_patterns": ["<pattern 1>", "<pattern 2>", "<pattern 3>"]
  }},
  "core_beliefs": [
    {{ "belief": "<statement>", "passion": "high|medium|low", "evidence": "<short quote or paraphrase>" }},
    ... (8 to 12 beliefs, ranked from most to least central)
  ],
  "signature_phrases": ["<phrase 1>", "<phrase 2>", "<phrase 3>", "<phrase 4>", "<phrase 5>"],
  "emotional_patterns": {{
    "excitement": "<how he sounds when excited>",
    "criticism": "<how he handles criticism>",
    "failure": "<how he talks about failure>",
    "disagreement": "<how he handles disagreement>"
  }},
  "thinking_style": {{
    "reasoning_approach": "<how he reasons through problems>",
    "decision_making": "<how he makes decisions>",
    "worldview": "<his core worldview>"
  }},
  "knowledge_boundaries": "<topics where his archive is sparse or silent>"
}}

ARCHIVE PASSAGES:

{context}

Return ONLY the JSON object."""

# Call Ollama
print(f"Calling {MODEL} via Ollama (this takes 1-3 minutes)...\n")
response = requests.post(
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
response.raise_for_status()
raw = response.json()["response"]

# Extract the first valid JSON object even if Ollama adds extra prose.
start = raw.find("{")
if start == -1:
    raise ValueError(f"No JSON found in response. First 500 chars:\n{raw[:500]}")

decoder = json.JSONDecoder()
try:
    card, _ = decoder.raw_decode(raw[start:])
except json.JSONDecodeError:
    cleaned = raw[start:].replace(",\n}", "\n}").replace(",\n]", "\n]")
    card, _ = decoder.raw_decode(cleaned)

# Validate structure
required = ["communication_style", "core_beliefs", "signature_phrases", "emotional_patterns", "thinking_style"]
for key in required:
    if key not in card:
        raise ValueError(f"Identity card missing required key: {key}")

# Save
out_path = Path("03-Identity-Card/elon_musk.json")
out_path.parent.mkdir(exist_ok=True)
out_path.write_text(json.dumps(card, indent=2, ensure_ascii=False))

print(f"\n{'='*60}")
print(f"IDENTITY CARD SAVED: {out_path}")
print(f"{'='*60}\n")
print(f"Beliefs extracted: {len(card.get('core_beliefs', []))}")
print(f"Signature phrases: {len(card.get('signature_phrases', []))}")
print(f"\nFirst 3 beliefs:")
for b in card.get("core_beliefs", [])[:3]:
    print(f"  - [{b.get('passion', '?')}] {b.get('belief', '')}")
print(f"\nSignature phrases: {card.get('signature_phrases', [])}")
