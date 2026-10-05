import sys
print("starting...", flush=True)
from sentence_transformers import SentenceTransformer
print("imported", flush=True)
model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
print("loaded", flush=True)
emb = model.encode(["hello"])
print(f"shape: {emb.shape}", flush=True)
print("DONE", flush=True)
