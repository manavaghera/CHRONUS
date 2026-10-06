#!/usr/bin/env python3
"""
CHRONUS - FastAPI Server

Answers questions as the persona from retrieved memories: natural mode (LLM,
services/natural_mode.py) or Mix Method (verbatim template,
services/mix_method.py). Auto-training (writing Q&A back into memory) only
happens through the human review queue (services/feedback.py).

Run: python api_server.py  (http://127.0.0.1:8001, website included)
"""

import json
import logging
import re
import time
from pathlib import Path
from typing import Literal, Optional

import chromadb
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from services import access, hybrid, tts, voice_sandbox
from services import personas as ps
from services.embedder import LazyEmbedder

# ---- Response pipelines ----
from services.mix_method import generate_mix_method_response  # CHRONUS core contribution
from services.natural_mode import generate_natural_response
from services.persona_routes import InterviewAnswer, embed_interview_answer, make_router

# Quick profile answers; re-exported for tests and evaluation scripts
from services.profile import (  # noqa: F401
    BASIC_INFO_PATTERNS,
    BASIC_PROFILE,
    check_basic_info,
    get_profile,
    profile_context_block,
)
from services.provenance import anchor_first, content_words, format_source_citation, grounding_score
from services.qa_log import QA_LOG_PATH, log_qa  # noqa: F401  (tests patch api_server.log_qa)

# ---- Logging ----
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("chronus")

# ---- Config (centralized in config.py) ----
from config import config

COLLECTION_NAME = config.COLLECTION_NAME
CHROMA_PATH = config.CHROMA_PATH
N_RESULTS = config.N_RESULTS  # the CHRONUS paper specifies top-k = 3
IMPORTANCE_WEIGHT = config.IMPORTANCE_WEIGHT
DISTANCE_THRESHOLD = config.DISTANCE_THRESHOLD

FALLBACK_ANSWER = "I don't have any documented information about that in my available records."

# ---- FastAPI ----
app = FastAPI(title="CHRONUS API", version="1.1.0")
access.install(app, config)

# ---- Connect to ChromaDB ----
client = chromadb.PersistentClient(path=CHROMA_PATH)
try:
    collection = client.get_collection(COLLECTION_NAME)
    logger.info(f"Loaded collection '{COLLECTION_NAME}' with {collection.count():,} memory units")
except Exception:
    collection = client.create_collection(name=COLLECTION_NAME, metadata={"hnsw:space": "cosine"})
    logger.warning(f"Created NEW empty collection '{COLLECTION_NAME}'. "
                   "Run: python 06-Testing/embed_elon.py to populate memories.")

# ---- Embedding model: loaded on first use (services/embedder.py) ----
embedder = LazyEmbedder(config.EMBEDDING_MODEL, device="cpu")
# Optional cross-encoder reranker (config.RERANKER_MODEL; off by default)
reranker = hybrid.Reranker(config.RERANKER_MODEL) if config.RERANKER_MODEL else None


# ---- Mix Method identity card loader (models/ directory) ----
MIX_IDENTITY_CARD_DIR = Path(__file__).parent / "models"


def load_mix_method_identity_card(person: str = "elon_musk") -> dict:
    """models/<person>/identity_card.json, or an EMPTY dict (never None) when
    the card is missing, so Mix Method degrades to its built-in defaults.
    Custom personas have no card, so a missing one is not worth a warning."""
    card_path = MIX_IDENTITY_CARD_DIR / person / "identity_card.json"
    if card_path.exists():
        return json.loads(card_path.read_text(encoding="utf-8"))
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
    confidence: str = "medium"
    fallback: bool = False
    # Which generation path produced the answer:
    # "natural" | "mix_method" | "mix_method_fallback" | "fallback" | "basic_info"
    mode: str = "mix_method"
    # Shown to the user when the requested mode couldn't be used
    notice: str = ""
    # Q&A log entry id, for thumbs up/down feedback (services/feedback.py)
    id: str = ""


class SpeakRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    # Speak in this model's consented voice (services/personas.py)
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
             threshold: float | None = None, mode: str | None = None) -> Optional[list[tuple]]:
    """Retrieve top-K memories from *memory* (a persona's ChromaDB collection;
    defaults to the default persona's). *where* is a ChromaDB metadata
    filter, e.g. to hold a source out during evaluation. *mode*: "dense"
    (semantic search + importance bias) or "hybrid" (semantic + BM25 fused
    by reciprocal rank, services/hybrid.py); default config.RETRIEVAL_MODE.

    Returns None when no memory passes the distance threshold, signalling
    insufficient evidence to the caller.

    Order matters: filter FIRST by raw distance, THEN rank the survivors,
    THEN take top-n, so neither importance nor keyword matches can ever
    rescue a memory past the threshold.
    """
    memory = memory or collection
    mode = mode or config.RETRIEVAL_MODE
    q_emb = embedder.encode([query], normalize_embeddings=True).tolist()
    raw = memory.query(query_embeddings=q_emb, n_results=n * 4, where=where)
    candidates = list(zip(raw["ids"][0], raw["documents"][0], raw["metadatas"][0], raw["distances"][0]))
    dense_order = [c[0] for c in candidates]
    keyword_order: list[str] = []
    if mode == "hybrid":
        keyword_order = hybrid.keyword_candidates(memory, query, n * 4, where)
        found = set(dense_order)
        candidates += hybrid.fetch_with_distance(memory, [i for i in keyword_order if i not in found], q_emb[0])

    # 1. Skip exact duplicate texts (e.g. the same letter uploaded twice)
    scored, seen = [], set()
    for mid, doc, meta, dist in candidates:
        key = " ".join(doc.lower().split())
        if key not in seen:
            seen.add(key)
            scored.append((mid, doc, meta or {}, dist))

    # 2. Keep only memories passing the raw-distance threshold. *threshold*:
    # a persona's own calibrated value (persona.json), else the global one.
    # (`is None`, not `or`: a persona threshold of 0.0 is a real setting.)
    limit = DISTANCE_THRESHOLD if threshold is None else threshold
    passing = [c for c in scored if c[3] <= limit]
    # Very short memories ("Mars is The New World") sit close to short
    # questions in embedding space but carry almost no content; drop them
    # whenever longer evidence also passed the threshold.
    substantive = [c for c in passing if len(c[1].split()) >= config.MIN_EVIDENCE_WORDS]
    passing = substantive or passing
    if not passing:
        return None

    # 3. Rank the survivors: importance-biased distance (dense), or fused
    # semantic + keyword rank (hybrid). Tuples: (rank_key, doc, meta, dist)
    if mode == "hybrid":
        fused = hybrid.rrf(dense_order, keyword_order)
        ranked = sorted(((-fused.get(mid, 0.0), doc, meta, dist) for mid, doc, meta, dist in passing),
                        key=lambda x: (x[0], x[3]))
    else:
        ranked = sorted(((dist - (meta.get("importance_score", 1) * IMPORTANCE_WEIGHT), doc, meta, dist)
                         for _, doc, meta, dist in passing), key=lambda x: x[0])

    # 4. Optional cross-encoder rerank of the best few (config.RERANKER_MODEL)
    if reranker is not None and len(ranked) > 1:
        head = ranked[: n * 2]
        scores = reranker.scores(query, [r[1] for r in head])
        ranked = [r for _, r in sorted(zip(scores, head), key=lambda x: -x[0])] + ranked[n * 2:]

    # 5. Top-n, then drop memories that match much worse than the best one.
    # Small custom models otherwise fill the 2nd/3rd slots with unrelated
    # text (~0.47 behind the best); on Elon's corpus supporting memories sit
    # <= 0.20 behind.
    result = ranked[:n]
    best = min(r[3] for r in result)
    return [r for r in result if r[3] <= best + config.SUPPORT_MARGIN]


def calculate_faithfulness(response: str, memories: list[tuple]) -> float:
    """Share (0-1) of the answer's content words found in its evidence
    (services.provenance.grounding_score)."""
    return grounding_score(response, [doc for _, doc, _, _ in memories])


def _load_ready_persona(persona_id: str) -> dict:
    persona = ps.load_persona(persona_id)
    if persona is None:
        raise HTTPException(status_code=404, detail=f"No model called '{persona_id}'")
    if persona.get("status") != "ready":
        raise HTTPException(status_code=409, detail=f"{persona['name']} isn't built yet. Finish the Create steps first.")
    return persona


def answer_from_memory(query: str, persona: dict, memory, mode: str, history: list[ChatTurn],
                       n_results: int = N_RESULTS, where: dict | None = None) -> dict:
    """Retrieve evidence for *query* and answer it in *mode*.

    Returns a dict with response, sources, confidence, fallback, mode,
    faithfulness and notice. Shared by /chat and the roundtable.
    """
    memories = retrieve(retrieval_query(query, history), n_results, memory, where=where,
                        threshold=persona.get("distance_threshold"))

    # True uncertainty fallback: no memory passed the threshold, so there is
    # insufficient evidence. Answer without calling the LLM at all.
    if memories is None:
        return {"response": FALLBACK_ANSWER, "sources": [], "faithfulness": 0.0, "confidence": "low",
                "fallback": True, "mode": "fallback", "notice": ""}

    # "natural"   : LLM answer in the persona's voice, grounded in evidence
    #               (falls back to Mix Method if the LLM fails or invents).
    # "mix_method": template-based 3-part answer, verbatim quotes, no LLM.
    # Both put the persona's own words first (anchor_first), so a biography
    # or news passage is never quoted as "what I've actually said".
    identity_card = load_mix_method_identity_card(persona["id"])
    evidence = anchor_first(memories[:3])
    notice = ""
    # Custom models are local-first: AI voice sends evidence excerpts to the
    # cloud LLM provider, so it needs the creator's opt-in. (Ollama and the
    # "local" provider run on this machine, so they need no opt-in.)
    if mode == "natural" and config.LLM_PROVIDER not in ("ollama", "local") and not persona.get("allow_cloud_llm"):
        mode = "mix_method"
        notice = ("AI voice is off for this model because it would send excerpts to a cloud AI service, "
                  "so these are verbatim quotes.")

    if mode == "natural":
        result = generate_natural_response(
            query=query,
            memories=evidence,
            identity_card=identity_card,
            profile_block=profile_context_block(persona["id"]),
            history=[turn.model_dump() for turn in history],
            persona_name=persona["name"],
            style_notes=persona.get("style_notes"),
            # The local LoRA adapter (lora/train_lora.py) was trained on Elon's words only
            use_adapter=persona["id"] == "elon_musk",
            embedder=embedder,
        )
        sources = result["sources"]
    else:
        result = generate_mix_method_response(
            query=query,
            memories=evidence,  # (adjusted_dist, doc_text, metadata, raw_dist) tuples
            identity_card=identity_card,
            persona_name=persona["name"],
            include_sources=True,
        )
        # Mix Method quotes evidence[0] (Part 1) + evidence[1:3] (Part 2), so
        # citations cover exactly the evidence used, in the same order.
        sources = [format_source_citation(meta, doc, dist) for _, doc, meta, dist in evidence]

    # Natural mode scores itself against evidence + profile (its grounding guard)
    return {
        "response": result["response"],
        "sources": sources,
        "faithfulness": result.get("faithfulness", calculate_faithfulness(result["response"], evidence)),
        "confidence": result["confidence"],
        "fallback": result.get("fallback", False),
        "mode": result.get("mode", mode),
        "notice": notice,
    }


# ---- Endpoints ----
@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """Answer a question as the chosen persona, grounded in its memories.

    Plain `def`: FastAPI runs it in a worker thread, so a slow LLM call
    doesn't freeze other requests.
    """
    started = time.perf_counter()
    persona = _load_ready_persona(req.persona)
    memory = ps.get_collection(client, persona)

    # Simple profile facts skip retrieval. A question that also asks
    # something else ("When were you born and why did you start SpaceX?")
    # gets the fact AND an answer from memory for the rest.
    basic = check_basic_info(req.query, persona["id"])
    if basic and not basic.get("remainder"):
        result = {**basic, "faithfulness": 1.0, "notice": ""}
    elif basic:
        rest = answer_from_memory(basic["remainder"], persona, memory, req.mode, req.history, req.n_results)
        result = {
            **rest,
            "response": f"{basic['response']}\n\n{rest['response']}",
            "sources": basic["sources"] + rest["sources"],
            # The fact half is certain; the rest keeps its own confidence
            "fallback": False,
        }
    else:
        result = answer_from_memory(req.query, persona, memory, req.mode, req.history, req.n_results)

    # Every answer is logged, refusals included: they show what the archive
    # is missing (knowledge-gap report)
    entry_id = log_qa(req.query, result["response"], result["sources"], persona=persona["id"],
                      mode=result["mode"], confidence=result["confidence"], fallback=result["fallback"],
                      faithfulness=result["faithfulness"],
                      latency_ms=round((time.perf_counter() - started) * 1000))

    return ChatResponse(
        answer=result["response"],
        sources=result["sources"],
        faithfulness=result["faithfulness"],
        auto_trained=False,
        collection_size=memory.count(),
        confidence=result["confidence"],
        fallback=result["fallback"],
        mode=result["mode"],
        notice=result.get("notice", ""),
        id=entry_id or "",
    )


@app.get("/health")
def health():
    """Health check."""
    return {"status": "ok", "collection_size": collection.count()}


@app.get("/stats")
def stats():
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
def voice_status():
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
    text: str = Field(min_length=1, max_length=500)


@app.post("/voice/demo")
def voice_demo(req: VoiceDemoRequest):
    """Fish Audio's default voice (no cloning): checks the API key works."""
    try:
        audio = tts.fish_demo_speech(req.text)
    except tts.VoiceServiceError as e:
        logger.error(f"Demo voice failed: {e}")
        raise HTTPException(status_code=e.status, detail=str(e))
    return Response(content=audio, media_type="audio/mpeg", headers={"X-Chronus-Voice": "demo"})


# Clone-voice page: consented test voices, tracked and deletable
app.include_router(voice_sandbox.make_router())


# ============================================================================
# INTERVIEW PROTOCOL ENDPOINTS
# ============================================================================

@app.get("/interview/questions")
def get_interview_questions(dimension: str = None):
    """Interview questions, optionally filtered by dimension (personality,
    core_memories, relationships, passions, beliefs_values,
    voice_communication)."""
    from data.interview_protocol import get_all_questions, get_dimension_summary, get_questions_by_dimension

    if dimension:
        questions = get_questions_by_dimension(dimension)
        if not questions:
            raise HTTPException(status_code=404, detail=f"Unknown dimension: {dimension}")
    else:
        questions = get_all_questions()

    return {"questions": questions, "count": len(questions), "dimensions": get_dimension_summary()}


@app.get("/interview/dimensions")
def get_interview_dimensions():
    """All interview dimensions with question counts."""
    from data.interview_protocol import get_dimension_summary

    return get_dimension_summary()


# Interview answers become retrievable memories, so these endpoints take a
# JSON body: browsers must preflight cross-site JSON POSTs (which this server
# rejects), so other websites can't silently write fake memories.
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
    records who answered (the person, family, a friend...).
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

    return {"success": results["failed"] == 0, **results,
            "collection_size": ps.get_collection(client, persona).count()}


# Pretrained + custom models: list, create, upload, interview, build, delete
app.include_router(make_router(client, embedder))
# Optional access code (CHRONUS_ACCESS_CODE)
app.include_router(access.make_router(config))


# ---- The website (FRONTEND/chronus-app, built with `npm run build`) ----
# Mounted last so every API route above wins; the React app uses #/ routes,
# so the server only has to serve index.html and its assets. In development
# the Vite server on :3000 serves the site instead and proxies /api here.
SITE_DIR = Path(__file__).resolve().parent.parent / "FRONTEND" / "chronus-app" / "dist"


@app.middleware("http")
async def revalidate_html(request, call_next):
    """Browsers must re-check index.html on every visit (assets have hashed
    names and can be cached), so an old page is never shown after an update."""
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
    # Loopback by default (config.HOST): no login exists unless
    # CHRONUS_ACCESS_CODE is set, so never bind 0.0.0.0 casually.
    uvicorn.run(app, host=config.HOST, port=config.PORT)
