import sys
print("1: torch...", flush=True)
import torch
print(f"2: torch {torch.__version__}, cuda={torch.cuda.is_available()}", flush=True)

print("3: chromadb...", flush=True)
import chromadb
print("4: chromadb OK", flush=True)

print("5: SentenceTransformer...", flush=True)
from sentence_transformers import SentenceTransformer
print("6: SentenceTransformer imported", flush=True)

print("7: loading model...", flush=True)
m = SentenceTransformer("all-MiniLM-L6-v2")
print("8: model loaded", flush=True)

print("9: encoding test...", flush=True)
emb = m.encode(["test"], normalize_embeddings=True)
print(f"10: embedding shape={emb.shape}", flush=True)

print("ALL PASSED", flush=True)
