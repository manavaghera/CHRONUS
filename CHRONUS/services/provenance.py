"""
Provenance helpers — "who said this?" for every retrieved memory.

The CHRONUS paper's core claim is that answers are traceable to real source
material. That only holds if the system never presents someone else's words
as the persona's own: a biographer's narration or a news article is evidence
ABOUT the person, and an LLM-written interview answer is a stand-in, not a
quote. Every memory is therefore classified into one of three voices:

    FIRST_PERSON  the persona's own words (interviews, tweets, quotes in books,
                  interview answers the person gave themselves)
    THIRD_PARTY   written about the persona by someone else (biography
                  narration, news, web articles, answers given by family)
    SYNTHESIZED   generated stand-ins (LLM-written interview answers,
                  auto-trained Q&A)
"""

from __future__ import annotations

import re

FIRST_PERSON = "first_person"
THIRD_PARTY = "third_party"
SYNTHESIZED = "synthesized"

# source_type values whose text is the persona speaking/writing
# ("personal_writing": letters, journals... uploaded to a custom model as
# written by the person; "written_about" uploads are third party;
# "writing": a famous figure's published works, figures/build_figures.py)
_FIRST_PERSON_TYPES = {"interview", "tweet", "book", "speech", "personal_writing", "writing", "voice_note"}
# interview_protocol "origin" values (who answered the interview question)
_SELF_ORIGINS = {"self", ""}
_SYNTHESIZED_ORIGINS = {"synthesized"}

_TYPE_LABELS = {
    "tweet": "Tweet",
    "interview": "Interview",
    "speech": "Speech",
    "pdf": "Book Excerpt",
    "json": "Archive",
    "csv": "Data",
    "interview_protocol": "Interview Protocol",
    "book": "Book Quote",
    "document": "Web Article",
    "video": "Video Description",
    "news": "News",
    "personal_writing": "Personal Writing",
    "writing": "Writing",
    "written_about": "Document",
    "reviewed_answer": "Reviewed past answer",
    "voice_note": "Voice note",
}


def voice_of(meta: dict) -> str:
    """Classify whose voice a memory is in (see module docstring)."""
    source_type = meta.get("source_type", "")
    if source_type == "interview_protocol":
        origin = str(meta.get("origin", "")).lower()
        if origin in _SYNTHESIZED_ORIGINS:
            return SYNTHESIZED
        return FIRST_PERSON if origin in _SELF_ORIGINS else THIRD_PARTY
    if source_type in ("auto_trained", "conversation", "reviewed_answer"):
        return SYNTHESIZED
    if source_type in _FIRST_PERSON_TYPES:
        return FIRST_PERSON
    # pdf (biography narration), news, document, video, unknown: safest is
    # to never treat unknown text as the persona's own words.
    return THIRD_PARTY


def attribution(meta: dict) -> str:
    """Short human-readable author/source for a memory, e.g. for framing
    third-party text ("Walter Isaacson's biography wrote: ...")."""
    source_type = meta.get("source_type", "")
    source_file = str(meta.get("source_file", "")).lower()
    if "isaacson" in source_file:
        return "Walter Isaacson's biography"
    if "vance" in source_file:
        return "Ashlee Vance's biography"
    if source_type == "interview_protocol":
        origin = str(meta.get("origin", "")).lower()
        if origin in _SYNTHESIZED_ORIGINS:
            return "a synthesized profile answer"
        return "the persona's own interview" if origin in _SELF_ORIGINS else f"an interview with their {origin}"
    if source_type == "written_about":
        return f"the document \"{meta.get('source_name', '')}\""
    if source_type == "reviewed_answer":
        return "a past answer a person reviewed and approved"
    return {
        "news": "a news report",
        "document": "a web article",
        "video": "a YouTube description",
        "pdf": f"the book {meta.get('source_name', '')}".strip(),
    }.get(source_type, str(meta.get("source_name") or meta.get("source_file") or "an outside source"))


# How much worse (raw cosine distance) the persona's own words may match than
# the best memory and still be quoted first. Measured on the live corpus:
# "Tell me about your childhood": own words 0.448 vs best 0.424, a good quote
# (promote); "describe your personality": 0.548 vs 0.389, an off-topic line
# about an AI's personality (don't).
ANCHOR_MARGIN = 0.10


def anchor_first(memories: list[tuple]) -> list[tuple]:
    """Move the persona's own words to the front when they match about as well.

    Mix Method quotes memories[0] first, so a close first-person memory beats
    a slightly closer biography or synthesized answer. A much weaker one does
    not: relevance wins, and the non-first-person anchor is framed honestly
    instead (mix_method._source_frame). Other memories keep retrieval order.
    """
    if not memories:
        return list(memories)
    best = min(m[3] for m in memories)
    anchor = next(
        (m for m in memories if voice_of(m[2]) == FIRST_PERSON and m[3] <= best + ANCHOR_MARGIN),
        None,
    )
    if anchor is None:
        return list(memories)
    return [anchor] + [m for m in memories if m is not anchor]


# Common words that appear in almost any text, so matching them says nothing
# about grounding (with them counted, an invented "I love pizza and
# basketball with friends" still scored as grounded in SpaceX evidence).
_FUNCTION_WORDS = frozenset(
    "with that this have they what were been from your just like really there their about "
    "would could should which when then than them will into also because very some more "
    "much being does doing here only over such these those while where other after before "
    "actually think know going thing things yeah well said make made want need even still "
    "maybe probably pretty basically obviously honestly mean kind sort lot lots something "
    "anything everything people time year years good great".split()
)


def content_words(text: str) -> set[str]:
    """Lowercased content words: longer than 3 letters, not a common function word."""
    return {w for w in re.findall(r"[a-z0-9']+", text.lower()) if len(w) > 3 and w not in _FUNCTION_WORDS}


def grounding_score(answer: str, evidence_texts: list[str]) -> float:
    """Share (0-1) of the answer's content words that appear in the evidence.

    A lexical grounding signal, not a semantic one: it drops when an answer
    drifts away from the retrieved memories, but rewording with synonyms or
    Mix Method's framing phrases lower it too.
    """
    answer_words = content_words(answer)
    if not answer_words:
        return 0.0
    evidence_words: set[str] = set()
    for text in evidence_texts:
        evidence_words |= content_words(text)
    return round(len(answer_words & evidence_words) / len(answer_words), 2)


_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def _sentences(text: str, min_words: int = 4) -> list[str]:
    return [p.strip() for p in _SENTENCE_END.split(text) if len(p.split()) >= min_words]


def semantic_support(answer: str, evidence_texts: list[str], embedder, min_similarity: float) -> float:
    """Share (0-1) of the answer's sentences that some evidence sentence backs.

    A sentence counts as supported when its embedding is within
    *min_similarity* (cosine) of at least one sentence, or whole passage, of
    the evidence. Unlike grounding_score this catches an answer that reuses
    the evidence's words for one sentence and invents the next (the
    "half-invented" 0.27-0.38 cases lexical scoring lets through), and it
    doesn't punish faithful rewording.
    """
    claims = _sentences(answer)
    if not claims:
        return 1.0
    pieces = [t for text in evidence_texts if text for t in (_sentences(text) or [text.strip()]) + [text.strip()]]
    if not pieces:
        return 0.0
    claim_vecs = embedder.encode(claims, normalize_embeddings=True)
    piece_vecs = embedder.encode(pieces, normalize_embeddings=True)
    best = (claim_vecs @ piece_vecs.T).max(axis=1)
    return round(float((best >= min_similarity).mean()), 2)


def format_source_citation(metadata: dict, doc_text: str = "", distance: float | None = None) -> dict:
    """Format a user-facing source citation from ChromaDB metadata.

    Includes ``voice`` (whose words these are), ``memory_id`` (to look the
    full memory up in ChromaDB) and ``distance`` (match strength; lower is
    closer) so clients can show and verify provenance.
    """
    source_type = metadata.get("source_type", "unknown")
    source_file = metadata.get("source_file", "unknown")
    # .title() capitalises after apostrophes ("Freedom'S Battle"); undo that
    source_name = re.sub(r"'S\b", "'s", str(metadata.get("source_name", "")).replace("_", " ").title())
    date = metadata.get("date", "")
    page = metadata.get("page")
    voice = voice_of(metadata)

    parts = [_TYPE_LABELS.get(source_type, str(source_type).title())]
    bare_file = str(source_file)
    for ext in (".csv", ".txt", ".md", ".pdf"):
        bare_file = bare_file.replace(ext, "")
    if source_name and source_name != bare_file:
        parts.append(f"from {source_name}")
    if date and date not in ("unknown", "protocol"):
        parts.append(f"({date})")
    if page:
        parts.append(f"p. {page}")
    if voice == SYNTHESIZED:
        parts.append("(synthesized, not a quote)")
    elif voice == THIRD_PARTY:
        parts.append(f"(from {attribution(metadata)}, not a quote)")

    return {
        "citation": " ".join(parts),
        "quote": doc_text[:150] + "..." if len(doc_text) > 150 else doc_text,
        "source_type": source_type,
        "source_file": source_file,
        "date": date,
        "voice": voice,
        "memory_id": metadata.get("memory_id", ""),
        "distance": round(distance, 3) if distance is not None else None,
    }
