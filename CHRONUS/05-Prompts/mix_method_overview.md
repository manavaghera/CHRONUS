# CHRONUS Mix Method — Pipeline Overview (Documentation)

> **Reference documentation only.** The Mix Method is implemented as
> **template-based Python code** in `CHRONUS/services/mix_method.py` —
> it is *not* an LLM prompt. This file documents how it works and how it
> differs from the legacy LLM prompt path.

## What it is

The core contribution of the CHRONUS paper: a deterministic, 3-part
response pipeline that **guarantees** every answer contains at least one
verbatim retrieved passage (the "provenance anchor"), eliminating the class
of hallucinations where an LLM fabricates claims with no source backing.

## The 3 parts

### Part 1 — Persona Introduction + Authentic Quote
Opens with the EXACT text of the best-matching retrieved memory, framed as
a direct quote. This is the provenance anchor: the one piece of the
response the user can trace back to a real source.

### Part 2 — Theme-Matched Explanation
Elaborates using additional retrieved memories (if any), framed by the
theme classifier's prompt fragment (`services/theme_classifier.py`).
Everything in this section comes directly from the vector store — no LLM
generation, no paraphrasing, no invented claims.

### Part 3 — Closing Signature
A persona-consistent sign-off drawn from the identity card's verified
signature phrases (`models/elon_musk/signature_phrases.txt`), selected to
match the query's theme. Theme→signature affinity mapping picks natural
pairings (e.g., `work_purpose` → "First principles, basically.").

## Design constraints

- **No LLM calls** — the entire pipeline is deterministic template
  assembly. Phrase banks (`_INTRO_FRAMES`, `_BRIDGE_SINGLE`,
  `_BRIDGE_MULTI_OPENER`, `_CONNECTOR_WORDS`, `_DEFAULT_SIGNATURES`) are
  selected by a deterministic hash of the query, so the same question
  always gets the same phrasing (reproducible, no randomness).
- **Verbatim quotes only** — memory text is never paraphrased. Long
  passages are truncated with `…` but opening words are preserved.
- **Graceful degradation** — works with 1 memory, missing identity card,
  empty signature phrases, or unknown themes.

## Confidence mapping (cosine distance in ChromaDB)

| Distance | Confidence |
|---|---|
| ≤ 0.80 | high |
| ≤ 1.20 | medium |
| ≤ 1.45 (`config.DISTANCE_THRESHOLD`) | low |
| > 1.45 | no memory passes — uncertainty fallback fires |

## How it relates to the legacy prompt path

- **Mix Method path (current):** `services/mix_method.py` assembles the
  response from real memories. No prompt template involved.
- **Legacy LLM path:** `api_server.py` → `build_system_prompt()` (see
  `system_base.md`) sends memories to Ollama and asks the model to answer
  in persona — kept for fallback/experimentation.
- **Legacy CLI path:** `06-Testing/chat_elon.py` → `build_prompt()`
  contains the full "interview roleplay" prompt (PRIME DIRECTIVE +
  SITUATIONAL FRAMING + VERBAL SIGNATURE PATTERNS + REASONING STYLE +
  BANNED WORDS), hardcoded in that script.
