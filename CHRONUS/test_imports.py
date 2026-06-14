import sys
print("1: importing torch...", flush=True)
import torch
print(f"2: torch {torch.__version__}, cuda={torch.cuda.is_available()}", flush=True)

print("3: importing transformers...", flush=True)
import transformers
print(f"4: transformers {transformers.__version__}", flush=True)

print("5: importing sentence_transformers...", flush=True)
import sentence_transformers
print(f"6: sentence_transformers {sentence_transformers.__version__}", flush=True)

print("7: importing SentenceTransformer...", flush=True)
from sentence_transformers import SentenceTransformer
print("8: all OK", flush=True)
