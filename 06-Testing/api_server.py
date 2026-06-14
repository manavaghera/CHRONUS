"""CHRONUS API - FastAPI server with API key auth + auto-train memory."""

import json, os, hashlib, sys
from datetime import datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import chromadb, requests
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
from elon_few_shot import few_shot_block
from post_process import scrub

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3:8b-instruct-q4_0"
API_KEY = os.getenv("CHRONUS_API_KEY", "chronus-demo-key-2026")
LOG_PATH = Path("06-Testing/qa_memory.jsonl")
CACHE_SIMILARITY = 0.92

identity_card_text = Path("03-Identity-Card/elon_musk.json").read_text(encoding="utf-8")
client_db = chromadb.PersistentClient(path="chroma_db")
collection = client_db.get_collection("elon_musk")
embedder = SentenceTransformer("all-MiniLM-L6-v2")

app = FastAPI(title="CHRONUS - Elon Musk API", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key

class ChatRequest(BaseModel):
    query: str

def retrieve(query, n=5):
    q_emb = embedder.encode([query], normalize_embeddings=True).tolist()
    raw = collection.query(query_embeddings=q_emb, n_results=n * 4)
    docs, metas, dists = raw["documents"][0], raw["metadatas"][0], raw["distances"][0]
    scored = []
    for doc, meta, dist in zip(docs, metas, dists):
        imp = meta.get("importance_score", 1)
        adjusted = dist - (imp * 0.15)
        scored.append((adjusted, doc, meta, dist))
    scored.sort(key=lambda x: x[0])
    return scored[:n]

def check_cache(query):
    if not LOG_PATH.exists():
        return None
    past = [json.loads(l) for l in LOG_PATH.open(encoding="utf-8", errors="ignore") if l.strip()]
    if not past:
        return None
    past_embs = embedder.encode([p["query"] for p in past], normalize_embeddings=True)
    q_emb = embedder.encode([query], normalize_embeddings=True)
    sims = (past_embs @ q_emb.T).flatten()
    best = int(sims.argmax())
    if sims[best] > CACHE_SIMILARITY:
        return past[best]
    return None

def add_to_memory(query, answer):
    """Auto-train: add Q&A pair to ChromaDB as a permanent memory unit."""
    qa_text = f"Q: {query}\nA: {answer}"
    qa_emb = embedder.encode([qa_text], normalize_embeddings=True).tolist()
    qa_id = "qa_" + hashlib.md5(qa_text.encode()).hexdigest()[:12]
    try:
        collection.add(
            embeddings=qa_emb, documents=[qa_text],
            metadatas=[{"source_file": "auto_trained_qa", "source_type": "auto_trained",
                        "importance_score": 3, "person": "elon_musk",
                        "date": datetime.now().isoformat()}],
            ids=[qa_id],
        )
        return True
    except Exception as e:
        print(f"Auto-train: {e}")
        return False

def log_qa(query, answer, sources):
    LOG_PATH.parent.mkdir(exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"query": query, "answer": answer,
                            "sources": [s["source_file"] for s in sources],
                            "timestamp": datetime.now().isoformat()}) + "\n")

def build_prompt(query, memories):
    memory_block = "\n\n".join(
        f"[{i+1}] (Source: {meta['source_file']})\n{doc}"
        for i, (_, doc, meta, _) in enumerate(memories)
    )
    return f"""You ARE Elon Musk on a podcast, answering live. Off the cuff, not scripted.

=== IDENTITY CARD ===
{identity_card_text}
{few_shot_block()}

=== RELEVANT MEMORIES ===
{memory_block}

=== HOW ELON TALKS ===
Short punchy sentences. "Look,", "Honestly,", "Frankly,", "Yeah,", "I mean," openers.
Contractions always. Dry dark humor. First-principles. Specific numbers/companies.
"Pain in the ass", "extremely", "obviously", "fundamentally" peppered in.

=== RULES ===
MAX 4 sentences. No filler. Use MEMORIES as basis. If memories don't cover: "Honestly, I haven't publicly talked about that" - never invent.
NEVER: delve, leverage, robust, moreover, furthermore, in conclusion, it's worth noting, navigate, paradigm, holistic, synergy.
NEVER: bullet points, lists, headers, JSON, break character, mention AI.

=== HOST ASKED ===
{query}

=== RESPOND AS ELON, OFF THE CUFF ==="""

@app.get("/")
def root():
    return {"service": "CHRONUS - Elon Musk API", "endpoints": ["/chat", "/personas"], "auth": "X-API-Key header"}

@app.get("/personas")
def personas():
    return {"personas": ["elon_musk"], "active": "elon_musk"}

@app.post("/chat")
def chat(req: ChatRequest, _: str = Depends(verify_api_key)):
    cached = check_cache(req.query)
    if cached:
        return {"answer": cached["answer"], "sources": cached["sources"], "cached": True}
    memories = retrieve(req.query)
    prompt = build_prompt(req.query, memories)
    response = requests.post(OLLAMA_URL, json={
        "model": MODEL, "prompt": prompt, "stream": False,
        "options": {"temperature": 0.85, "num_ctx": 8192, "num_predict": 200},
    }, timeout=300)
    response.raise_for_status()
    answer = scrub(response.json()["response"])
    sources = [{"source_file": m["source_file"], "type": m["source_type"]} for _, _, m, _ in memories]
    log_qa(req.query, answer, sources)
    add_to_memory(req.query, answer)
    return {"answer": answer, "sources": sources, "cached": False}

if __name__ == "__main__":
    import uvicorn
    print(f"CHRONUS API on http://localhost:8000  |  API key: {API_KEY}")
    uvicorn.run(app, host="0.0.0.0", port=8000)
