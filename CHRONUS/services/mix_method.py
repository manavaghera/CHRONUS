"""
Mix Method response generator for CHRONUS.

This is the CORE CONTRIBUTION of the CHRONUS paper — a 3-part template-based
response pipeline that **guarantees** every answer contains at least one
verbatim retrieved passage (the "provenance anchor"), eliminating the class
of hallucinations where an LLM fabricates claims with no source backing.

Architecture
============

    Part 1 — Persona Introduction + Authentic Quote
        Opens with the EXACT text of the best-matching retrieved memory,
        framed as a direct quote.  This is the provenance anchor: the one
        piece of the response the user can trace back to a real source.

    Part 2 — Theme-Matched Explanation
        Elaborates using additional retrieved memories (if any), framed by
        the theme classifier's prompt fragment.  Everything in this section
        comes directly from the vector store — no LLM generation, no
        paraphrasing, no invented claims.

    Part 3 — Closing Signature
        A persona-consistent sign-off drawn from the identity card's
        verified signature phrases, selected to match the query's theme.

Design Constraints
==================

*   **No LLM calls** — the entire pipeline is deterministic template
    assembly.  The LLM is only invoked *after* this module produces its
    structured output (by the caller, e.g. `api_server.py`), and even then
    the Mix Method output can stand alone as a fully-grounded response.

*   **Verbatim quotes only** — memory text is never paraphrased.  Long
    passages are truncated with ``…`` but the opening words are always
    preserved so the user can locate the original.

*   **Graceful degradation** — works with 1 memory, missing identity card,
    empty signature phrases, or unknown themes.
"""

from __future__ import annotations

import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from services.provenance import FIRST_PERSON, SYNTHESIZED, anchor_first, attribution, content_words, voice_of
from services.theme_classifier import classify_theme, get_theme_prompt

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Distance → confidence label boundaries (cosine distance in ChromaDB),
# from the calibration run (evaluation/run_eval.py, 2026-10-06): below 0.45
# only answerable questions occurred (44 vs 0); 0.45-0.52 mixed 10 vs 3;
# 0.52 up to DISTANCE_THRESHOLD (0.58) mixed 10 vs 4.
_HIGH_CONFIDENCE_CEIL = 0.45
_MEDIUM_CONFIDENCE_CEIL = 0.52
# 0.52 up to DISTANCE_THRESHOLD is "low" but still answered.

# Maximum characters to show in a quoted passage before truncating.
_QUOTE_DISPLAY_LIMIT = 280

# Maximum characters to show in a Part 2 supplementary quote.
_SUPPLEMENTARY_QUOTE_LIMIT = 200

# ---------------------------------------------------------------------------
# Intro / bridge / closing phrase banks
# ---------------------------------------------------------------------------
# Multiple options per category so repeated calls don't sound robotic.
# A deterministic selector picks based on a hash of the query so the same
# question always gets the same phrasing (reproducible, no randomness).

_INTRO_FRAMES: list[str] = [
    "I've been pretty clear about this:",
    "As I've said before:",
    "Look, I've talked about this:",
    "Here's what I've actually said:",
    "I've addressed this publicly:",
]

_BRIDGE_SINGLE: list[str] = [
    "I also mentioned:",
    "Related to that, I've said:",
    "I've also pointed out:",
    "On a related note:",
    "Along those lines:",
]

_BRIDGE_MULTI_OPENER: list[str] = [
    "I've also talked about this a few times.",
    "There's more context here.",
    "I've addressed several angles on this.",
]

_CONNECTOR_WORDS: list[str] = [
    "And separately:",
    "I also said:",
    "Additionally:",
    "On top of that:",
]

# Closing lines: only phrases verified to occur in the persona's own words
# (identity card "signature_phrases_verified", written by
# evaluation/verify_signatures.py), and only when they relate to the
# question. The old built-in defaults ("First principles, basically.") and
# three of Elon's generated card phrases never occur in anything he said.

# Theme framing for personas without an identity card (see
# generate_mix_method_response). Plain and claim-free on purpose.
_NEUTRAL_THEME_PROMPTS: dict[str, str] = {
    "love_relationships": "About the people in my life,",
    "work_purpose": "About my work and what I was trying to do,",
    "fear_resilience": "About the hard times and how I got through them,",
    "meaning": "About what matters in the end,",
    "failure_growth": "About my mistakes and what they taught me,",
    "change_decisions": "About the big decisions I made,",
    "humanity_society": "About the wider world,",
}

# Theme → extra closing color when the identity card has relevant beliefs.
_THEME_BELIEF_KEYWORDS: dict[str, list[str]] = {
    "love_relationships": ["family", "personal", "partner"],
    "work_purpose":       ["innovation", "build", "engineer", "success"],
    "fear_resilience":     ["perseverance", "risk", "overcome", "obstacle"],
    "meaning":            ["humanity", "purpose", "consciousness"],
    "failure_growth":      ["perseverance", "mistake", "learn"],
    "change_decisions":    ["decision", "critical thinking", "calculated"],
    "humanity_society":    ["multi-planetary", "sustainable", "civilization"],
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _deterministic_pick(items: list, seed: str, offset: int = 0) -> Any:
    """Pick an item from *items* deterministically based on a string seed.

    Same seed always yields the same index, so responses are reproducible
    across identical queries without introducing randomness.
    """
    if not items:
        return None
    digest = int(hashlib.md5(seed.encode("utf-8")).hexdigest(), 16)
    return items[(digest + offset) % len(items)]


def _truncate(text: str, limit: int, *, suffix: str = "…") -> str:
    """Truncate *text* at a word boundary, preserving the start."""
    text = text.strip()
    if len(text) <= limit:
        return text
    # Cut at the last space before the limit, then append suffix
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut.rstrip(".,;:!? ") + suffix


# Speech-transcript noise removed from displayed quotes (the words stay theirs)
_FILLERS = re.compile(r"(?:,\s*)?(?<![\w'-])(?:u+m+|u+h+|e+r+m+|a+h+)(?![\w'-])(?:\s*(?:,|\.{3}|…))?", re.IGNORECASE)
_STUTTER = re.compile(r"(?<![\w'])([\w']+)(?:,?\s+\1)+(?![\w'])", re.IGNORECASE)
_STAGE = re.compile(r"\[(?:inaudible|crosstalk|unintelligible|music|applause|silence)[^\]]*\]"
                    r"|[\[(]\d{1,2}:\d{2}(?::\d{2})?[\])]|\b\d{1,2}:\d{2}:\d{2}\b", re.IGNORECASE)
_URL = re.compile(r"https?://\S+|www\.\S+")
_LEADING_HANDLES = re.compile(r"^(?:@\w+[\s,]*)+")
_KEEP_REPEATS = {"very", "no", "yes", "so", "really", "ha", "go", "bye", "that", "had", "is"}


_WORD_FIXES_PATH = Path(__file__).resolve().parent / "data" / "word_fixes.json"
_GLUED_NUMBER = re.compile(r"(\d)(and|or|to|of|in|for|the|is|was|are|with|per|from)\b")


@lru_cache(maxsize=1)
def _word_fixes() -> dict:
    """Glued words and lost PDF ligatures in the cleaned transcripts
    (evaluation/build_word_fixes.py): "pointat" -> "point at", "dierent" -> "different"."""
    try:
        return json.loads(_WORD_FIXES_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _fix_words(text: str) -> str:
    fixes = _word_fixes()
    if not fixes:
        return text

    def fix(m: re.Match) -> str:
        word = m.group(0)
        fixed = fixes.get(word.lower())
        if not fixed or not (word.islower() or word[1:].islower()):
            return word
        return fixed if word.islower() else fixed[0].upper() + fixed[1:]
    return re.sub(r"(?<![@#\w])[A-Za-z][a-z]{4,23}(?![\w@])", fix, _GLUED_NUMBER.sub(r"\1 \2", text))


def clean_for_display(text: str) -> str:
    """Remove transcript noise without changing anyone's words: "um"/"uh",
    stutters ("I I think" -> "I think"), timestamps, [inaudible], links,
    reply @handles, and extraction damage (words glued together, lost
    ff/fi ligatures). Also used by tests to compare quotes with their memory."""
    out = _fix_words(_URL.sub("", text))
    out = _LEADING_HANDLES.sub("", out.strip())
    out = _STAGE.sub("", out)
    out = _FILLERS.sub(" ", out)
    out = _STUTTER.sub(lambda m: m.group(0) if m.group(1).lower() in _KEEP_REPEATS else m.group(1), out)
    out = re.sub(r"\s+([,.!?;:])", r"\1", out)
    out = re.sub(r"([,;:])(?:\s*[,;:])+", r"\1", out)
    return re.sub(r"\s{2,}", " ", out).strip()


def _clean_quote(text: str) -> str:
    """Light cleanup of a memory passage for display as a quote.

    Collapses whitespace, strips stray markdown, speaker labels and the
    interviewer's question, and transcript noise (clean_for_display). Does
    NOT paraphrase or alter wording.
    """
    out = text.strip()
    # Collapse runs of whitespace (newlines, tabs, multi-space)
    out = re.sub(r"\s+", " ", out)
    # Interview-protocol memories are stored as "[Interview Response] Q: <question>
    # A: <answer>" — quote only the answer, never the interviewer's question.
    out = re.sub(r"^\[Interview Response\]\s*Q:.*?\sA:\s*", "", out)
    # Strip leading markdown headers
    out = re.sub(r"^#{1,4}\s*", "", out)
    # Strip speaker labels like "Elon:" or "[Elon Musk]:"
    out = re.sub(
        r"^(?:\[?(?:Elon|Elon Musk|Interviewer|Host|Q|A)\]?\s*[:–—]\s*)",
        "", out, flags=re.IGNORECASE,
    )
    return clean_for_display(out)


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])[\"'”’)]*\s+")
_QUESTION_WORDS = frozenset("why how what when who where which did do does you your is are was were if can could would should".split())


def _relevance(query: str, texts: list[str], embedder=None) -> list[float]:
    """How well each text answers *query*: cosine similarity with the
    embedder when there is one, else content-word overlap."""
    if embedder is not None and texts:
        vecs = embedder.encode([query, *texts], normalize_embeddings=True)
        return [float(v @ vecs[0]) for v in vecs[1:]]
    q = content_words(query)
    return [len(q & content_words(t)) / (len(q) or 1) for t in texts]


def focused_excerpt(text: str, query: str, limit: int, embedder=None) -> str:
    """The part of *text* that best answers *query*, within *limit* characters.

    A passage that fits is quoted whole. Otherwise the best run of 1-3 whole
    sentences is chosen (memory chunks are word windows, so the first
    sentence is often half of one, and the answer is often in the middle).
    "…" marks text left out before or after, so the quote stays verbatim.
    """
    text = text.strip()
    if len(text) <= limit:
        return text
    sentences = [x.strip() for x in _SENTENCE_SPLIT.split(text) if x.strip()]
    windows = []
    for i in range(len(sentences)):
        for size in (1, 2, 3):
            chunk = " ".join(sentences[i:i + size])
            if i + size <= len(sentences) and 30 <= len(chunk) <= limit:
                windows.append((i, i + size, chunk))
    if not windows:
        return _truncate(text, limit)
    scores = _relevance(query, [w[2] for w in windows], embedder)

    def rank(k):
        i, j, chunk = windows[k]
        starts_well = bool(re.match(r"[A-Z0-9\"'“‘(]", chunk))
        # relevance first; then prefer complete-looking sentences, then length
        return (round(scores[k], 3), starts_well, len(chunk))
    best = max(range(len(windows)), key=rank)
    i, j, chunk = windows[best]
    # A trailing "…" only where a sentence is cut; whole sentences end cleanly
    tail = "…" if j < len(sentences) and not re.search(r"[.!?][\"'”’)]*$", chunk) else ""
    return f"{'…' if i > 0 else ''}{chunk}{tail}"


def _near_duplicate(a: str, b: str, threshold: float = 0.6) -> bool:
    """Do two passages say nearly the same thing (content-word Jaccard)?"""
    wa, wb = content_words(a), content_words(b)
    if not wa or not wb:
        return False
    return len(wa & wb) / len(wa | wb) >= threshold


def theme_is_clear(theme_result: dict) -> bool:
    """Did the question actually mention the theme? Matching only question
    words ("why", "why did you") or nothing at all is a default guess, and
    framing a birthday question as "Regarding the mission..." reads wrong."""
    for keyword in theme_result.get("matched_keywords", []):
        if set(keyword.lower().split()) - _QUESTION_WORDS:
            return True
    return False


def _after_comma(theme_prompt: str, phrase: str) -> str:
    """Join a theme prompt ("About my work,") and a phrase that follows it,
    lower-casing the phrase's first letter ("Along those lines:" ->
    "along those lines:") unless it starts with "I"."""
    if theme_prompt and phrase and not re.match(r"I\b|I'", phrase):
        phrase = phrase[0].lower() + phrase[1:]
    return f"{theme_prompt} {phrase}".strip()


def _source_frame(meta: dict, first_person_frame: str, *, opening: bool) -> str:
    """Return *first_person_frame* only when the memory is the persona's own words.

    Biography narration, news and synthesized interview answers must never be
    framed as "what I've actually said" (see services/provenance.py), so they
    get an honest attribution instead.
    """
    voice = voice_of(meta)
    if voice == FIRST_PERSON:
        # Letters/journals uploaded to a custom model are private writing, so
        # frames like "I've addressed this publicly" would be false.
        if opening and meta.get("source_type") == "personal_writing":
            return "In my own words:"
        # A famous figure's published works: name the book ("As I wrote in
        # Meditations:") instead of modern interview frames ("Look, I've talked...")
        if opening and meta.get("source_type") == "writing" and meta.get("source_name"):
            return f"As I wrote in {meta['source_name']}:"
        return first_person_frame
    if voice == SYNTHESIZED:
        return "My interview profile, which is a summary rather than a direct quote, says:"
    source = attribution(meta)
    if opening:
        return f"I haven't said this in so many words, but {source} puts it this way:"
    return f"{source[0].upper()}{source[1:]} adds:"


def _format_source(doc: str, meta: dict, dist: float) -> dict:
    """Build a clean source dict from a memory tuple's components."""
    return {
        "text": _truncate(doc, 200, suffix="..."),
        "source": meta.get("source_file", "unknown"),
        "type": meta.get("source_type", "unknown"),
        "distance": round(dist, 3),
    }


def _find_belief_match(
    identity_card: dict | None, theme: str
) -> Optional[str]:
    """Find a top_belief from the identity card that relates to *theme*."""
    if not identity_card:
        return None
    beliefs = identity_card.get("top_beliefs", [])
    keywords = _THEME_BELIEF_KEYWORDS.get(theme, [])
    if not beliefs or not keywords:
        return None
    for belief in beliefs:
        # Identity cards may store top_beliefs either as plain strings or as
        # {"belief": ..., "source": ...} dicts (the production
        # models/elon_musk/identity_card.json uses dicts) — normalise both.
        belief_text = belief.get("belief", "") if isinstance(belief, dict) else belief
        if belief_text and any(kw in belief_text.lower() for kw in keywords):
            return belief_text
    return None


# ---------------------------------------------------------------------------
# Part builders
# ---------------------------------------------------------------------------

def build_part1(
    best_memory: tuple,
    persona_name: str,
    query: str,
    whole_passage: bool = False,
    limit: int = _QUOTE_DISPLAY_LIMIT,
    embedder=None,
) -> dict:
    """
    Build Part 1 — Persona Introduction + Authentic Quote.

    The provenance anchor: the part of the best-matching memory that answers
    the question (focused_excerpt), framed by whose words it is.

    Args:
        best_memory: ``(adjusted_dist, doc_text, metadata, raw_dist)``
        persona_name: Display name (e.g. ``"Elon Musk"``).
        query: The original user query (picks the excerpt and the phrasing).
        whole_passage: Quote the passage from its start (nothing else is quoted).
        limit: Maximum quote length in characters.

    Returns:
        ``{"text": "...", "quote": "...", "source": {...}}``
    """
    _, doc_text, meta, raw_dist = best_memory

    cleaned = _clean_quote(doc_text)
    # With nothing else to quote (only one memory), show the passage itself
    # rather than an excerpt, which can drop the context of the answer.
    display_quote = (_truncate(cleaned, max(limit, _QUOTE_DISPLAY_LIMIT)) if whole_passage
                     else focused_excerpt(cleaned, query, limit, embedder))

    # Pick an intro frame deterministically
    frame = _source_frame(meta, _deterministic_pick(_INTRO_FRAMES, query), opening=True)

    text = f"{frame} \"{display_quote}\""

    return {
        "text": text,
        "quote": cleaned,
        "source": _format_source(doc_text, meta, raw_dist),
    }


def build_part2(
    query: str,
    memories: list[tuple],
    theme: str,
    theme_prompt: str,
    identity_card: dict | None,
    max_extra: int = 2,
    limit: int = _SUPPLEMENTARY_QUOTE_LIMIT,
    embedder=None,
) -> dict:
    """
    Build Part 2 — Theme-Matched Explanation.

    Elaborates on the topic using additional retrieved memories (indices 1+),
    framed by the theme prompt when the question clearly has a theme.
    Everything here comes directly from the vector store, no LLM generation.
    A supporting memory that says nearly the same as one already quoted is
    skipped: it adds length, not information.

    Returns:
        ``{"text": "...", "additional_sources": [...]}``
    """
    quoted = [_clean_quote(memories[0][1])]
    additional = []
    for memory in memories[1:]:
        cleaned = _clean_quote(memory[1])
        if any(_near_duplicate(cleaned, q) for q in quoted):
            continue
        quoted.append(cleaned)
        additional.append((memory, cleaned))
        if len(additional) == max_extra:
            break
    sources: list[dict] = []

    if not additional:
        # Only 1 usable memory. Nothing grounded to add: say nothing rather
        # than filler like "that's really the key context here".
        if not identity_card:
            return {"text": "", "additional_sources": sources}
        # A belief from the identity card, clearly marked as a summary
        belief = _find_belief_match(identity_card, theme) if theme_prompt else None
        if belief:
            text = f"{theme_prompt} this connects to something my profile summarises as a core belief: \"{belief}\""
            return {"text": text, "additional_sources": sources}
        return {"text": "", "additional_sources": sources}

    parts: list[str] = []
    previous_source = None
    for k, ((_, doc, meta, dist), cleaned) in enumerate(additional):
        snippet = focused_excerpt(cleaned, query, limit, embedder)
        if k == 0:
            pick = _BRIDGE_SINGLE if len(additional) == 1 else _BRIDGE_MULTI_OPENER
            if len(additional) == 1:
                bridge = _source_frame(meta, _deterministic_pick(pick, query), opening=False)
                parts.append(f"{_after_comma(theme_prompt, bridge)} \"{snippet}\"")
            else:
                parts.append(_after_comma(theme_prompt, _deterministic_pick(pick, query)))
                parts.append(f"{_source_frame(meta, '', opening=False)} \"{snippet}\"".strip())
        else:
            frame = _source_frame(meta, _deterministic_pick(_CONNECTOR_WORDS, query, offset=k), opening=False)
            if voice_of(meta) != FIRST_PERSON and attribution(meta) == previous_source:
                frame = "And from the same source:"  # not "An interview with their family adds:" twice
            parts.append(f"{frame} \"{snippet}\"")
        previous_source = attribution(meta) if voice_of(meta) != FIRST_PERSON else None
        sources.append(_format_source(doc, meta, dist))

    return {"text": " ".join(parts), "additional_sources": sources}


def build_part3(
    identity_card: dict | None,
    theme: str = "work_purpose",
    query: str = "",
    context: str = "",
) -> dict:
    """
    Build Part 3 — Closing Signature.

    Only a phrase verified to occur in the persona's own words (identity
    card "signature_phrases_verified", see evaluation/verify_signatures.py)
    and only when it relates to the question or to what was just quoted.
    Otherwise no closing line: an unrelated catchphrase ("I'm confident it
    will succeed.") tacked onto an answer about childhood misrepresents them.

    Returns:
        ``{"text": "...", "source": {...} | None}``
    """
    verified = (identity_card or {}).get("signature_phrases_verified", [])
    topic = content_words(query)  # the question itself must touch the phrase's subject
    related = [v for v in verified if content_words(v.get("phrase", "")) & topic]
    if not related:
        return {"text": "", "source": None}
    chosen = _deterministic_pick(related, query)
    return {"text": f"As I've put it before: \"{chosen['phrase']}\"",
            "source": {"text": chosen["phrase"], "source": chosen.get("source_file", "unknown"),
                       "type": chosen.get("source_type", "interview"), "distance": None}}


# ---------------------------------------------------------------------------
# Confidence mapping
# ---------------------------------------------------------------------------

def calculate_confidence(raw_distance: float) -> str:
    """
    Map a raw cosine distance to a human-readable confidence label.

    Boundaries (shared by Mix Method and natural mode):
        distance < 0.45    → ``"high"``   — only answerable questions land here
        distance 0.45–0.52 → ``"medium"`` — grey zone, mostly answerable
        distance 0.52–0.58 → ``"low"``    — grey zone, up to DISTANCE_THRESHOLD

    Args:
        raw_distance: The raw cosine distance from ChromaDB.

    Returns:
        One of ``"high"``, ``"medium"``, or ``"low"``.
    """
    if raw_distance < _HIGH_CONFIDENCE_CEIL:
        return "high"
    if raw_distance < _MEDIUM_CONFIDENCE_CEIL:
        return "medium"
    return "low"


# ---------------------------------------------------------------------------
# Response assembler
# ---------------------------------------------------------------------------

def assemble_response(
    part1: dict,
    part2: dict,
    part3: dict,
    *,
    theme: str,
    confidence: str,
    include_sources: bool = True,
) -> dict:
    """
    Combine the 3 Mix Method parts into the final response dict.

    Layout::

        Part 1 text          ← provenance anchor quote
                              ← blank line
        Part 2 text          ← theme-framed elaboration
                              ← blank line
        Part 3 text          ← closing signature

    Args:
        part1: Output of :func:`build_part1`.
        part2: Output of :func:`build_part2`.
        part3: Output of :func:`build_part3`.
        theme: Winning theme label.
        confidence: ``"high"`` / ``"medium"`` / ``"low"``.
        include_sources: Whether to attach source provenance dicts.

    Returns:
        The complete Mix Method response dict.
    """
    full_text = "\n\n".join(p["text"] for p in (part1, part2, part3) if p["text"])

    # Deduplicate sources by source file
    sources: list[dict] = []
    seen_sources: set[str] = set()
    all_raw_sources = [part1.get("source", {})] + part2.get("additional_sources", []) + [part3.get("source") or {}]
    for src in all_raw_sources:
        if not src:
            continue
        key = src.get("source", "") + "|" + src.get("text", "")[:60]
        if key not in seen_sources:
            seen_sources.add(key)
            sources.append(src)

    return {
        "response": full_text,
        "sources": sources if include_sources else [],
        "confidence": confidence,
        "theme": theme,
        "fallback": False,
        "parts": {
            "part1_intro_quote": part1["text"],
            "part2_theme_explanation": part2["text"],
            "part3_closing_signature": part3["text"],
        },
    }


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def generate_mix_method_response(
    query: str,
    memories: list,
    identity_card: dict | None,
    persona_name: str = "Elon Musk",
    include_sources: bool = True,
    length: str = "normal",
    embedder=None,
) -> dict:
    """
    Generate a 3-part Mix Method response grounded in retrieved evidence.

    *length*: "short" (one focused quote), "normal", or "detailed" (longer
    quotes, up to three supporting memories). *embedder*: picks the most
    relevant sentences of each memory by meaning (word overlap without it).

    This is the primary public API of the module.  It orchestrates theme
    classification, the three part builders, confidence scoring, and final
    assembly into a single call.

    Args:
        query: The user's natural-language question.
        memories: List of ``(adjusted_dist, doc_text, metadata, raw_dist)``
                  tuples as returned by ``api_server.retrieve()``.
                  **Must contain at least one memory** (the caller should
                  handle the ``retrieve() → None`` case before calling).
        identity_card: Loaded identity card dict.  May be ``None``; the
                       pipeline degrades gracefully with defaults.
        persona_name: Display name for the persona (default
                      ``"Elon Musk"``).
        include_sources: Attach source provenance dicts to the output.

    Returns:
        A dict with keys::

            {
                "response":   str,         # Full assembled 3-part text
                "sources":    list[dict],   # Source provenance
                "confidence": str,          # "high" | "medium" | "low"
                "theme":      str,          # Winning theme key
                "fallback":   bool,         # Always False here
                "parts": {
                    "part1_intro_quote":       str,
                    "part2_theme_explanation": str,
                    "part3_closing_signature": str,
                },
            }

    Raises:
        ValueError: If *memories* is empty or ``None``.
    """
    # --- Guard ---
    if not memories:
        raise ValueError(
            "generate_mix_method_response() requires at least one memory. "
            "Handle the no-memory / below-threshold case upstream."
        )

    # --- Theme classification ---
    theme_result = classify_theme(query)
    theme = theme_result["theme"]
    # The classifier's theme prompts were written for Elon ("the explosions",
    # "the engineering"); personas without an identity card (custom models)
    # get neutral ones. No framing when the question never named the theme.
    if not theme_is_clear(theme_result):
        theme_prompt = ""
    else:
        theme_prompt = get_theme_prompt(theme) if identity_card else _NEUTRAL_THEME_PROMPTS.get(theme, "")

    # --- Provenance anchor must be the persona's own words when available ---
    memories = anchor_first(memories)

    # --- Confidence from the closest memory's raw distance ---
    best_memory = memories[0]
    confidence = calculate_confidence(min(m[3] for m in memories))

    # --- Build the three parts ---
    limits = {"short": (220, 0, 0), "normal": (_QUOTE_DISPLAY_LIMIT, 2, _SUPPLEMENTARY_QUOTE_LIMIT),
              "detailed": (420, 3, 320)}
    quote_limit, max_extra, extra_limit = limits.get(length, limits["normal"])
    part1 = build_part1(best_memory, persona_name, query, whole_passage=len(memories) == 1,
                        limit=quote_limit, embedder=embedder)
    if max_extra:
        part2 = build_part2(query, memories, theme, theme_prompt, identity_card, max_extra=max_extra,
                            limit=extra_limit, embedder=embedder)
    else:
        part2 = {"text": "", "additional_sources": []}
    part3 = build_part3(identity_card, theme=theme, query=query, context=part1["quote"]) if length != "short" \
        else {"text": "", "source": None}

    # --- Assemble ---
    return assemble_response(
        part1, part2, part3,
        theme=theme,
        confidence=confidence,
        include_sources=include_sources,
    )


# ---------------------------------------------------------------------------
# Standalone demo / smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json

    # Simulated memories as returned by api_server.retrieve()
    # Format: (adjusted_dist, doc_text, metadata_dict, raw_dist)
    mock_memories = [
        (
            0.35,
            (
                "The goal of SpaceX is to make humanity a multi-planetary species. "
                "We need a self-sustaining city on Mars. That's the whole point — "
                "to ensure the long-term survival of consciousness."
            ),
            {
                "source_file": "lex-fridman-interview-2021.md",
                "source_type": "interview",
                "source_name": "Lex Fridman Interview 2021",
                "importance_score": 5,
            },
            0.50,
        ),
        (
            0.48,
            (
                "If we can make the cost per ton to Mars less than a million dollars, "
                "then I think we can build a self-sustaining city there. Starship is "
                "the architecture that gets us there."
            ),
            {
                "source_file": "shareholder-meeting-2022.md",
                "source_type": "interview",
                "source_name": "Shareholder Meeting 2022",
                "importance_score": 4,
            },
            0.63,
        ),
        (
            0.60,
            (
                "Mars is about backing up the biosphere. Earth has had five mass "
                "extinction events. People don't appreciate how rare and precious "
                "consciousness is."
            ),
            {
                "source_file": "joe-rogan-podcast-2020.md",
                "source_type": "interview",
                "source_name": "Joe Rogan Podcast 2020",
                "importance_score": 4,
            },
            0.75,
        ),
    ]

    mock_identity_card = {
        "name": "Elon Musk",
        "signature_phrases": [
            "Make humanity a multi-planetary species",
            "Sustainable energy is the future",
            "Innovation is key to success",
        ],
        "top_beliefs": [
            "The importance of innovation and taking risks to achieve success.",
            "The need for humanity to become a multi-planetary species.",
            "The potential of artificial intelligence to revolutionize industries.",
            "The need for sustainable energy solutions to combat climate change.",
            "The value of perseverance and hard work in overcoming obstacles.",
        ],
        "communication": {
            "formality": "Informal",
            "patterns": ["Direct", "Conversational", "Storytelling"],
        },
    }

    query = "What's the mission of SpaceX?"
    result = generate_mix_method_response(
        query=query,
        memories=mock_memories,
        identity_card=mock_identity_card,
        persona_name="Elon Musk",
    )

    print("=" * 72)
    print("CHRONUS Mix Method — Demo Output")
    print("=" * 72)
    print(f"\nQuery: \"{query}\"")
    print(f"Theme: {result['theme']}")
    print(f"Confidence: {result['confidence']}")
    print()
    print("--- FULL RESPONSE ---")
    print(result["response"])
    print()
    print("--- PARTS BREAKDOWN ---")
    for key, val in result["parts"].items():
        print(f"\n  [{key}]")
        print(f"  {val}")
    print()
    print("--- SOURCES ---")
    for src in result["sources"]:
        print(f"  • {src['source']} ({src['type']}) — distance {src['distance']}")
        print(f"    \"{src['text']}\"")
    print()
    print("--- RAW JSON ---")
    print(json.dumps(result, indent=2))
