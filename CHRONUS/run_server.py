import os
os.chdir(r"C:\Users\manav\OneDrive\Desktop\CHRONUS DB\CHRONUS")
import sys
sys.path.insert(0, r"C:\Users\manav\OneDrive\Desktop\CHRONUS DB\CHRONUS")
print("1: torch...", flush=True)
import torch
print(f"2: torch OK, cuda={torch.cuda.is_available()}", flush=True)
print("3: chromadb...", flush=True)
import chromadb
print("4: chromadb OK", flush=True)
print("5: SentenceTransformer import...", flush=True)
from sentence_transformers import SentenceTransformer
print("6: import OK", flush=True)
print("7: model load...", flush=True)
embedder = SentenceTransformer("all-MiniLM-L6-v2")
print("8: model OK", flush=True)
print("9: elon_few_shot...", flush=True)
sys.path.insert(0, str(os.path.join(os.getcwd(), "06-Testing")))
from elon_few_shot import few_shot_block
print("10: few_shot OK", flush=True)
print("11: post_process...", flush=True)
from post_process import scrub
print("12: scrub OK", flush=True)
print("13: api_server...", flush=True)
import api_server
print("14: api_server OK", flush=True)
import uvicorn
print("15: starting uvicorn...", flush=True)
uvicorn.run(api_server.app, host="0.0.0.0", port=8000)
