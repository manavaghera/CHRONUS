"""
Natural response mode — an LLM answers in the persona's voice, grounded in
retrieved evidence. Mix Method (services/mix_method.py) is the automatic
fallback whenever the LLM call fails.

Voice design (why answers used to sound AI-written): the old prompt told the
model "do NOT copy the evidence, rephrase it", so it threw away his words and
wrote generic ones ("ensuring the long-term survival of consciousness").
Now the model is told to reuse the persona's own phrasing from the evidence
and only tidy it, every evidence line says whose words it is, and
post_process.scrub() strips leftover AI habits. The prompt deliberately
contains no dashes: models copy them. (Verbatim style-example quotes were
tried and removed: free models pasted them into unrelated answers.)
"""

from __future__ import annotations

import json
import logging
import re
from typing import Callable

import requests

from config import config
from services.mix_method import calculate_confidence, clean_for_display, generate_mix_method_response
from services.post_process import scrub
from services.provenance import (
    FIRST_PERSON,
    SYNTHESIZED,
    anchor_first,
    attribution,
    format_source_citation,
    grounding_score,
    semantic_support,
    voice_of,
)

logger = logging.getLogger("chronus")

# Ceiling for completions. The prompt asks for 1-3 sentences, but reasoning
# models spend tokens thinking first and those count against this limit:
# 150 produced empty or cut-off replies like "I mean, the exact". Reasoning is
# disabled for OpenRouter below; this is headroom for models that think anyway.
NATURAL_MAX_TOKENS = 1000
# The local model doesn't "think" first, so a short ceiling is enough and
# keeps generation fast on a laptop GPU.
LOCAL_MAX_TOKENS = 300

# Prior chat turns sent to the LLM so follow-ups ("which state?") make sense.
MAX_HISTORY_TURNS = 6

# The prompt asks for 1-3 sentences, but free models often run on, stitching
# in loosely related evidence ("...My British grandmother, Cora..."). Enforced
# here, with one sentence of slack.
MAX_ANSWER_SENTENCES = 4

# Per-persona style lives in persona.json ("style_notes"); this is the fallback.
# Describe a style, don't list favourite words: a list of Elon's most frequent
# words ("I think", "actually", "probably") made the model open every sentence
# with one of them, a new robotic pattern.
_DEFAULT_STYLE_NOTES = (
    "Talk like a person in a conversation, not like an essay: plain words and "
    "concrete details instead of big abstract phrases."
)


def _usable_llm_text(text: str | None, truncated: bool) -> str:
    """Validate raw LLM output, raising ValueError if it can't be used.

    Providers can return null/empty content (e.g. a reasoning model that
    spent its whole token budget thinking) or stop mid-sentence at the token
    limit. Raising lets generate_natural_response() fall back to Mix Method
    instead of crashing in scrub() or returning half a sentence.
    """
    text = (text or "").strip()
    if truncated:
        # Keep only complete sentences: half a sentence is worse than none.
        last = max(text.rfind("."), text.rfind("!"), text.rfind("?"))
        text = text[: last + 1] if last > 0 else ""
    if not text:
        reason = "hit the token limit" if truncated else "returned empty content"
        raise ValueError(f"LLM {reason}")
    return text


_MARKERS_AFTER_STOP = re.compile(r"([.!?])\s*((?:\[\d{1,2}\]\s*)+)")
_MARKER = re.compile(r"\s*\[(\d{1,2})\]")


def clean_citations(text: str, n_sources: int) -> str:
    """Keep only valid [n] evidence markers (1..n_sources), placed before the
    sentence's full stop, so sentence splitting and display stay clean.
    "Mars matters. [1] [9] Next" -> "Mars matters [1]. Next"."""
    text = _MARKERS_AFTER_STOP.sub(lambda m: " " + "".join(f"[{d}]" for d in re.findall(r"\d+", m.group(2))) + m.group(1) + " ", text)

    def keep(m: re.Match) -> str:
        return f" [{m.group(1)}]" if 1 <= int(m.group(1)) <= n_sources else ""
    text = _MARKER.sub(keep, text)
    text = re.sub(r"(\[\d+\])(?:\s*\1)+", r"\1", text)  # "[1] [1]" -> "[1]"
    return re.sub(r"\s+([.!?,])", r"\1", re.sub(r"\s{2,}", " ", text)).strip()


def strip_citations(text: str) -> str:
    """Text without [n] markers (for reading aloud or scoring)."""
    return re.sub(r"\s{2,}", " ", _MARKER.sub("", text)).strip()


def _evidence_line(index: int, doc: str, meta: dict, citation: str) -> str:
    """One evidence entry, labelled with whose words it is."""
    voice = voice_of(meta)
    if voice == FIRST_PERSON:
        label = f"YOUR OWN WORDS ({citation})"
    elif voice == SYNTHESIZED:
        label = f"SYNTHESIZED SUMMARY, NOT A QUOTE ({attribution(meta)})"
    else:
        label = f"ABOUT YOU, WRITTEN BY SOMEONE ELSE ({attribution(meta)})"
    return f"[{index}] {label}:\n{doc.strip()}"


# Sentences asked for, and the cap enforced (one sentence of slack), per length
LENGTHS = {"short": ("One or two sentences", 2), "normal": ("One to three sentences", MAX_ANSWER_SENTENCES),
           "detailed": ("Three to six sentences", 7)}


def build_system_prompt(
    persona_name: str, evidence_block: str, profile_block: str = "", style_notes: str | None = None,
    length: str = "normal",
) -> str:
    """Assemble the natural-mode system prompt (no dashes on purpose)."""
    sentences = LENGTHS.get(length, LENGTHS["normal"])[0]
    return f"""You are {persona_name}, talking in a live conversation. Answer the user's question.

HOW TO ANSWER
1. Answer the actual question, building the answer from YOUR OWN WORDS in the evidence. Reuse your actual phrases, examples, numbers and jokes where they fit, and only tidy them up: drop fillers like "um", "uh" and "you know", fix run-together or broken words, and join fragments into sentences. Do not just paste unrelated lines together.
2. Evidence marked ABOUT YOU was written by someone else. You can use its facts, but never present its wording as something you said.
3. Evidence marked SYNTHESIZED is a generated summary. Use it for facts only, not for phrasing.
4. Do not add facts, opinions, numbers or examples that are not in the evidence or the profile. If the evidence does not really answer the question, say that briefly, in your own voice.
5. {sentences}, spoken style. Start with the answer itself. No intro and no wrap-up line that sums things up.
6. Never use dashes of any kind, and never use the words "crucial", "ensuring", "pivotal", "delve", "testament", "landscape" or "journey".
7. End each sentence, before its full stop, with the number of the evidence it comes from in square brackets, like [1] or [2]. Only use numbers shown in EVIDENCE.

HOW YOU TALK
{style_notes or _DEFAULT_STYLE_NOTES}

{profile_block}

EVIDENCE
{evidence_block}"""


def _clean_history(history: list[dict] | None) -> list[dict]:
    """Keep the last MAX_HISTORY_TURNS well-formed user/assistant turns."""
    turns = [
        {"role": h["role"], "content": str(h["content"])}
        for h in (history or [])
        if h.get("role") in ("user", "assistant") and h.get("content")
    ]
    return turns[-MAX_HISTORY_TURNS:]


def _stream_openai(url: str, headers: dict, payload: dict, on_token: Callable[[str], None]) -> tuple[str, bool]:
    """OpenAI-compatible streaming (server-sent events); returns (text, cut_off)."""
    parts, finish = [], None
    with requests.post(url, headers=headers, json={**payload, "stream": True}, timeout=60, stream=True) as response:
        response.raise_for_status()
        for line in response.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data:"):
                continue  # keep-alive comments like ": OPENROUTER PROCESSING"
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
            except json.JSONDecodeError:
                continue
            if chunk.get("error"):
                raise ValueError(f"LLM stream error: {chunk['error']}")
            choice = (chunk.get("choices") or [{}])[0]
            delta = (choice.get("delta") or {}).get("content") or ""
            if delta:
                parts.append(delta)
                on_token(delta)
            finish = choice.get("finish_reason") or finish
    return "".join(parts), finish == "length"


def _stream_ollama(payload: dict, on_token: Callable[[str], None]) -> tuple[str, bool]:
    parts, done_reason = [], None
    with requests.post(f"{config.OLLAMA_URL}/api/generate", json={**payload, "stream": True}, timeout=60,
                       stream=True) as response:
        response.raise_for_status()
        for line in response.iter_lines(decode_unicode=True):
            if not line:
                continue
            chunk = json.loads(line)
            if chunk.get("response"):
                parts.append(chunk["response"])
                on_token(chunk["response"])
            if chunk.get("done"):
                done_reason = chunk.get("done_reason")
                break
    return "".join(parts), done_reason == "length"


def _call_llm(system_prompt: str, query: str, history: list[dict], use_adapter: bool = False,
              on_token: Callable[[str], None] | None = None) -> str:
    """Call the configured provider and return usable raw text (or raise).

    *on_token*: stream the reply, calling it with each new piece of text as
    it arrives (the website's typing effect, /chat/stream).
    """
    if config.LLM_PROVIDER == "local":
        # On-device model (services/local_llm.py): nothing leaves the machine
        from services.local_llm import generate
        messages = [{"role": "system", "content": system_prompt}, *history, {"role": "user", "content": query}]
        text, cut_off = generate(messages, LOCAL_MAX_TOKENS, use_adapter=use_adapter, temperature=config.LLM_TEMPERATURE)
        if on_token and text:
            on_token(text)
        return _usable_llm_text(text, truncated=cut_off)

    if config.LLM_PROVIDER in ("openai", "openrouter") and config.OPENAI_API_KEY:
        headers = {
            "Authorization": f"Bearer {config.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": config.OPENAI_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                *history,
                {"role": "user", "content": query},
            ],
            "max_tokens": NATURAL_MAX_TOKENS,
            "temperature": 0.7,
        }
        if config.LLM_PROVIDER == "openrouter":
            headers["X-Title"] = "CHRONUS"  # OpenRouter app-attribution header
            # A 1-3 sentence in-character reply doesn't need thinking, and with
            # it on the model sometimes burned all 1000 tokens reasoning (no
            # answer, ~20s). Off: 0 reasoning tokens, 2-4s.
            payload["reasoning"] = {"enabled": False}
            if config.OPENAI_FALLBACK_MODELS:
                # OpenRouter-only: try these in order if the primary fails
                payload["models"] = [config.OPENAI_MODEL, *config.OPENAI_FALLBACK_MODELS]
        url = f"{config.OPENAI_BASE_URL}/chat/completions"
        if on_token:
            text, cut_off = _stream_openai(url, headers, payload, on_token)
            return _usable_llm_text(text, truncated=cut_off)
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        choice = response.json()["choices"][0]
        return _usable_llm_text(
            choice.get("message", {}).get("content"),
            truncated=choice.get("finish_reason") == "length",
        )

    # Ollama's single-prompt API
    convo = "".join(f"\n{t['role'].upper()}: {t['content']}" for t in history)
    payload = {
        "model": config.LLM_MODEL,
        "prompt": f"{system_prompt}\n{convo}\n\nTHE QUESTION: {query}",
        "stream": False,
        "options": {
            "temperature": 0.7,
            "num_predict": NATURAL_MAX_TOKENS,
            "num_ctx": config.LLM_CONTEXT_WINDOW,
        },
    }
    if on_token:
        text, cut_off = _stream_ollama(payload, on_token)
        return _usable_llm_text(text, truncated=cut_off)
    response = requests.post(f"{config.OLLAMA_URL}/api/generate", json=payload, timeout=60)
    response.raise_for_status()
    data = response.json()
    return _usable_llm_text(data.get("response"), truncated=data.get("done_reason") == "length")


def generate_natural_response(
    query: str,
    memories: list,  # (adjusted_dist, doc_text, metadata, raw_dist) tuples
    identity_card: dict,
    profile_block: str = "",
    history: list[dict] | None = None,
    persona_name: str = "Elon Musk",
    style_notes: str | None = None,
    use_adapter: bool = False,  # local provider only: apply the persona's LoRA adapter
    embedder=None,  # enables the sentence-level support check (config.NATURAL_MIN_SEMANTIC_SUPPORT)
    on_token: Callable[[str], None] | None = None,  # stream the draft (see _call_llm)
    length: str = "normal",  # "short" | "normal" | "detailed"
) -> dict:
    """Answer *query* in the persona's voice, grounded in *memories*.

    Returns a dict with keys response, sources, confidence, fallback, mode
    ("natural" on success; Mix Method output with mode="mix_method_fallback"
    if the LLM call fails).
    """
    memories = anchor_first(memories[:4 if length == "detailed" else 3])
    # The model sees (and is scored against) the evidence with transcript
    # noise and extraction damage removed ("pointat" -> "point at")
    texts = [clean_for_display(doc) for _, doc, _, _ in memories]
    evidence, sources = [], []
    for i, ((_, doc, meta, raw_dist), text) in enumerate(zip(memories, texts), start=1):
        citation = format_source_citation(meta, doc, raw_dist)
        sources.append(citation)
        evidence.append(_evidence_line(i, text, meta, citation["citation"]))
    system_prompt = build_system_prompt(persona_name, "\n\n".join(evidence), profile_block, style_notes, length)
    max_sentences = LENGTHS.get(length, LENGTHS["normal"])[1]

    try:
        raw = _call_llm(system_prompt, query, _clean_history(history), use_adapter, on_token)
        # Markers go before the full stop first: scrub() cuts anything after
        # the last one ("...bicycle. [1]" would lose its citation)
        clean_text = clean_citations(scrub(clean_citations(raw, len(memories))), len(memories))
        if not strip_citations(clean_text):
            raise ValueError("LLM reply was empty after scrubbing")
        clean_text = " ".join(re.split(r"(?<=[.!?])\s+", clean_text)[:max_sentences])
        # Grounding guard: an answer whose words mostly aren't in the evidence
        # (or the curated profile) is invented, whatever the prompt said.
        grounding = grounding_score(strip_citations(clean_text), texts + [profile_block])
        if grounding < config.NATURAL_MIN_GROUNDING:
            raise ValueError(f"answer not grounded in evidence (score {grounding})")
        # Sentence-level check: every sentence should be backed by some
        # evidence, not just the answer's words on average
        if embedder is not None and config.NATURAL_MIN_SEMANTIC_SUPPORT > 0:
            support = semantic_support(strip_citations(clean_text), texts + [profile_block], embedder,
                                       config.SEMANTIC_SENTENCE_MIN)
            if support < config.NATURAL_MIN_SEMANTIC_SUPPORT:
                raise ValueError(f"answer sentences not backed by evidence (support {support})")
        best_dist = min((m[3] for m in memories), default=2.0)
        return {
            "response": clean_text,
            "sources": sources,
            "confidence": calculate_confidence(best_dist),
            "fallback": False,
            "mode": "natural",
            "faithfulness": grounding,
        }
    except Exception as e:
        logger.error(f"Natural mode LLM call failed ({e}); falling back to Mix Method")
        mix_fallback = generate_mix_method_response(
            query=query,
            memories=memories,
            identity_card=identity_card,
            persona_name=persona_name,
            include_sources=True,
            length=length,
            embedder=embedder,
        )
        mix_fallback["mode"] = "mix_method_fallback"
        # Keep the citation schema identical to the success path.
        mix_fallback["sources"] = sources
        return mix_fallback
