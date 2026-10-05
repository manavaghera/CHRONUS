"""Quick system health check for CHRONUS"""
import os, sys
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.getcwd(), "06-Testing"))

print("Step 1: imports...", flush=True)
import json, chromadb, requests
from pathlib import Path

print("Step 2: torch...", flush=True)
import torch
print(f"  torch OK, cuda={torch.cuda.is_available()}", flush=True)

print("Step 3: sentence_transformers...", flush=True)
from sentence_transformers import SentenceTransformer
print("  import OK", flush=True)

print("Step 4: loading model (CPU)...", flush=True)
model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
print("  model loaded", flush=True)

from elon_few_shot import few_shot_block
from post_process import scrub
print("  elon imports OK", flush=True)

print("Step 5: identity card...", flush=True)
identity_card_text = Path("03-Identity-Card/elon_musk.json").read_text(encoding="utf-8")
print(f"  loaded ({len(identity_card_text)} chars)", flush=True)

print("Step 6: ChromaDB...", flush=True)
client = chromadb.PersistentClient(path="chroma_db")
collection = client.get_collection("elon_musk")
print(f"  {collection.count():,} units", flush=True)

print("Step 7: test encode...", flush=True)
q_emb = model.encode(["test query"], normalize_embeddings=True).tolist()
print(f"  embedding OK ({len(q_emb[0])} dims)", flush=True)

print("Step 8: test retrieve...", flush=True)
raw = collection.query(query_embeddings=q_emb, n_results=5)
print(f"  retrieval OK ({len(raw['documents'][0])} docs)", flush=True)

print("Step 9: test Ollama...", flush=True)
resp = requests.post(
    "http://localhost:11434/api/generate",
    json={"model": "llama3:8b-instruct-q4_0", "prompt": "Say hello in 5 words", "stream": False, "options": {"num_predict": 20}},
    timeout=60,
)
print(f"  Ollama OK: {resp.json()['response'][:80]}", flush=True)

print("\n=== ALL SYSTEMS GO ===", flush=True)
