#!/usr/bin/env python3
"""
CHRONUS - FastAPI Server with Auto-Training
Every Q&A pair gets added back to ChromaDB as a memory unit.
Future similar questions retrieve it — the system gets smarter with each conversation.
"""

import hashlib
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import chromadb
import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

# ---- Imports from 06-Testing ----
sys.path.insert(0, str(Path(__file__).parent / "06-Testing"))
from elon_few_shot import few_shot_block
from post_process import scrub

# ---- Logging ----
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("chronus")

# ---- Config ----
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3:8b-instruct-q4_0"
COLLECTION_NAME = "elon_musk"
CHROMA_PATH = "chroma_db"
N_RESULTS = 5
IMPORTANCE_WEIGHT = 0.15
DISTANCE_THRESHOLD = 1.45

# ---- FastAPI ----
app = FastAPI(title="CHRONUS API", version="1.0.0")

# ---- Connect to ChromaDB ----
client = chromadb.PersistentClient(path=CHROMA_PATH)
try:
    collection = client.get_collection(COLLECTION_NAME)
    print(f"[OK] Loaded existing collection '{COLLECTION_NAME}' with {collection.count():,} memory units")
except Exception:
    collection = client.create_collection(name=COLLECTION_NAME, metadata={"hnsw:space": "cosine"})
    print(f"[WARN] Created NEW empty collection '{COLLECTION_NAME}'. Run: python 06-Testing/embed_elon.py to populate memories.")

# ---- Load embedding model ----
logger.info("Loading embedding model...")
embedder = SentenceTransformer("all-MiniLM-L6-v2")
logger.info("Embedding model loaded.")

# ---- Identity card base directory ----
IDENTITY_CARD_DIR = Path(__file__).parent / "03-Identity-Card"


def load_identity_card(person: str = "elon_musk") -> dict | None:
    """Load identity card JSON for the given person. Returns None if missing."""
    path = IDENTITY_CARD_DIR / f"{person}.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        logger.info(f"Loaded identity card for '{data.get('name', person)}' from {path}")
        return data
    except FileNotFoundError:
        print(f"WARNING: Identity card not found at {path} — using fallback prompt")
        return None
    except json.JSONDecodeError as e:
        print(f"WARNING: Malformed identity card at {path}: {e}")
        return None


identity_card = load_identity_card()


# ---- Request/Response models ----
class ChatRequest(BaseModel):
    query: str
    n_results: Optional[int] = N_RESULTS


class ChatResponse(BaseModel):
    answer: str
    sources: list[dict]
    faithfulness: float
    auto_trained: bool
    collection_size: int


class SpeakRequest(BaseModel):
    text: str
    speaker_wav: str


# ---- Core functions ----
def retrieve(query: str, n: int = N_RESULTS) -> list[tuple]:
    """Retrieve top-K memories with importance bias."""
    q_emb = embedder.encode([query], normalize_embeddings=True).tolist()
    raw = collection.query(query_embeddings=q_emb, n_results=n * 4)
    docs = raw["documents"][0]
    metas = raw["metadatas"][0]
    dists = raw["distances"][0]

    scored = []
    for doc, meta, dist in zip(docs, metas, dists):
        imp = meta.get("importance_score", 1)
        adjusted = dist - (imp * IMPORTANCE_WEIGHT)
        scored.append((adjusted, doc, meta, dist))
    scored.sort(key=lambda x: x[0])
    return scored[:n]


def build_system_prompt(identity_card: dict | None, memories: list[tuple], user_question: str) -> str:
    """Build the full system prompt dynamically from the identity card and memories."""

    # --- MEMORY BLOCK (only memories within distance threshold) ---
    filtered = [(adj, doc, meta, dist) for adj, doc, meta, dist in memories if dist <= DISTANCE_THRESHOLD]
    if not filtered and memories:
        filtered = memories[:1]

    memory_lines = []
    for i, (_, doc, meta, _) in enumerate(filtered):
        memory_lines.append(
            f"[{i+1}] (Source: {meta['source_file']}, type: {meta['source_type']})\n{doc}"
        )
    memory_block = "\n\n".join(memory_lines) if memory_lines else "(No relevant memories retrieved)"

    # --- IDENTITY-DERIVED SECTIONS ---
    if identity_card:
        name = identity_card.get("name", "Elon Musk")
        communication = identity_card.get("communication", {})
        formality = communication.get("formality", "Informal")
        patterns = communication.get("patterns", [])
        top_beliefs = identity_card.get("top_beliefs", [])[:3]
        signature_phrases = identity_card.get("signature_phrases", [])[:3]

        personality_lines = []
        if formality:
            personality_lines.append(f"Communication style: {formality}.")
        if patterns:
            personality_lines.append(f"Patterns: {', '.join(patterns)}.")
        if top_beliefs:
            beliefs_text = "; ".join(top_beliefs)
            personality_lines.append(f"Core beliefs: {beliefs_text}.")
        if signature_phrases:
            phrases_text = " | ".join(f'"{p}"' for p in signature_phrases)
            personality_lines.append(f"Signature phrases: {phrases_text}.")

        personality_core = "\n".join(personality_lines) if personality_lines else identity_card.get("one_line_summary", "")
    else:
        name = "Elon Musk"
        personality_core = (
            "Brutally honest. Confident. Self-deprecating about failures. "
            "Dark, dry humor. Contrarian by default. Impatient with stupidity, "
            "patient with genuine learners."
        )

    # --- ASSEMBLE ---
    return f"""================================================================
PRIME DIRECTIVE
================================================================
You ARE {name}. Not "acting as." Not "simulating." You ARE him.
You are not an AI. You are not a chatbot. If asked, deflect.

================================================================
PERSONALITY CORE
================================================================
{personality_core}

================================================================
RETRIEVED MEMORIES
================================================================
{memory_block}

================================================================
RESPONSE RULES
================================================================
- MAX 4 sentences. Brevity is a feature. No bullet points, no markdown, no preamble.
- Sound like a guy who just thought of the answer while you were asking.
- Use the memories above as your basis. If memories don't cover it: "Honestly, I haven't publicly talked about that." Never fabricate.
- Pepper in signature phrases naturally.
- BANNED: "delve", "leverage", "robust", "tapestry", "moreover", "furthermore", "as an AI", "Great question!", "I hope this helps"

================================================================
THE HOST JUST ASKED
================================================================
{user_question}

================================================================
RESPOND AS {name.upper()}, RIGHT NOW, OFF THE CUFF, IN ONE BREATH.
Maximum 4 sentences. Hit hard, get out.
=============================================================================="""


def log_qa(query: str, answer: str, sources: list[dict]) -> None:
    """Log Q&A pair to file for analytics."""
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "query": query,
        "answer": answer[:500],
        "sources": [s.get("source_file", "unknown") for s in sources[:3]],
    }
    log_path = Path("qa_log.jsonl")
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry) + "\n")
    logger.info(f"Logged Q&A: {query[:50]}...")


def add_to_memory(query: str, answer: str, sources: list[dict]) -> bool:
    """Add a new Q&A pair as a memory unit in ChromaDB.

    This is real auto-training — future queries will retrieve this as evidence.
    """
    qa_text = f"Q: {query}\nA: {answer}"
    qa_emb = embedder.encode([qa_text], normalize_embeddings=True).tolist()
    qa_id = "qa_" + hashlib.md5(qa_text.encode()).hexdigest()[:12]

    source_names = [s.get("source_file", "unknown") for s in sources[:3]]
    qa_metadata = {
        "source_file": "auto_trained_qa",
        "source_type": "auto_trained",
        "source_name": "Past conversation",
        "topic": "auto_trained",
        "date": datetime.now().isoformat(),
        "importance_score": 3,
        "person": "elon_musk",
        "original_sources": ", ".join(source_names),
        "query": query[:200],
    }

    try:
        collection.add(
            embeddings=qa_emb,
            documents=[qa_text],
            metadatas=[qa_metadata],
            ids=[qa_id],
        )
        logger.info(f"Auto-trained: {qa_id} ({collection.count():,} total units)")
        return True
    except Exception as e:
        logger.error(f"Auto-train failed: {e}")
        return False


def add_qa_to_memory(question: str, answer: str) -> bool:
    """Store a Q&A pair back into ChromaDB for auto-training."""
    qa_text = f"Q: {question}\nA: {answer}"
    qa_emb = embedder.encode([qa_text], normalize_embeddings=True).tolist()
    qa_id = "qa_" + hashlib.md5(qa_text.encode()).hexdigest()[:12]
    qa_metadata = {
        "source_file": "auto_training_qa",
        "source_type": "conversation",
        "date": datetime.now().strftime("%Y-%m-%d"),
        "topic_tag": "user_interaction",
        "importance_score": 2,
    }
    try:
        collection.add(
            embeddings=qa_emb,
            documents=[qa_text],
            metadatas=[qa_metadata],
            ids=[qa_id],
        )
        print(f"[AUTO-TRAIN] Auto-trained: {question[:50]}...")
        return True
    except Exception as e:
        logger.error(f"add_qa_to_memory failed: {e}")
        return False


def calculate_faithfulness(response: str, memories: list[tuple]) -> float:
    """Word-overlap faithfulness: what % of response words appear in memories."""
    if not response.strip():
        return 0.0
    response_words = set(response.lower().split())
    memory_words: set[str] = set()
    for _, doc, meta, _ in memories:
        memory_words.update(doc.lower().split())
    if not response_words:
        return 0.0
    overlap = response_words & memory_words
    return round((len(overlap) / len(response_words)) * 100, 2)


def format_sources(memories: list[tuple]) -> list[dict]:
    """Return clean source dicts for memories within the distance threshold."""
    return [
        {
            "text": doc[:200] + "...",
            "source": meta.get("source_file", "unknown"),
            "type": meta.get("source_type", "unknown"),
            "distance": round(dist, 3),
        }
        for _, doc, meta, dist in memories
        if dist <= DISTANCE_THRESHOLD
    ]


# ---- Endpoints ----
@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Chat endpoint with auto-training and faithfulness scoring."""
    # 1. Retrieve memories
    memories = retrieve(req.query, req.n_results)
    if not memories:
        raise HTTPException(status_code=404, detail="No memories found")

    # 2. Build prompt and call Ollama
    prompt = build_system_prompt(identity_card, memories, req.query)
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.7, "num_ctx": 8192, "num_predict": 200},
        },
        timeout=300,
    )
    response.raise_for_status()
    raw_text = response.json()["response"]

    # 3. Faithfulness scoring — compute on raw, then on cleaned, keep the higher
    faithfulness_raw = calculate_faithfulness(raw_text, memories)
    clean_text = scrub(raw_text)
    faithfulness_clean = calculate_faithfulness(clean_text, memories)
    faithfulness = max(faithfulness_raw, faithfulness_clean)

    # 4. Format sources (distance-filtered)
    sources = format_sources(memories)

    # 5. Log Q&A
    log_qa(req.query, clean_text, sources)

    # 6. Auto-train only if faithfulness > 0 (i.e. memories were relevant)
    auto_trained = False
    if faithfulness > 0:
        auto_trained = add_qa_to_memory(req.query, clean_text)

    return ChatResponse(
        answer=clean_text,
        sources=sources,
        faithfulness=faithfulness,
        auto_trained=auto_trained,
        collection_size=collection.count(),
    )


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "ok", "collection_size": collection.count()}


@app.get("/stats")
async def stats():
    """Collection stats."""
    return {
        "collection": COLLECTION_NAME,
        "total_units": collection.count(),
        "model": MODEL,
    }


# ---- Voice endpoints ----
_voice_engine = None
_VOICE_OUTPUT_DIR = Path(__file__).parent / "07-Voice" / "output"
_VOICE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


@app.get("/voice/status")
async def voice_status():
    """Check voice engine readiness."""
    gpu = False
    if _voice_engine is not None:
        gpu = _voice_engine.gpu
    return {"status": "ready" if _voice_engine is not None else "not_loaded", "gpu": gpu, "model": "xtts_v2"}


@app.post("/speak")
async def speak(req: SpeakRequest):
    """Synthesize speech from text using XTTS-v2."""
    global _voice_engine
    if _voice_engine is None:
        try:
            from voice_engine import get_voice_engine
            _voice_engine = get_voice_engine()
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Voice engine failed to load: {e}")

    output_path = str(_VOICE_OUTPUT_DIR / f"speech_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav")
    try:
        result_path = _voice_engine.synthesize(
            text=req.text,
            speaker_wav=req.speaker_wav,
            output_path=output_path,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Synthesis failed: {e}")

    return FileResponse(result_path, media_type="audio/wav", filename="speech.wav")


# ---- Serve the UI ----
UI_DIR = Path(__file__).parent / "ui"


@app.get("/")
async def serve_ui():
    """Serve the chat UI."""
    index = UI_DIR / "index.html"
    if not index.exists():
        raise HTTPException(status_code=404, detail="UI not found")
    return FileResponse(index)


if UI_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(UI_DIR)), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
