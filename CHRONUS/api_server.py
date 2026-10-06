#!/usr/bin/env python3
"""
CHRONUS - FastAPI Server

Answers questions as the persona from retrieved memories: natural mode (LLM,
services/natural_mode.py) or Mix Method (verbatim template,
services/mix_method.py). Auto-training (writing Q&A back into memory) is
disabled — see add_qa_to_memory().
"""

import hashlib
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional

import chromadb

# WORKAROUND (same as 06-Testing/embed_elon.py): pyarrow 24.0.0 access-violates
# (hard native crash, no traceback) when pyarrow is loaded AFTER chromadb +
# torch have initialized their native DLLs — which happens via
# sentence_transformers -> torch/sklearn/datasets. Pre-loading pyarrow.dataset
# FIRST fixes the import order and avoids the crash.
import pyarrow.dataset  # noqa: F401  (must be imported before sentence_transformers)
from fastapi import FastAPI, HTTPException, Query, UploadFile, File
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from sentence_transformers import SentenceTransformer

# ---- Response pipelines ----
from services.mix_method import generate_mix_method_response  # CHRONUS core contribution
from services.natural_mode import generate_natural_response
from services.provenance import anchor_first, content_words, format_source_citation, grounding_score
from services import personas as ps
from services import tts
# Quick profile answers; re-exported for tests and evaluation scripts
from services.profile import (BASIC_INFO_PATTERNS, BASIC_PROFILE, check_basic_info, get_profile,  # noqa: F401
                              profile_context_block)
from services.persona_routes import InterviewAnswer, embed_interview_answer, make_router


# ---- Logging ----
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("chronus")

# ---- Config (Task 4.2: centralized in config.py) ----
from config import config

OLLAMA_URL = config.OLLAMA_URL + "/api/generate"
MODEL = config.LLM_MODEL
COLLECTION_NAME = config.COLLECTION_NAME
CHROMA_PATH = config.CHROMA_PATH
N_RESULTS = config.N_RESULTS  # BUG 4 FIX: was 5; CHRONUS paper specifies top-k = 3
IMPORTANCE_WEIGHT = config.IMPORTANCE_WEIGHT
DISTANCE_THRESHOLD = config.DISTANCE_THRESHOLD

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
embedder = SentenceTransformer(config.EMBEDDING_MODEL, device="cpu")
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


# ---- Mix Method identity card loader (models/ directory) ----
MIX_IDENTITY_CARD_DIR = Path(__file__).parent / "models"


def load_mix_method_identity_card(person: str = "elon_musk") -> dict:
    """Load the identity card used by the Mix Method pipeline from models/.

    Differs from load_identity_card() above (which serves the legacy LLM
    prompt path from 03-Identity-Card/): this one reads
    models/<person>/identity_card.json and returns an EMPTY dict (never
    None) when the card is missing, so the Mix Method pipeline can degrade
    gracefully to its built-in defaults.
    """
    card_path = MIX_IDENTITY_CARD_DIR / person / "identity_card.json"
    if card_path.exists():
        with open(card_path, "r", encoding="utf-8") as f:
            return json.load(f)
    # Expected for custom personas (no generated identity card), so no warning
    return {}


# ---- Request/Response models ----
# Inputs are bounded at the API boundary: n_results drives an n*4 ChromaDB
# query, and an unknown mode used to fall silently into Mix Method.
class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)


class ChatRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    n_results: int = Field(default=N_RESULTS, ge=1, le=10)
    mode: Literal["natural", "mix_method"] = "natural"  # LLM-based or template-based
    # Recent conversation, oldest first, so follow-ups ("which state?") make sense.
    history: list[ChatTurn] = Field(default_factory=list, max_length=20)
    # Which model to talk to: a pretrained one or a custom one (services/personas.py)
    persona: str = Field(default=config.DEFAULT_PERSONA, pattern=ps.PERSONA_ID_PATTERN)

    @field_validator("query")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("query must not be blank")
        return value


class ChatResponse(BaseModel):
    answer: str
    sources: list[dict]
    # Share of the answer's words found in the evidence it cites (0-1); a
    # lexical grounding signal, see calculate_faithfulness().
    faithfulness: float
    auto_trained: bool
    collection_size: int
    # BUG 3 FIX: fields to support the true uncertainty fallback path
    confidence: str = "medium"
    fallback: bool = False
    # Which generation path produced the answer:
    # "natural" | "mix_method" | "mix_method_fallback" | "fallback"
    mode: str = "mix_method"
    # Shown to the user when the requested mode couldn't be used
    notice: str = ""


class SpeakRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    # Speak in this model's consented voice (services/personas.py); the client
    # no longer passes a file path
    persona: str = Field(pattern=ps.PERSONA_ID_PATTERN)


# ---- Core functions ----
_REFERS_BACK = re.compile(r"\b(it|that|this|these|those|they|them|there|he|she|him|her|its)\b")


def is_follow_up(query: str) -> bool:
    """Does this question lean on the previous turn for its topic?

    True for "why?", "why was it hard?", "is that true?", "which state?";
    False for short standalone questions like "Why Mars?" or "How do you
    handle failure?" (an earlier word-count-only rule glued the previous
    Mars answer onto the failure question).
    """
    words = re.findall(r"[a-z']+", query.lower())
    if not words or len(words) > 6:
        return False
    own_topic = content_words(query)
    if not own_topic:
        return True  # "why?", "how so?", "and then?"
    if _REFERS_BACK.search(query.lower()) and len(own_topic) <= 1:
        return True  # "why was it hard?" (but not "is it hard to run Tesla?")
    return len(words) <= 2 and words[0] in ("which", "what", "where", "when", "who")  # "which state?"


def retrieval_query(query: str, history: list[ChatTurn]) -> str:
    """Text to search memory with.

    Follow-ups (see is_follow_up) carry no topic of their own, so the previous
    exchange is prepended. The previous answer matters most: for "Tell me
    about your childhood" -> "why was it hard?", the question alone retrieved
    2008 business hardships; with the answer it finds the childhood memories.
    """
    if history and is_follow_up(query):
        prev_question = next((t.content for t in reversed(history) if t.role == "user"), "")
        prev_answer = next((t.content for t in reversed(history) if t.role == "assistant"), "")
        context = f"{prev_question} {prev_answer[:300]}".strip()
        if context:
            return f"{context} {query}"
    return query



def retrieve(query: str, n: int = N_RESULTS, memory=None, where: dict | None = None,
             threshold: float | None = None) -> Optional[list[tuple]]:
    """Retrieve top-K memories with importance bias from *memory* (a persona's
    ChromaDB collection; defaults to the default persona's). *where* is a
    ChromaDB metadata filter, e.g. to hold a source out during evaluation.

    BUG 2 FIX: returns None when no memory passes DISTANCE_THRESHOLD,
    signaling insufficient evidence to the caller.

    BUG 8 FIX: filter FIRST by raw distance (theta check), THEN re-rank the
    survivors by adjusted (importance-biased) distance, THEN take top-n.
    Previously ranking used adjusted distance while the threshold check used
    raw distance on an already-truncated top-n list — so a high-importance
    memory could rank #1 by adjusted score yet be filtered out, and candidates
    beyond the pre-truncated top-n never got a chance at the threshold check.
    """
    q_emb = embedder.encode([query], normalize_embeddings=True).tolist()
    raw = (memory or collection).query(query_embeddings=q_emb, n_results=n * 4, where=where)
    docs = raw["documents"][0]
    metas = raw["metadatas"][0]
    dists = raw["distances"][0]

    # 1. Build scored list from raw ChromaDB results (raw distance only here),
    # skipping exact duplicate texts (e.g. the same letter uploaded twice)
    scored, seen = [], set()
    for doc, meta, dist in zip(docs, metas, dists):
        key = " ".join(doc.lower().split())
        if key not in seen:
            seen.add(key)
            scored.append((doc, meta, dist))

    # 2. BUG 8 FIX: FILTER FIRST — keep only memories passing the raw-distance
    # threshold (theta). Importance must never rescue a memory past theta.
    # *threshold*: a persona's own calibrated value (persona.json), else the global one
    limit = threshold or DISTANCE_THRESHOLD
    passing = [(doc, meta, dist) for doc, meta, dist in scored if dist <= limit]
    # Very short memories ("Mars is The New World") sit close to short
    # questions in embedding space but carry almost no content; drop them
    # whenever longer evidence also passed the threshold.
    substantive = [p for p in passing if len(p[0].split()) >= config.MIN_EVIDENCE_WORDS]
    passing = substantive or passing

    # 3. THEN re-rank the survivors by adjusted (importance-biased) distance
    passing_with_adjusted = [
        (dist - (meta.get("importance_score", 1) * IMPORTANCE_WEIGHT), doc, meta, dist)
        for doc, meta, dist in passing
    ]
    passing_with_adjusted.sort(key=lambda x: x[0])  # Sort by adjusted

    # 4. Take top-n from the re-ranked results
    result = passing_with_adjusted[:n]

    # 5. BUG 2 FIX retained: return None when nothing passed the threshold
    if not result:
        return None

    # 6. Drop memories that match much worse than the best one. Small custom
    # models otherwise fill the 2nd/3rd slots with unrelated text (~0.47
    # behind the best); on Elon's corpus supporting memories sit <= 0.20 behind.
    best = min(r[3] for r in result)
    return [r for r in result if r[3] <= best + config.SUPPORT_MARGIN]


# DEPRECATED: Used by legacy LLM response path (now commented out).
# Kept for potential re-enable. See /chat endpoint for Mix Method usage.
def build_system_prompt(identity_card: dict | None, memories: list[tuple], user_question: str) -> str:
    """Build the full system prompt dynamically from the identity card and memories."""

    # --- MEMORY BLOCK ---
    # BUG 2 FIX: retrieve() now filters by DISTANCE_THRESHOLD and returns None
    # when nothing passes (the /chat endpoint handles that case), so the old
    # `filtered = memories[:1]` worst-match fallback was removed.
    filtered = [(adj, doc, meta, dist) for adj, doc, meta, dist in memories if dist <= DISTANCE_THRESHOLD]

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


# Next to this file, not the current working directory (starting the server
# from the repo root used to scatter logs there).
QA_LOG_PATH = Path(__file__).parent / "qa_log.jsonl"


def log_qa(query: str, answer: str, sources: list[dict], **details) -> None:
    """Log Q&A pair to file for analytics. *details*: mode, confidence, etc."""
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "query": query,
        "answer": answer[:500],
        "sources": [s.get("source_file", "unknown") for s in sources[:3]],
        **details,
    }
    with QA_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry) + "\n")
    logger.info(f"Logged Q&A: {query[:50]}...")


def add_qa_to_memory(question: str, answer: str) -> bool:
    """Store a Q&A pair back into ChromaDB for auto-training.

    BUG 9 FIX: the duplicate add_to_memory() (the only other user of which was
    chat_elon.py, now served by services/memory_store.py) was removed — this
    is the canonical in-server version.

    NOTE: currently DISABLED per BUG 1 fix (memory poisoning risk) — the /chat
    endpoint stopped calling it until a human-review step exists.
    """
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
    """Share (0-1) of the answer's content words found in its evidence
    (services.provenance.grounding_score). Replaces a hardcoded 1.0/0.7 that
    only mirrored the confidence label."""
    return grounding_score(response, [doc for _, doc, _, _ in memories])


# ---- Endpoints ----
@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """Answer a question as the chosen persona, grounded in its memories.

    Plain `def` (was `async def` doing blocking I/O): FastAPI runs it in a
    worker thread, so a slow LLM call no longer freezes every other request.
    """
    persona = ps.load_persona(req.persona)
    if persona is None:
        raise HTTPException(status_code=404, detail=f"No model called '{req.persona}'")
    if persona.get("status") != "ready":
        raise HTTPException(status_code=409, detail=f"{persona['name']} isn't built yet. Finish the Create steps first.")
    memory = ps.get_collection(client, persona)

    # Check for basic info requests first (skip RAG for simple facts). Only
    # personas with a curated BASIC_PROFILE entry have any.
    basic = check_basic_info(req.query, persona["id"])
    if basic:
        return ChatResponse(
            answer=basic["response"],
            sources=basic["sources"],
            faithfulness=1.0,
            auto_trained=False,
            collection_size=memory.count(),
            confidence=basic["confidence"],
            fallback=False,
            mode="basic_info"
        )

    # 1. Retrieve memories (follow-ups borrow the previous question's topic)
    memories = retrieve(retrieval_query(req.query, req.history), req.n_results, memory,
                        threshold=persona.get("distance_threshold"))

    # BUG 3 FIX: true uncertainty fallback — if retrieve() returned None, no
    # memory passed DISTANCE_THRESHOLD, so there is insufficient evidence.
    # Return a low-confidence fallback WITHOUT calling the LLM at all, instead
    # of relying on a prompt instruction that could still receive garbage data.
    if memories is None:
        return ChatResponse(
            answer="I don't have any documented information about that in my available records.",
            sources=[],
            faithfulness=0.0,
            auto_trained=False,
            collection_size=memory.count(),
            confidence="low",
            fallback=True,
            mode="fallback",
        )

    # =========================================================================
    # RESPONSE GENERATION — mode selection
    #   "natural"    (default): LLM answer in the persona's voice, grounded in
    #                evidence (auto-falls back to Mix Method if the LLM fails).
    #   "mix_method": template-based 3-part response — NO LLM call, verbatim
    #                quotes from retrieved memories.
    # Both put the persona's own words first (anchor_first), so a biography or
    # news passage is never quoted as "what I've actually said".
    # =========================================================================
    identity_card = load_mix_method_identity_card(persona["id"])
    evidence = anchor_first(memories[:3])
    mode, notice = req.mode, ""
    # Custom models are local-first: AI voice sends evidence excerpts to the
    # cloud LLM provider, so it needs the creator's opt-in (paper: disclose
    # cloud use, keep personal data on-device by default).
    # (Ollama and the "local" provider run on this machine, so they need no opt-in.)
    if mode == "natural" and config.LLM_PROVIDER not in ("ollama", "local") and not persona.get("allow_cloud_llm"):
        mode = "mix_method"
        notice = "AI voice is off for this model because it would send excerpts to a cloud AI service, so these are verbatim quotes."

    if mode == "natural":
        result = generate_natural_response(
            query=req.query,
            memories=evidence,
            identity_card=identity_card,
            profile_block=profile_context_block(persona["id"]),
            history=[turn.model_dump() for turn in req.history],
            persona_name=persona["name"],
            style_notes=persona.get("style_notes"),
            # The local LoRA adapter (lora/train_lora.py) was trained on Elon's words only
            use_adapter=persona["id"] == "elon_musk",
        )
        sources = result["sources"]
    else:
        result = generate_mix_method_response(
            query=req.query,
            memories=evidence,  # (adjusted_dist, doc_text, metadata, raw_dist) tuples
            identity_card=identity_card,
            persona_name=persona["name"],
            include_sources=True,
        )
        # Mix Method quotes evidence[0] (Part 1) + evidence[1:3] (Part 2), so
        # citations cover exactly the evidence used, in the same order.
        sources = [format_source_citation(meta, doc, dist) for _, doc, meta, dist in evidence]

    # Natural mode scores itself against evidence + profile (its grounding guard)
    faithfulness = result.get("faithfulness", calculate_faithfulness(result["response"], evidence))
    mode = result.get("mode", mode)
    log_qa(req.query, result["response"], sources, persona=persona["id"],
           mode=mode, confidence=result["confidence"], faithfulness=faithfulness)

    return ChatResponse(
        answer=result["response"],
        sources=sources,
        faithfulness=faithfulness,
        auto_trained=False,
        collection_size=memory.count(),
        confidence=result["confidence"],
        fallback=result.get("fallback", False),
        mode=mode,
        notice=notice,
    )


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "ok", "collection_size": collection.count()}


@app.get("/stats")
async def stats():
    """Collection stats and the models actually in use."""
    uses_openai_api = config.LLM_PROVIDER in ("openai", "openrouter")
    return {
        "collection": COLLECTION_NAME,
        "total_units": collection.count(),
        "llm_provider": config.LLM_PROVIDER,
        "llm_model": config.OPENAI_MODEL if uses_openai_api else config.LLM_MODEL,
        "embedding_model": config.EMBEDDING_MODEL,
    }


# ---- Voice endpoints (services/tts.py) ----

@app.get("/voice/status")
async def voice_status():
    """Which voices the Listen button can use."""
    return {
        "stand_in": {"engine": "Kokoro-82M", "where": "local"},
        "cloned": {"engine": f"Fish Audio {config.FISH_TTS_MODEL}", "where": "cloud",
                   "configured": tts.cloud_voice_configured()},
    }


@app.post("/speak")
def speak(req: SpeakRequest):
    """Read *text* aloud for a model.

    Custom models whose creator uploaded a voice sample with consent (and
    opted in to Fish Audio) speak in that cloned voice. Pretrained models
    (public figures) are never cloned: they speak in a labelled Kokoro
    stand-in voice.
    """
    persona = ps.load_persona(req.persona)
    if persona is None:
        raise HTTPException(status_code=404, detail=f"No model called '{req.persona}'")
    if persona.get("kind") == "custom" and persona.get("voice"):
        voice_id = persona["voice"].get("fish_voice_id")
        if not voice_id:
            raise HTTPException(status_code=409, detail="This voice was saved before cloud voices; please upload it again")
        try:
            audio = tts.fish_speech(req.text, voice_id)
        except tts.VoiceServiceError as e:
            logger.error(f"Cloned voice failed for {persona['id']}: {e}")
            raise HTTPException(status_code=e.status, detail=str(e))
        return Response(content=audio, media_type="audio/mpeg", headers={"X-Chronus-Voice": "cloned"})
    if persona.get("kind") == "pretrained" and persona.get("stand_in_voice"):
        try:
            wav = tts.stand_in_wav(req.text, persona["stand_in_voice"])
        except Exception as e:
            logger.error(f"Stand-in voice failed for {persona['id']}: {e}")
            raise HTTPException(status_code=503, detail=f"Stand-in voice failed: {e}")
        return Response(content=wav, media_type="audio/wav", headers={"X-Chronus-Voice": "stand-in"})
    raise HTTPException(status_code=404, detail=f"{persona['name']} has no voice")


class VoiceDemoRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)

@app.post("/voice/demo")
def voice_demo(req: VoiceDemoRequest):
    """Test FishAudio API connection by generating speech without a custom reference ID."""
    try:
        audio = tts.fish_demo_speech(req.text)
    except tts.VoiceServiceError as e:
        logger.error(f"Demo voice failed: {e}")
        raise HTTPException(status_code=e.status, detail=str(e))
    return Response(content=audio, media_type="audio/mpeg", headers={"X-Chronus-Voice": "demo"})


@app.post("/voice/quick-clone")
async def quick_clone(audio: UploadFile = File(...)):
    """Bypass model creation and create a temporary voice model directly on FishAudio."""
    wav = await audio.read()
    try:
        voice_id = tts.fish_create_voice(wav, audio.filename, audio.content_type)
        return {"voice_id": voice_id}
    except tts.VoiceServiceError as e:
        raise HTTPException(status_code=e.status, detail=str(e))


class QuickSpeakRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    voice_id: str

@app.post("/voice/quick-speak")
def quick_speak(req: QuickSpeakRequest):
    """Speak using a specific voice_id (for the quick clone sandbox)."""
    try:
        audio = tts.fish_speech(req.text, req.voice_id)
        return Response(content=audio, media_type="audio/mpeg", headers={"X-Chronus-Voice": "cloned"})
    except tts.VoiceServiceError as e:
        raise HTTPException(status_code=e.status, detail=str(e))


# ============================================================================
# INTERVIEW PROTOCOL ENDPOINTS
# ============================================================================

@app.get("/interview/questions")
async def get_interview_questions(dimension: str = None):
    """Get interview questions, optionally filtered by dimension.

    Args:
        dimension: Optional dimension filter (personality, core_memories,
                   relationships, passions, beliefs_values, voice_communication)

    Returns:
        List of question objects with id, question, dimension, sub_dimension
    """
    from data.interview_protocol import (
        get_all_questions,
        get_questions_by_dimension,
        get_dimension_summary
    )

    if dimension:
        questions = get_questions_by_dimension(dimension)
        if not questions:
            raise HTTPException(status_code=404, detail=f"Unknown dimension: {dimension}")
    else:
        questions = get_all_questions()

    return {
        "questions": questions,
        "count": len(questions),
        "dimensions": get_dimension_summary()
    }


@app.get("/interview/dimensions")
async def get_interview_dimensions():
    """Get all interview dimensions with question counts."""
    from data.interview_protocol import get_dimension_summary

    return get_dimension_summary()


# Interview answers become retrievable memories, so these endpoints take a
# JSON body: browsers must preflight cross-site JSON POSTs (which this server
# rejects), so other websites can't silently write fake memories into the
# persona. They used to accept plain query parameters.
PERSON_ID = Query(config.DEFAULT_PERSONA, pattern=ps.PERSONA_ID_PATTERN)
MAX_INTERVIEW_BATCH = 50


def _persona_or_404(person: str) -> dict:
    persona = ps.load_persona(person)
    if persona is None:
        raise HTTPException(status_code=404, detail=f"No model called '{person}'")
    return persona


@app.post("/interview/answer")
def submit_interview_answer(item: InterviewAnswer, person: str = PERSON_ID):
    """Embed and store a single interview answer in that person's memory.

    Body: {"question_id": "Q7", "answer": "...", "origin": "self"}; origin
    records who answered (the person, family, a friend...). Each person has
    their own collection — answers no longer land in Elon's memory whatever
    `person` says.
    """
    persona = _persona_or_404(person)
    result = embed_interview_answer(client, embedder, persona, item)
    return {
        "success": True,
        "message": f"Embedded {item.question_id} ({result['dimension']})",
        "memory_id": result["memory_id"],
        "collection_size": ps.get_collection(client, persona).count()
    }


@app.post("/interview/complete")
def complete_interview(responses: list[InterviewAnswer], person: str = PERSON_ID):
    """Embed several interview answers at once (body: a list of answers)."""
    if len(responses) > MAX_INTERVIEW_BATCH:
        raise HTTPException(status_code=400, detail=f"At most {MAX_INTERVIEW_BATCH} answers per request")
    persona = _persona_or_404(person)

    results = {"embedded": 0, "failed": 0, "errors": []}
    for item in responses:
        try:
            embed_interview_answer(client, embedder, persona, item)
            results["embedded"] += 1
        except HTTPException as e:
            results["failed"] += 1
            results["errors"].append(f"{item.question_id}: {e.detail}")

    return {
        "success": results["failed"] == 0,
        **results,
        "collection_size": ps.get_collection(client, persona).count()
    }


# Pretrained + custom models: list, create, upload, interview, build, delete
app.include_router(make_router(client, embedder))


# ---- The website (FRONTEND/chronus-app, built with `npm run build`) ----
# Mounted last so every API route above wins; the React app uses #/ routes,
# so the server only has to serve index.html and its assets. In development
# the Vite server on :3000 serves the site instead and proxies /api here.
SITE_DIR = Path(__file__).resolve().parent.parent / "FRONTEND" / "chronus-app" / "dist"

@app.middleware("http")
async def revalidate_html(request, call_next):
    """Browsers must re-check index.html on every visit (assets have hashed
    names and can be cached): otherwise a browser that saw the old single-page
    UI kept showing it after the switch to the React site."""
    response = await call_next(request)
    if response.headers.get("content-type", "").startswith("text/html"):
        response.headers["Cache-Control"] = "no-cache"
    return response


if (SITE_DIR / "index.html").exists():
    app.mount("/", StaticFiles(directory=str(SITE_DIR), html=True), name="site")
else:
    @app.get("/")
    def site_not_built():
        return {"detail": "Website not built yet: run `npm --prefix FRONTEND/chronus-app run build`, "
                          "or use the dev server on http://localhost:3000"}


if __name__ == "__main__":
    import uvicorn
    # BUG 5 FIX: was "0.0.0.0", which exposed the server to the entire LAN.
    # Bind to loopback only — no auth exists on these endpoints.
    uvicorn.run(app, host=config.HOST, port=config.PORT)
