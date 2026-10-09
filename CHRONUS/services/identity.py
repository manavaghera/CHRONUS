"""
Identity profile: who a person is, in their own words.

A short sheet of the person (what they believe, how they are, what shaped
them, the people who matter, what they love, how they talk) that goes into
the AI voice's prompt, so answers sound like them even when a question's
evidence is thin, and so "in their spirit" answers (services/spirit.py) have
something real to stand on. Every line is one of their own sentences linked
to the memory it came from: nothing here is written by an AI.

Where lines come from:
* interview answers (personal models), by the interview's six dimensions;
  answers a family member gave are kept but labelled as about them, and
  LLM-written stand-in answers are never used
* a meaning search of their own words for each section (all models; the only
  source for the pretrained figures), keeping close, first-person sentences
* public-record facts (pretrained figures, models/<id>/profile.json); shown
  on the profile but left out of the prompt, which already has them

Rebuilt when the archive changes (its memory count differs from the build);
lines a reviewer hid stay hidden across rebuilds. Stored as identity.json in
the model's folder.

    python -m services.identity elon_musk      # build or refresh one model
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
from datetime import datetime, timezone

from services import personas as ps
from services.mix_method import TRANSCRIPT_TYPES, clean_for_display, without_host_questions
from services.profile import _public_record
from services.provenance import FIRST_PERSON, SYNTHESIZED, voice_of

FILE = "identity.json"
VERSION = 1

# key -> (heading, interview dimension, meaning-search probes). Probes are
# sentence openings: a model of meaning matches "I love all my kids" to "My
# kids" far better than to an abstract "the people in my life".
SECTIONS = {
    "values": ("What I believe", "beliefs_values",
               ["The principle I believe in most is", "What matters most in life to me is", "I care about", "My goal is"]),
    "temperament": ("How I am", "personality",
                    ["I am the kind of person who", "When things go wrong I", "I work hard because", "My habit is"]),
    "shaped": ("What shaped me", "core_memories",
               ["When I was a kid I", "Growing up I", "The hardest thing I ever went through was"]),
    "people": ("People who matter", "relationships",
               ["My mother", "My father", "My kids", "My wife", "My husband", "My best friend"]),
    "loves": ("What I love", "passions",
              ["I love doing", "What I enjoy most is", "In my free time I"]),
    "voice": ("How I talk", "voice_communication", []),  # interview answers only: a search can't find style
}
DIMENSION_SECTION = {dim: key for key, (_, dim, _) in SECTIONS.items()}

MAX_LINES = 4        # per section on the profile
PROMPT_LINES = 3     # per section in the AI voice's prompt
MAX_WORDS = 40       # per line
MIN_SEARCH_SCORE = 0.40  # sentence-to-probe cosine for a searched line
SEARCH_RESULTS = 25  # memories per probe
DUPLICATE = 0.9      # cosine above which two lines say the same thing

_FIRST_PERSON = re.compile(r"\b(I|I'm|I’m|I've|I’ve|I'd|I’d|my|me|mine)\b", re.I)
_FILLERS = re.compile(r"\b(you know|I mean|uh|um|sort of|kind of)\b", re.I)
# Speech that stutters or restarts ("what what's wrong", "that's how I that's
# how I define") reads badly as a profile line, however true it is
_REPEAT = re.compile(r"\b(\w+)\s+\1\b|\b(\w+\W+\w+)\b.*\b\2\b", re.I)


def _usable(sentence: str, spoken: bool) -> bool:
    """A searched sentence worth putting on the profile."""
    n = len(sentence.split())
    if not (7 <= n <= MAX_WORDS and _FIRST_PERSON.search(sentence)):
        return False
    if "?" in sentence or "http" in sentence or "@" in sentence:
        return False
    fillers = len(_FILLERS.findall(sentence))
    return fillers == 0 and not _REPEAT.search(sentence) if spoken else fillers < 2
_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def _clip(text: str, max_words: int = MAX_WORDS) -> str:
    words = text.split()
    return text if len(words) <= max_words else " ".join(words[:max_words]).rstrip(",;:") + "…"


def _answer_part(doc: str) -> str:
    """'[Interview Response] Q: ... A: ...' -> the answer."""
    match = re.search(r"\bA:\s*(.*)$", doc, re.S)
    return (match.group(1) if match else doc).strip()


def _line(section: str, text: str, meta: dict, voice: str, score: float | None = None, question: str = "") -> dict:
    memory_id = str(meta.get("memory_id", ""))
    line = {
        "id": hashlib.md5(f"{memory_id}|{text}".encode("utf-8")).hexdigest()[:10],
        "section": section,
        "text": text,
        "memory_id": memory_id,
        "source": meta.get("source_name") or meta.get("source_file") or "",
        "voice": voice,  # "own" | "about" | "public"
    }
    if question:
        line["question"] = question
    if score is not None:
        line["score"] = round(float(score), 3)
    return line


def _interview_lines(collection, embedder) -> list[dict]:
    """Lines from interview and follow-up answers: up to MAX_WORDS of each answer."""
    got = collection.get(where={"source_type": "interview_protocol"}, include=["documents", "metadatas"])
    lines, unplaced = [], []
    for doc, meta in zip(got["documents"], got["metadatas"]):
        voice = voice_of(meta)
        if voice == SYNTHESIZED:  # an LLM's stand-in answer is not who they are
            continue
        answer = clean_for_display(_answer_part(doc))
        text, words = [], 0
        for sentence in _sentences(answer):
            if words and words + len(sentence.split()) > MAX_WORDS:
                break
            text.append(sentence)
            words += len(sentence.split())
        if not text:
            continue
        question = str(meta.get("question") or meta.get("parent_text") or "")
        line = _line(DIMENSION_SECTION.get(meta.get("dimension"), ""), _clip(" ".join(text)), meta,
                     "own" if voice == FIRST_PERSON else "about", question=question)
        (lines if line["section"] else unplaced).append(line)
    if unplaced and embedder is not None:  # follow-ups have no dimension: put each where it fits best
        probes = [(key, p) for key, (_, _, ps_) in SECTIONS.items() for p in ps_]
        pv = embedder.encode([p for _, p in probes], normalize_embeddings=True)
        lv = embedder.encode([line["text"] for line in unplaced], normalize_embeddings=True)
        for line, scores in zip(unplaced, lv @ pv.T):
            line["section"] = probes[int(scores.argmax())][0]
            lines.append(line)
    return lines


def _searched_lines(collection, embedder) -> list[dict]:
    """Their own first-person sentences closest to each section's probes."""
    probes = [(key, p) for key, (_, _, ps_) in SECTIONS.items() for p in ps_]
    if not probes or collection.count() == 0:
        return []
    pv = embedder.encode([p for _, p in probes], normalize_embeddings=True)
    raw = collection.query(query_embeddings=pv.tolist(), n_results=min(SEARCH_RESULTS, collection.count()),
                           include=["documents", "metadatas"])
    candidates: dict[str, dict] = {}
    for docs, metas in zip(raw["documents"], raw["metadatas"]):
        for doc, meta in zip(docs, metas):
            if voice_of(meta) != FIRST_PERSON or meta.get("source_type") == "interview_protocol":
                continue
            spoken = meta.get("source_type") in TRANSCRIPT_TYPES
            text = without_host_questions(doc) if spoken else doc
            for sentence in _sentences(clean_for_display(text)):
                if _usable(sentence, spoken):
                    candidates.setdefault(sentence, meta)
    if not candidates:
        return []
    sentences = list(candidates)
    scores = embedder.encode(sentences, normalize_embeddings=True) @ pv.T
    lines = []
    for sentence, row in zip(sentences, scores):
        best = int(row.argmax())  # each sentence goes to the one section it fits best
        if row[best] >= MIN_SEARCH_SCORE:
            lines.append(_line(probes[best][0], sentence, candidates[sentence], "own", score=row[best]))
    return lines


def _public_lines(persona_id: str) -> list[dict]:
    record = _public_record(persona_id) or {}
    keep = ("Born", "Died", "Occupation", "Companies", "Education", "Lives in", "Hobbies")
    meta = {"source_name": "Public record (Wikidata)", "memory_id": "profile"}
    return [_line("about", f"{label}: {value}", meta, "public")
            for label, value in record.get("facts", {}).items() if label in keep]


def _select(lines: list[dict], embedder) -> list[dict]:
    """Up to MAX_LINES per section: interview answers first (asked directly),
    then the best-scoring searched sentences, without near-duplicates."""
    ordered = sorted(lines, key=lambda ln: (ln["voice"] == "public", "question" not in ln, -ln.get("score", 1.0)))
    vectors = (embedder.encode([ln["text"] for ln in ordered], normalize_embeddings=True)
               if embedder is not None and ordered else None)
    chosen, kept_vectors, per_section, seen_memory = [], [], {}, set()
    for i, line in enumerate(ordered):
        cap = 8 if line["voice"] == "public" else MAX_LINES
        if per_section.get(line["section"], 0) >= cap:
            continue
        key = (line["memory_id"], line["section"])
        if line["voice"] != "public" and key in seen_memory:
            continue
        if vectors is not None and kept_vectors and max(float(vectors[i] @ v) for v in kept_vectors) > DUPLICATE:
            continue
        chosen.append(line)
        per_section[line["section"]] = per_section.get(line["section"], 0) + 1
        seen_memory.add(key)
        if vectors is not None:
            kept_vectors.append(vectors[i])
    order = ["about", *SECTIONS]
    return sorted(chosen, key=lambda ln: order.index(ln["section"]) if ln["section"] in order else len(order))


def _path(persona: dict):
    return ps._folder(persona) / FILE


def _lock(persona_id: str) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(persona_id, threading.Lock())


def _read(persona: dict) -> dict | None:
    path = _path(persona)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def build(persona: dict, collection, embedder) -> dict:
    """(Re)build *persona*'s identity profile from its archive and save it."""
    with _lock(persona["id"]):
        previous = _read(persona) or {}
        lines = _interview_lines(collection, embedder) + _searched_lines(collection, embedder)
        if persona.get("kind") == "pretrained":
            lines += _public_lines(persona["id"])
        identity = {
            "version": VERSION,
            "persona": persona["id"],
            "built_at": _now(),
            "memory_count": collection.count(),
            "hidden": [h for h in previous.get("hidden", [])],  # a reviewer's choices survive rebuilds
            "lines": _select(lines, embedder),
        }
        path = _path(persona)
        path.parent.mkdir(parents=True, exist_ok=True)
        ps.atomic_write_text(path, json.dumps(identity, ensure_ascii=False, indent=1))
        return identity


def get(persona: dict, collection, embedder) -> dict:
    """The saved profile, rebuilt first if the archive changed since."""
    identity = _read(persona)
    if identity is None or identity.get("version") != VERSION or identity.get("memory_count") != collection.count():
        identity = build(persona, collection, embedder)
    return identity


def set_hidden(persona: dict, line_id: str, hidden: bool) -> dict:
    """Hide a line from the profile and the prompt (or show it again)."""
    with _lock(persona["id"]):
        identity = _read(persona)
        if identity is None or not any(ln["id"] == line_id for ln in identity["lines"]):
            raise KeyError(line_id)
        rest = [h for h in identity.get("hidden", []) if h != line_id]
        identity["hidden"] = rest + [line_id] if hidden else rest
        ps.atomic_write_text(_path(persona), json.dumps(identity, ensure_ascii=False, indent=1))
        return identity


def visible_lines(identity: dict | None) -> list[dict]:
    if not identity:
        return []
    hidden = set(identity.get("hidden", []))
    return [ln for ln in identity.get("lines", []) if ln["id"] not in hidden]


def prompt_block(identity: dict | None, max_per_section: int = PROMPT_LINES) -> str:
    """The 'WHO YOU ARE' block for the AI voice's system prompt ("" if empty).

    Public-record lines are left out: profile.profile_context_block() already
    gives the model those facts."""
    groups: dict[str, list[str]] = {}
    for line in visible_lines(identity):
        if line["voice"] == "public" or line["section"] not in SECTIONS:
            continue
        items = groups.setdefault(line["section"], [])
        if len(items) < max_per_section:
            said = "" if line["voice"] == "own" else " (said about you by someone who knew you)"
            items.append(f'- "{line["text"]}"{said}')
    if not groups:
        return ""
    out = ["WHO YOU ARE (lines from your own words and interview answers. Let them shape your tone and what you care about. "
           "You may use them in an answer; a sentence built only from them needs no evidence number.)"]
    for key, items in groups.items():
        out += [f"{SECTIONS[key][0]}:", *items]
    return "\n".join(out)


if __name__ == "__main__":
    import sys

    import chromadb
    import pyarrow.dataset  # noqa: F401  (before torch on Windows)
    from sentence_transformers import SentenceTransformer

    from config import config

    client = chromadb.PersistentClient(path=config.CHROMA_PATH)
    embedder = SentenceTransformer(config.EMBEDDING_MODEL)
    for persona_id in sys.argv[1:] or [config.DEFAULT_PERSONA]:
        persona = ps.load_persona(persona_id, any_owner=True)
        if persona is None:
            sys.exit(f"No model called '{persona_id}'")
        built = build(persona, ps.get_collection(client, persona), embedder)
        print(f"{persona_id}: {len(built['lines'])} lines -> {_path(persona)}")
        for line in built["lines"]:
            print(f"  [{line['section']}/{line['voice']}] {line['text'][:110]}")
