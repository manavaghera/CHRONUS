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
import re
from typing import Any, Optional

from services.provenance import FIRST_PERSON, SYNTHESIZED, anchor_first, attribution, voice_of
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

_DEFAULT_SIGNATURES: list[str] = [
    "That's essentially the core of it.",
    "First principles, basically.",
    "It's not that complicated actually.",
    "That's the fundamental thing people miss.",
    "Pretty straightforward when you think about it.",
]

# Theme → indices into _DEFAULT_SIGNATURES that feel most natural.
_THEME_SIGNATURE_AFFINITY: dict[str, list[int]] = {
    "love_relationships": [0, 4],
    "work_purpose":       [1, 3],
    "fear_resilience":     [0, 3],
    "meaning":            [2, 3],
    "failure_growth":      [0, 4],
    "change_decisions":    [1, 4],
    "humanity_society":    [3, 0],
}

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


def _clean_quote(text: str) -> str:
    """Light cleanup of a memory passage for display as a quote.

    Collapses whitespace, strips stray markdown, and normalises quotes.
    Does NOT paraphrase or alter wording — only cosmetic.
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
    return out.strip()


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


def _extract_best_sentence(text: str, limit: int = _QUOTE_DISPLAY_LIMIT) -> str:
    """Extract the strongest single sentence from a passage.

    Heuristic: prefer the first sentence that is ≥ 40 chars (likely a
    complete thought) and ≤ *limit* chars, and that starts like a sentence
    (capital letter, quote or digit): memory chunks are overlapping word
    windows, so the first "sentence" is often the tail of a cut one ("of
    nature in general, however; ..."). All-lowercase transcripts have no
    such sentence and keep the plain length rule.  If none qualifies, fall
    back to truncating the full text.
    """
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip())]
    fitting = [s for s in sentences if 40 <= len(s) <= limit]
    starts_well = [s for s in fitting if re.match(r"[A-Z0-9\"'“‘(]", s)]
    if starts_well or fitting:
        return (starts_well or fitting)[0]
    # Fallback: return the beginning of the passage, truncated
    return _truncate(text, limit)


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
) -> dict:
    """
    Build Part 1 — Persona Introduction + Authentic Quote.

    The provenance anchor: opens with the EXACT text of the best-matching
    retrieved memory framed as a direct first-person quote.

    Args:
        best_memory: ``(adjusted_dist, doc_text, metadata, raw_dist)``
        persona_name: Display name (e.g. ``"Elon Musk"``).
        query: The original user query (used for deterministic phrase
               selection).

    Returns:
        ``{"text": "...", "quote": "...", "source": {...}}``
    """
    _, doc_text, meta, raw_dist = best_memory

    cleaned = _clean_quote(doc_text)
    # With nothing else to quote (only one memory), show the passage itself
    # rather than its first sentence, which can drop the actual answer.
    display_quote = (_truncate(cleaned, _QUOTE_DISPLAY_LIMIT) if whole_passage
                     else _extract_best_sentence(cleaned, limit=_QUOTE_DISPLAY_LIMIT))

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
) -> dict:
    """
    Build Part 2 — Theme-Matched Explanation.

    Elaborates on the topic using additional retrieved memories (indices 1+),
    framed by the theme classifier's prompt fragment.  Everything here comes
    directly from the vector store — **no LLM generation**.

    Args:
        query: The original user query.
        memories: Full list of ``(adj, doc, meta, dist)`` tuples from
                  ``retrieve()``.
        theme: Winning theme key from ``classify_theme()``.
        theme_prompt: Fragment from ``get_theme_prompt(theme)``.
        identity_card: Loaded identity card dict (may be ``None``).

    Returns:
        ``{"text": "...", "additional_sources": [...]}``
    """
    additional = memories[1:3]  # At most 2 supplementary memories
    sources: list[dict] = []

    if not additional:
        # Only 1 memory was retrieved — keep Part 2 minimal.
        # No identity card (custom personas): nothing grounded to add, and
        # filler like "that's really the key context here" says nothing.
        if not identity_card:
            return {"text": "", "additional_sources": sources}
        # Pull a relevant belief from the identity card if possible.
        belief = _find_belief_match(identity_card, theme)
        if belief:
            text = f"{theme_prompt} this connects to something I deeply believe: \"{belief}\""
        else:
            text = f"{theme_prompt} that's really the key context here."
        return {"text": text, "additional_sources": sources}

    if len(additional) == 1:
        # One supplementary memory
        _, doc, meta, dist = additional[0]
        cleaned = _clean_quote(doc)
        snippet = _truncate(cleaned, _SUPPLEMENTARY_QUOTE_LIMIT)
        bridge = _source_frame(meta, _deterministic_pick(_BRIDGE_SINGLE, query), opening=False)
        text = f"{_after_comma(theme_prompt, bridge)} \"{snippet}\""
        sources.append(_format_source(doc, meta, dist))

    else:
        # Two supplementary memories
        opener = _deterministic_pick(_BRIDGE_MULTI_OPENER, query)
        parts = [_after_comma(theme_prompt, opener)]

        _, doc1, meta1, dist1 = additional[0]
        cleaned1 = _clean_quote(doc1)
        snippet1 = _truncate(cleaned1, _SUPPLEMENTARY_QUOTE_LIMIT)
        parts.append(f"{_source_frame(meta1, '', opening=False)} \"{snippet1}\"".strip())
        sources.append(_format_source(doc1, meta1, dist1))

        _, doc2, meta2, dist2 = additional[1]
        cleaned2 = _clean_quote(doc2)
        snippet2 = _truncate(cleaned2, _SUPPLEMENTARY_QUOTE_LIMIT)
        connector = _source_frame(meta2, _deterministic_pick(_CONNECTOR_WORDS, query), opening=False)
        parts.append(f"{connector} \"{snippet2}\"")
        sources.append(_format_source(doc2, meta2, dist2))

        text = " ".join(parts)

    return {"text": text, "additional_sources": sources}


def build_part3(
    identity_card: dict | None,
    theme: str = "work_purpose",
    query: str = "",
) -> dict:
    """
    Build Part 3 — Closing Signature.

    Selects a persona-consistent closing line from the identity card's
    ``signature_phrases``.  Falls back to a theme-appropriate default if
    the card is missing or has no phrases.

    Args:
        identity_card: Loaded identity card dict (may be ``None``).
        theme: Winning theme key, used to bias signature selection.
        query: Original query for deterministic pick seeding.

    Returns:
        ``{"text": "..."}``
    """
    # 1. Try identity card signature phrases
    card_phrases = []
    if identity_card:
        card_phrases = identity_card.get("signature_phrases", [])

    if card_phrases:
        # Try to find a phrase that matches the theme's keywords
        theme_kws = _THEME_BELIEF_KEYWORDS.get(theme, [])
        themed_phrases = [
            p for p in card_phrases
            if any(kw in p.lower() for kw in theme_kws)
        ]
        if themed_phrases:
            phrase = _deterministic_pick(themed_phrases, query)
            return {"text": phrase}
        # No theme match — pick any card phrase
        phrase = _deterministic_pick(card_phrases, query)
        return {"text": phrase}

    # No identity card at all (custom personas): no closing line. The built-in
    # defaults ("First principles, basically.") would put words in the mouth of
    # someone who never said them.
    if not identity_card:
        return {"text": ""}

    # 2. Fall back to built-in defaults, biased by theme
    affinities = _THEME_SIGNATURE_AFFINITY.get(theme, [0])
    preferred = [_DEFAULT_SIGNATURES[i] for i in affinities if i < len(_DEFAULT_SIGNATURES)]
    if preferred:
        return {"text": _deterministic_pick(preferred, query)}

    return {"text": _deterministic_pick(_DEFAULT_SIGNATURES, query)}


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
    all_raw_sources = [part1.get("source", {})] + part2.get("additional_sources", [])
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
) -> dict:
    """
    Generate a 3-part Mix Method response grounded in retrieved evidence.

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
    # get neutral ones.
    theme_prompt = get_theme_prompt(theme) if identity_card else _NEUTRAL_THEME_PROMPTS.get(theme, "")

    # --- Provenance anchor must be the persona's own words when available ---
    memories = anchor_first(memories)

    # --- Confidence from the closest memory's raw distance ---
    best_memory = memories[0]
    confidence = calculate_confidence(min(m[3] for m in memories))

    # --- Build the three parts ---
    part1 = build_part1(best_memory, persona_name, query, whole_passage=len(memories) == 1)
    part2 = build_part2(query, memories, theme, theme_prompt, identity_card)
    part3 = build_part3(identity_card, theme=theme, query=query)

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
