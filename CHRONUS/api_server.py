#!/usr/bin/env python3
"""
CHRONUS - FastAPI Server

Answers questions as the persona from retrieved memories: natural mode (LLM,
services/natural_mode.py) or Mix Method (verbatim template,
services/mix_method.py). Auto-training (writing Q&A back into memory) only
happens through the human review queue (services/feedback.py).

Run: python api_server.py  (http://127.0.0.1:8001, website included)
"""

import asyncio
import json
import logging
import queue
import re
import threading
import time
from pathlib import Path
from typing import Annotated, Literal, Optional

import chromadb
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator, model_validator

from services import (
    access,
    answer_cache,
    bundle,
    chroma_index,
    consent,
    consent_text,
    followups,
    hybrid,
    identity,
    insights,
    instance_lock,
    jobs,
    memory_routes,
    natural_mode,
    ops,
    originals,
    person_routes,
    private_files,
    roundtable,
    security_headers,
    site_forms,
    spirit,
    stt,
    style,
    timeline,
    translate,
    tts,
    voice_sandbox,
    wellbeing,
)
from services import personas as ps
from services.embedder import LazyEmbedder
from services.mix_method import _near_duplicate as near_duplicate

# ---- Response pipelines ----
from services.mix_method import generate_mix_method_response  # CHRONUS core contribution
from services.natural_mode import generate_natural_response
from services.persona_routes import InterviewAnswer, delete_model, embed_interview_answer, make_router
from services.persona_routes import summarize as summarize_persona

# Quick profile answers; re-exported for tests and evaluation scripts
from services.profile import (  # noqa: F401
    BASIC_INFO_PATTERNS,
    check_basic_info,
    get_profile,
    profile_context_block,
)
from services.provenance import FIRST_PERSON, anchor_first, content_words, format_source_citation, grounding_score, voice_of
from services.qa_log import QA_LOG_PATH, log_qa  # noqa: F401  (tests patch api_server.log_qa)

# ---- Logging ----
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("chronus")

# ---- Config (centralized in config.py) ----
from config import config
from config import validate as validate_settings

# Wrong settings stop the server instead of failing silently (a typo like
# "hybird" used to fall back to dense search without a word)
_setting_errors, _setting_warnings = validate_settings(config)
for _warning in _setting_warnings:
    logger.warning(_warning)
if _setting_errors:
    raise SystemExit("CHRONUS can't start, fix these settings (CHRONUS/.env):\n  " + "\n  ".join(_setting_errors))

COLLECTION_NAME = config.COLLECTION_NAME
CHROMA_PATH = config.CHROMA_PATH
N_RESULTS = config.N_RESULTS  # the CHRONUS paper specifies top-k = 3
IMPORTANCE_WEIGHT = config.IMPORTANCE_WEIGHT
DISTANCE_THRESHOLD = config.DISTANCE_THRESHOLD

FALLBACK_ANSWER = "I don't have any documented information about that in my available records."

# ---- Private data: owner-only files (services/private_files.py) ----
private_files.restrict_new_files()
private_files.tighten([ps.CUSTOM_DIR, Path(CHROMA_PATH), QA_LOG_PATH, insights.FEEDBACK_PATH, ops.AUDIT_LOG_PATH, site_forms.DATA_DIR,
                      Path(__file__).resolve().parent / ".env"])

# ---- FastAPI ----
app = FastAPI(title="CHRONUS API", version="1.1.0")
access.install(app, config)

# ---- Connect to ChromaDB ----
client = chromadb.PersistentClient(path=CHROMA_PATH)
try:
    collection = client.get_collection(COLLECTION_NAME)
    logger.info(f"Loaded collection '{COLLECTION_NAME}' with {collection.count():,} memory units")
except Exception:
    collection = client.create_collection(name=COLLECTION_NAME, metadata=chroma_index.COLLECTION_METADATA)
    logger.warning(f"Created NEW empty collection '{COLLECTION_NAME}'. "
                   "Run: python 06-Testing/embed_elon.py to populate memories.")

# Small collections used to keep their search index only in memory, and failed
# with "Nothing found on disk" when Chroma reloaded it (services/chroma_index.py)
_switched = chroma_index.ensure_all_saved(client)
if _switched:
    logger.info(f"Saved the search index of {_switched} collection(s) to disk")

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
    # Assistant turns: the memories that answer cited (sources[].memory_id), so
    # a follow-up searches from them and doesn't repeat the same quotes
    memory_ids: list[Annotated[str, Field(pattern=r"^[A-Za-z0-9_.:-]{1,100}$")]] = Field(default_factory=list,
                                                                                       max_length=10)


class ChatRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    n_results: int = Field(default=N_RESULTS, ge=1, le=10)
    mode: Literal["natural", "mix_method"] = "natural"  # LLM-based or template-based
    # Recent conversation, oldest first, so follow-ups ("which state?") make sense.
    history: list[ChatTurn] = Field(default_factory=list, max_length=20)
    # Which model to talk to: a pretrained one or a custom one (services/personas.py)
    persona: str = Field(default=config.DEFAULT_PERSONA, pattern=ps.PERSONA_ID_PATTERN)
    # Time travel: answer only from memories dated within these years
    year_from: Optional[int] = Field(default=None, ge=1000, le=2100)
    year_to: Optional[int] = Field(default=None, ge=1000, le=2100)
    # Answer in this language ("hi", "gu"...); default: the question's language
    language: Optional[str] = Field(default=None, pattern=r"^[a-z]{2}$")
    # How much to say: one focused quote / sentence, the usual, or more
    length: Literal["short", "normal", "detailed"] = "normal"
    # When the archive doesn't cover the question, infer an answer from what
    # they believed and said, labelled as such (services/spirit.py)
    spirit: bool = False

    @field_validator("query")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("query must not be blank")
        return value

    @model_validator(mode="after")
    def _years_in_order(self):
        if self.year_from is not None and self.year_to is not None and self.year_from > self.year_to:
            raise ValueError("year_from must not be after year_to")
        return self


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
    # Q&A log entry id, for thumbs up/down feedback (services/insights.py)
    id: str = ""
    # Crisis support replies (services/wellbeing.py) list helplines
    helplines: list[dict] = Field(default_factory=list)
    # Why this confidence: closest match, how many sources and whose words
    why: dict = Field(default_factory=dict)
    # Multilingual (services/translate.py): language of `answer`, and the
    # English original when it was translated
    language: str = "en"
    original_answer: str = ""


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
    if words and len(words) <= 8 and set(words) <= _CONTINUATION_WORDS:
        return True  # "tell me more", "what else?", "go on", "anything else about that?"
    if not words or len(words) > 6:
        return False
    own_topic = content_words(query)
    if not own_topic:
        return True  # "why?", "how so?", "and then?"
    if _REFERS_BACK.search(query.lower()) and len(own_topic) <= 1:
        return True  # "why was it hard?" (but not "is it hard to run Tesla?")
    return len(words) <= 2 and words[0] in ("which", "what", "where", "when", "who")  # "which state?"


# Words a continuation is made of ("tell me more", "what else?", "go on"):
# they carry no topic, so they used to be searched as if they did
_CONTINUATION_WORDS = frozenset(
    "tell me more say talk explain elaborate go on keep going continue else further anything something what please "
    "about that this it and then so detail details bit little a some can could you would".split()
)
_QUOTED = re.compile(r"[\"“]([^\"”]{15,})[\"”]")


def _previous_answer_text(turn: ChatTurn | None, memory) -> str:
    """What the previous answer was about: the memories it cited, or else the
    words it quoted. Its template text ("As I've said before:", "There's
    more context here.") used to steer the search for the follow-up."""
    if turn is None:
        return ""
    if turn.memory_ids and memory is not None:
        try:
            docs = memory.get(ids=turn.memory_ids[:3], include=["documents"])["documents"]
        except Exception:  # deleted since, or another model's ids
            docs = []
        if docs:
            return " ".join(d[:300] for d in docs)
    quoted = _QUOTED.findall(turn.content)
    return " ".join(quoted)[:600] if quoted else turn.content[:300]


def retrieval_query(query: str, history: list[ChatTurn], memory=None) -> str:
    """Text to search memory with.

    Follow-ups (see is_follow_up) carry no topic of their own, so the previous
    exchange is prepended. The previous answer matters most: for "Tell me
    about your childhood" -> "why was it hard?", the question alone retrieved
    2008 business hardships; with the answer it finds the childhood memories.
    """
    if history and is_follow_up(query):
        prev_question = next((t.content for t in reversed(history) if t.role == "user"), "")
        prev_answer = next((t for t in reversed(history) if t.role == "assistant"), None)
        context = f"{prev_question} {_previous_answer_text(prev_answer, memory)}".strip()
        if context:
            return f"{context} {query}"
    return query


def used_memory_ids(query: str, history: list[ChatTurn]) -> set[str]:
    """For a follow-up, the memories already quoted in this conversation (skipped, so
    "tell me more" brings something new instead of the same quotes again)."""
    if not (history and is_follow_up(query)):
        return set()
    return {mid for turn in history if turn.role == "assistant" for mid in turn.memory_ids}


def raw_caption(meta: dict) -> bool:
    """An auto-caption chunk whose speakers no one told apart (rebuild_elon.py)."""
    return str(meta.get("speaker_verified")) == "False" and str(meta.get("punctuated")) == "False"


def retrieve(query: str, n: int = N_RESULTS, memory=None, where: dict | None = None,
             threshold: float | None = None, mode: str | None = None,
             exclude: set[str] | None = None, skip=None) -> Optional[list[tuple]]:
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

    # 1. Skip exact duplicate texts (e.g. the same letter uploaded twice), and
    # *exclude*: memories a follow-up shouldn't quote again
    scored, seen = [], set()
    for mid, doc, meta, dist in candidates:
        key = " ".join(doc.lower().split())
        if exclude and (mid in exclude or (meta or {}).get("memory_id") in exclude):
            continue
        if skip is not None and skip(doc, meta or {}):  # never quoted: "never quote", off-limits topics
            continue
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
    # Raw auto-captions (no punctuation, speakers not told apart) run the
    # host's words into the answer ("...let's ask about spacex okay well");
    # likewise dropped whenever better-transcribed evidence also passed.
    transcribed = [c for c in passing if not raw_caption(c[2])]
    passing = transcribed or passing
    if not passing:
        return None

    # 3. Rank the survivors: importance-biased distance (dense), or fused
    # semantic + keyword rank (hybrid). Tuples: (rank_key, doc, meta, dist)
    if mode == "hybrid":
        fused = hybrid.rrf(dense_order, keyword_order)
        ranked = sorted(((-fused.get(mid, 0.0), doc, meta, dist) for mid, doc, meta, dist in passing),
                        key=lambda x: (x[0], x[3]))
    else:
        # Importance only breaks near-ties: at most IMPORTANCE_WEIGHT (score
        # 5) and 0 at score 1. Unbounded (score x 0.15) it handed interview
        # answers (score 4) a 0.45 head start over tweets and letters (1),
        # more than the whole support margin, so it overrode relevance.
        def bonus(meta):
            score = meta.get("importance_score", 1)
            score = score if isinstance(score, (int, float)) else 1
            return IMPORTANCE_WEIGHT * min(1.0, max(0.0, (score - 1) / 4))
        ranked = sorted(((dist - bonus(meta), doc, meta, dist) for _, doc, meta, dist in passing), key=lambda x: x[0])

    # 4. Optional cross-encoder rerank of the best few (config.RERANKER_MODEL)
    if reranker is not None and len(ranked) > 1:
        head = ranked[: n * 2]
        scores = reranker.scores(query, [r[1] for r in head])
        ranked = [r for _, r in sorted(zip(scores, head), key=lambda x: -x[0])] + ranked[n * 2:]

    # 5. Top-n, skipping near-duplicates of what's already chosen (Elon
    # tweets the same line many ways), then drop memories that match much
    # worse than the best one. Small custom models otherwise fill the 2nd/3rd
    # slots with unrelated text (~0.47 behind the best); on Elon's corpus
    # supporting memories sit <= 0.20 behind.
    result = []
    for candidate in ranked:
        if not any(near_duplicate(candidate[1], chosen[1]) for chosen in result):
            result.append(candidate)
        if len(result) == n:
            break
    best = min(r[3] for r in result)
    return [r for r in result if r[3] <= best + config.SUPPORT_MARGIN]


def _match(distance: float) -> int:
    """Cosine distance as the "match %" the website shows."""
    return max(0, round((1 - distance) * 100))


def closest_distance(query: str, memory, where: dict | None = None) -> float | None:
    """Distance of the single closest memory (explains an "I don't know")."""
    if memory.count() == 0:
        return None
    raw = memory.query(query_embeddings=embedder.encode([query], normalize_embeddings=True).tolist(),
                       n_results=1, where=where, include=["distances"])
    dists = raw["distances"][0]
    return dists[0] if dists else None


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
    reason = consent.unavailable(persona)  # paused, or consent due for review
    if reason:
        raise HTTPException(status_code=423, detail=reason)
    return persona


def ai_voice_allowed(persona: dict) -> bool:
    """Custom models are local-first: the AI voice sends evidence excerpts to
    the cloud LLM provider, so it needs the creator's opt-in. Ollama and the
    "local" provider run on this machine, so they need none."""
    return config.LLM_PROVIDER in ("ollama", "local") or bool(persona.get("allow_cloud_llm"))


def person_profile_block(persona: dict, memory) -> str:
    """Public-record facts and the identity profile (services/identity.py),
    for the AI voice's prompt. A profile that can't be built is left out."""
    try:
        who = identity.prompt_block(identity.get(persona, memory, embedder))
    except Exception as e:  # never let the profile stop an answer
        logger.error(f"Identity profile for {persona['id']} unavailable: {e}")
        who = ""
    return "\n\n".join(block for block in (profile_context_block(persona["id"]), who) if block)


def answer_from_memory(query: str, persona: dict, memory, mode: str, history: list[ChatTurn],
                       n_results: int = N_RESULTS, where: dict | None = None,
                       years: tuple[int | None, int | None] = (None, None), on_token=None,
                       length: str = "normal", in_spirit: bool = False) -> dict:
    """Retrieve evidence for *query* and answer it in *mode*.

    *years*: time travel, only memories dated in that range (inclusive).
    *in_spirit*: when nothing covers the question, try an answer inferred
    from their values (services/spirit.py) before saying "I don't know".
    Returns a dict with response, sources, confidence, fallback, mode,
    faithfulness and notice. Shared by /chat and the roundtable.
    """
    topic = consent.off_limits_topic(persona, query)
    if topic:  # marked off limits by whoever gave consent: no search, nothing quoted
        return {"response": f"That's something {persona['name']}'s archive keeps private.", "sources": [],
                "faithfulness": 1.0, "confidence": "high", "fallback": True, "mode": "off_limits",
                "why": {"sources": 0}, "notice": "This topic was marked off limits for this model."}
    era = ""
    if years != (None, None):
        timeline.ensure_year_metadata(memory)
        where = timeline.combine(where, timeline.year_filter(*years))
        era = f"{years[0] or 'the start'} to {years[1] or 'today'}"
    if length == "detailed":
        n_results = max(n_results, 4)  # room for a third supporting memory
    started = time.perf_counter()
    search_text = retrieval_query(query, history, memory)
    used = used_memory_ids(query, history)
    memories = retrieve(search_text, n_results, memory, where=where, threshold=persona.get("distance_threshold"),
                        exclude=used, skip=lambda doc, meta: consent.blocked(persona, doc, meta))
    ops.record_timing("chat.retrieve", (time.perf_counter() - started) * 1000)

    # True uncertainty fallback: no memory passed the threshold, so there is
    # insufficient evidence. Answer without calling the LLM at all.
    limit = persona.get("distance_threshold")
    limit = DISTANCE_THRESHOLD if limit is None else limit
    if memories is None and used and retrieve(search_text, n_results, memory, where=where,
                                              threshold=persona.get("distance_threshold"),
                                              skip=lambda doc, meta: consent.blocked(persona, doc, meta)) is not None:
        # Everything relevant was already quoted in this conversation
        return {"response": "That's everything my records have on this.", "sources": [], "faithfulness": 0.0,
                "confidence": "low", "fallback": True, "mode": "fallback", "why": {"sources": 0},
                "notice": "Nothing new beyond the quotes above."}
    if memories is None and in_spirit and mode == "natural" and spirit.allowed(persona) and ai_voice_allowed(persona):
        inferred = spirit.answer(
            query, persona, memory, embedder,
            search=lambda _q: retrieve(search_text, n_results, memory, where=where, threshold=limit + spirit.MARGIN,
                                       exclude=used, skip=lambda doc, meta: consent.blocked(persona, doc, meta)),
            profile_block=person_profile_block(persona, memory),
            history=[turn.model_dump() for turn in history],
            style_notes=wellbeing.style_for(persona),
            use_adapter=style.adapter_for(persona),
            on_token=on_token,
            length=length,
        )
        if inferred:
            return {**inferred, "why": {"threshold_match": _match(limit), "sources": len(inferred["sources"]),
                                        "inferred": True},
                    "notice": " ".join(n for n in (inferred["notice"], f"Time travel: only memories dated {era}." if era else "") if n)}
    if memories is None:
        closest = closest_distance(search_text, memory, where)
        why = {"threshold_match": _match(limit), "best_match": None if closest is None else _match(closest), "sources": 0}
        return {"response": FALLBACK_ANSWER, "sources": [], "faithfulness": 0.0, "confidence": "low",
                "fallback": True, "mode": "fallback", "why": why,
                "notice": f"Nothing dated {era} covers this." if era else ""}

    # "natural"   : LLM answer in the persona's voice, grounded in evidence
    #               (falls back to Mix Method if the LLM fails or invents).
    # "mix_method": template-based 3-part answer, verbatim quotes, no LLM.
    # Both put the persona's own words first (anchor_first), so a biography
    # or news passage is never quoted as "what I've actually said".
    identity_card = load_mix_method_identity_card(persona["id"])
    evidence = anchor_first(memories[:4 if length == "detailed" else 3])
    notice = ""
    if mode == "natural" and not ai_voice_allowed(persona):
        mode = "mix_method"
        notice = ("AI voice is off for this model because it would send excerpts to a cloud AI service, "
                  "so these are verbatim quotes.")

    started = time.perf_counter()
    if mode == "natural":
        result = generate_natural_response(
            query=query,
            memories=evidence,
            identity_card=identity_card,
            profile_block=person_profile_block(persona, memory),
            history=[turn.model_dump() for turn in history],
            persona_name=persona["name"],
            style_notes=wellbeing.style_for(persona),
            # This person's promoted style adapter, if any (services/style.py)
            use_adapter=style.adapter_for(persona),
            embedder=embedder,
            on_token=on_token,
            length=length,
            threshold=limit,
        )
        sources = result["sources"]
    else:
        result = generate_mix_method_response(
            query=query,
            memories=evidence,  # (adjusted_dist, doc_text, metadata, raw_dist) tuples
            identity_card=identity_card,
            persona_name=persona["name"],
            include_sources=True,
            length=length,
            embedder=embedder,
            threshold=limit,
        )
        # Mix Method quotes evidence[0] (Part 1) + evidence[1:3] (Part 2), so
        # citations cover exactly the evidence used, in the same order.
        sources = [format_source_citation(meta, doc, dist) for _, doc, meta, dist in evidence]
    ops.record_timing(f"chat.generate.{mode}", (time.perf_counter() - started) * 1000)

    if result.get("notice"):  # e.g. the AI service was too slow, so these are quotes
        notice = (notice + " " if notice else "") + result["notice"]
    if era:
        notice = (notice + " " if notice else "") + f"Time travel: only memories dated {era}."
    why = {"best_match": _match(min(m[3] for m in evidence)), "threshold_match": _match(limit),
           "sources": len(evidence), "own_words": sum(voice_of(m[2]) == FIRST_PERSON for m in evidence)}
    # Natural mode scores itself against evidence + profile (its grounding guard)
    return {
        "response": result["response"],
        "sources": sources,
        "faithfulness": result.get("faithfulness", calculate_faithfulness(result["response"], evidence)),
        "confidence": result["confidence"],
        "fallback": result.get("fallback", False),
        "mode": result.get("mode", mode),
        "notice": notice,
        "why": why,
    }


# ---- Endpoints ----
def _support_reply(persona: dict, memory, started: float, query: str) -> ChatResponse:
    """Crisis language: step out of character, give helplines, generate
    nothing in the persona's voice, and keep the message out of the log."""
    message = wellbeing.support_message(query)  # Hindi or Gujarati first when they wrote in that script
    entry_id = log_qa("(withheld: support message shown)", message, [], persona=persona["id"],
                      mode="support", confidence="high", fallback=False, faithfulness=1.0,
                      latency_ms=round((time.perf_counter() - started) * 1000))
    return ChatResponse(answer=message, sources=[], faithfulness=1.0, auto_trained=False,
                        collection_size=memory.count(), confidence="high", fallback=False, mode="support",
                        notice="Out of character: support information", id=entry_id or "",
                        helplines=wellbeing.HELPLINES)


def respond(req: ChatRequest, on_token=None) -> ChatResponse:
    """Answer *req* (shared by /chat and /chat/stream). *on_token* receives
    the AI voice's draft as it is generated."""
    started = time.perf_counter()
    persona = _load_ready_persona(req.persona)
    memory = ps.get_collection(client, persona)
    years = (req.year_from, req.year_to)
    if wellbeing.needs_support(req.query):
        return _support_reply(persona, memory, started, req.query)

    # Other languages: translate the question to English (the archive's
    # language), answer as usual, translate the answer back (services/translate.py)
    query, notes = req.query, []
    asked_in = translate.detect(req.query)
    target = req.language or asked_in
    can_translate = translate.available(persona)
    if asked_in != "en":
        if not can_translate:
            return ChatResponse(
                answer=FALLBACK_ANSWER, sources=[], faithfulness=0.0, auto_trained=False, collection_size=memory.count(),
                confidence="low", fallback=True, mode="fallback", language=asked_in,
                notice=f"This model's archive is in English. Ask in English, or turn on AI voice for this model to ask in "
                       f"{translate.LANGUAGES.get(asked_in, 'your language')}.")
        try:
            query = translate.translate(req.query, "en", asked_in)
        except Exception as e:
            logger.error(f"Translating the question failed: {e}")
            raise HTTPException(status_code=503, detail="Couldn't translate the question right now; please ask in English")
        if wellbeing.needs_support(query):
            return _support_reply(persona, memory, started, req.query)
        notes.append(f"Your question was translated from {translate.LANGUAGES.get(asked_in, asked_in)} by AI.")

    # Repeated questions (quick-question buttons) come from the cache;
    # follow-ups depend on the conversation, so they never do
    cache_key = None
    if not (req.history and is_follow_up(query)):
        cache_key = answer_cache.key(persona["id"], req.query, req.mode, req.n_results, years, target, req.length, req.spirit)
        cached = answer_cache.get(cache_key)
        if cached is not None:
            entry_id = log_qa(req.query, cached["answer"], cached["sources"], persona=persona["id"], mode=cached["mode"],
                              confidence=cached["confidence"], fallback=cached["fallback"],
                              faithfulness=cached["faithfulness"], language=cached["language"], cached=True,
                              latency_ms=round((time.perf_counter() - started) * 1000))
            return ChatResponse(**{**cached, "id": entry_id or "", "collection_size": memory.count()})

    # Simple profile facts skip retrieval. A question that also asks
    # something else ("When were you born and why did you start SpaceX?")
    # gets the fact AND an answer from memory for the rest.
    basic = check_basic_info(query, persona["id"])
    if basic and not basic.get("remainder"):
        result = {**basic, "faithfulness": 1.0, "notice": ""}
    elif basic:
        rest = answer_from_memory(basic["remainder"], persona, memory, req.mode, req.history, req.n_results,
                                  years=years, on_token=on_token, length=req.length, in_spirit=req.spirit)
        result = {
            **rest,
            "response": f"{basic['response']}\n\n{rest['response']}",
            "sources": basic["sources"] + rest["sources"],
            # The fact half is certain; the rest keeps its own confidence
            "fallback": False,
        }
    else:
        result = answer_from_memory(query, persona, memory, req.mode, req.history, req.n_results,
                                    years=years, on_token=on_token, length=req.length, in_spirit=req.spirit)

    original, language = "", "en"
    if target != "en" and target in translate.LANGUAGES:
        if not can_translate:
            notes.append("Answers in other languages need AI voice turned on for this model.")
        else:
            try:
                original = result["response"]
                result["response"] = translate.translate(original, target, "en")
                language = target
                notes.append("Translated by AI from the original English (shown below); sources are untranslated.")
            except Exception as e:
                logger.error(f"Translating the answer failed: {e}")
                original = ""
                notes.append("Couldn't translate the answer, so here it is in English.")
    notice = " ".join(n for n in [result.get("notice", ""), *notes] if n)

    # Every answer is logged, refusals included: they show what the archive
    # is missing (knowledge-gap report)
    entry_id = log_qa(req.query, result["response"], result["sources"], persona=persona["id"],
                      mode=result["mode"], confidence=result["confidence"], fallback=result["fallback"],
                      faithfulness=result["faithfulness"], language=language,
                      latency_ms=round((time.perf_counter() - started) * 1000))

    response = ChatResponse(
        answer=result["response"],
        sources=result["sources"],
        faithfulness=result["faithfulness"],
        auto_trained=False,
        collection_size=memory.count(),
        confidence=result["confidence"],
        fallback=result["fallback"],
        mode=result["mode"],
        notice=notice,
        id=entry_id or "",
        language=language,
        original_answer=original,
        why=result.get("why", {}),
    )
    # Not cached: answers shaped by a passing outage (no translation, AI service down)
    if cache_key is not None and "Couldn't translate" not in notice and "AI service is slow" not in notice:
        answer_cache.put(cache_key, response.model_dump())
    return response


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """Answer a question as the chosen persona, grounded in its memories.

    Plain `def`: FastAPI runs it in a worker thread, so a slow LLM call
    doesn't freeze other requests.
    """
    return respond(req)


def _sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.post("/chat/stream")
def chat_stream(req: ChatRequest, request: Request):
    """/chat as server-sent events, so AI-voice answers appear as they're written.

    Events: "token" ({"text"}: the next piece of the draft), then "final"
    (the full /chat response, which replaces the draft: it is cleaned, and
    may be the verbatim fallback if the draft wasn't grounded), or "error".
    Unknown or unbuilt models fail as normal HTTP errors before streaming.
    If the browser goes away, generation stops (it used to run to the end,
    using up the provider for nobody).
    """
    _load_ready_persona(req.persona)
    events: queue.Queue = queue.Queue()
    gone = threading.Event()

    def on_token(text: str) -> None:
        if gone.is_set():
            raise natural_mode.StreamCancelled()
        events.put(("token", {"text": text}))

    def work():
        try:
            events.put(("final", respond(req, on_token=on_token).model_dump()))
        except HTTPException as e:
            events.put(("error", {"detail": e.detail, "status": e.status_code}))
        except Exception as e:  # never leave the client hanging
            logger.exception("chat stream failed")
            events.put(("error", {"detail": f"Answer failed: {type(e).__name__}", "status": 500}))

    async def stream():
        threading.Thread(target=work, daemon=True).start()
        try:
            while True:
                try:
                    event, data = events.get_nowait()
                except queue.Empty:
                    if await request.is_disconnected():
                        return
                    await asyncio.sleep(0.05)
                    continue
                yield _sse(event, data)
                if event in ("final", "error"):
                    return
        finally:
            gone.set()

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/consent-text")
def get_consent_text(lang: str = Query("en", pattern="^(en|hi|gu)$")):
    """The consent statements in English, Hindi or Gujarati (services/consent_text.py):
    the website shows exactly the words the consent record will keep."""
    return consent_text.texts(lang)


@app.get("/health")
def health():
    """Health check: the process is up (it may still be loading; see /ready)."""
    return {"status": "ok", "collection_size": collection.count()}


_server_lock = instance_lock.InstanceLock(instance_lock.lock_path(CHROMA_PATH))


@app.on_event("startup")
def _start():
    """Refuse to run beside another server on the same data (services/instance_lock.py),
    then load the embedding model in the background, so /ready turns true
    without waiting for someone's first question."""
    _server_lock.acquire()
    threading.Thread(target=lambda: embedder.model, name="embedder-warmup", daemon=True).start()


@app.on_event("shutdown")
def _stop():
    _server_lock.release()


@app.get("/ready")
def ready():
    """Can the server answer questions yet? 200 when the embedding model and
    Elon's memories are loaded and the settings are valid, else 503 with
    what is missing (for start scripts, monitors and the website)."""
    checks = {
        "settings": not validate_settings(config)[0],
        "embedding_model": embedder.loaded,
        "memories": collection.count() > 0,
        "website": (SITE_DIR / "index.html").exists(),
        "ai_voice": bool(config.OPENAI_API_KEY) or config.LLM_PROVIDER in ("ollama", "local"),
    }
    ok = checks["settings"] and checks["embedding_model"] and checks["memories"]
    return JSONResponse({"ready": ok, "checks": checks}, status_code=200 if ok else 503)


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
        # Voice input: local Whisper if installed, else the browser's own
        "speech_to_text": {"engine": f"faster-whisper {config.STT_MODEL}", "where": "local",
                           "available": stt.available()},
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
# Voice input: local speech-to-text
app.include_router(stt.make_router())


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


def _custom_persona(person: str) -> dict:
    """Only custom models take interview answers here, as on /personas/{id}/interview:
    these older endpoints once let anyone plant fake first-person "answers"
    (e.g. investment advice) in Elon's and the figures' shared archives."""
    persona = ps.load_persona(person)
    if persona is None:
        raise HTTPException(status_code=404, detail=f"No model called '{person}'")
    if persona.get("kind") != "custom":
        raise HTTPException(status_code=403, detail="Pretrained models can't be changed")
    return persona


@app.post("/interview/answer")
def submit_interview_answer(item: InterviewAnswer, person: str = PERSON_ID):
    """Embed and store a single interview answer in that person's memory.

    Body: {"question_id": "Q7", "answer": "...", "origin": "self"}; origin
    records who answered (the person, family, a friend...).
    """
    persona = _custom_persona(person)
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
    persona = _custom_persona(person)

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
# Pause, revoke, review date and off-limits topics for custom models
app.include_router(consent.make_router(lambda persona: delete_model(client, persona)))
# Background work (large uploads) with progress
app.include_router(jobs.make_router())
# Encrypted .chronus export / import of custom models
app.include_router(bundle.make_router(client, embedder, config.EMBEDDING_MODEL, summarize_persona))
# Adaptive interview: free-form follow-up questions
app.include_router(followups.make_router(client, embedder))
# Person model: identity profile, style adapters, switches
app.include_router(person_routes.make_router(client, embedder))
# Website forms: waitlist, contact, report a model (public, rate-limited)
app.include_router(site_forms.make_router())
# Memory browser, citation context, time-travel year counts
app.include_router(memory_routes.make_router(client, embedder))
# The uploaded file behind a memory: play the voice note, see the photo (services/originals.py)
app.include_router(originals.make_router())
# Several models answer one question (and reply to each other)
app.include_router(roundtable.make_router(_load_ready_persona, lambda p: ps.get_collection(client, p),
                                          answer_from_memory, lambda *a, **k: log_qa(*a, **k)))
# Feedback + review queue, knowledge gaps, analytics
app.include_router(insights.make_router(client, embedder))
# Optional access code (CHRONUS_ACCESS_CODE)
app.include_router(access.make_router(config))
# Admin/ops: audit log, MFA, log search/export, timings (off unless configured)
app.include_router(ops.make_router())


# ---- The website (FRONTEND/chronus-app, built with `npm run build`) ----
# Mounted last so every API route above wins; the React app uses #/ routes,
# so the server only has to serve index.html and its assets. In development
# the Vite server on :3000 serves the site instead and proxies /api here.
SITE_DIR = Path(__file__).resolve().parent.parent / "FRONTEND" / "chronus-app" / "dist"


@app.middleware("http")
async def forget_cached_answers(request, call_next):
    """Uploads, edits, deletions, builds...: cached answers may be stale now."""
    response = await call_next(request)
    if answer_cache.invalidates(request.method, request.url.path) and response.status_code < 400:
        answer_cache.clear()
    return response


@app.middleware("http")
async def revalidate_html(request, call_next):
    """Browsers must re-check index.html on every visit (assets have hashed
    names and can be cached), so an old page is never shown after an update.
    Also times every request for the ops dashboard (services/ops.py)."""
    started = time.perf_counter()
    response = await call_next(request)
    if response.headers.get("content-type", "").startswith("text/html"):
        response.headers["Cache-Control"] = "no-cache"
    ops.record_timing(ops.route_metric(request), (time.perf_counter() - started) * 1000)
    return response


# Outermost middleware: every response, refusals included (services/security_headers.py)
security_headers.install(app)

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
