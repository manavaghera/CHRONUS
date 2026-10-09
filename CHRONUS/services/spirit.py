"""
"In their spirit": an answer to something the person never talked about,
inferred from what they believed and said, and labelled so nobody takes it
for something they said.

It runs only when:
* the asker turned it on for this chat (ChatRequest.spirit),
* the model allows it: the pretrained figures do; a personal model only once
  its creator switched it on (persona["allow_spirit"]), because an invented
  answer in a loved one's voice is a different thing from their words,
* the AI voice can run for the model, and
* something real is nearby: memories within a looser distance than the
  model's "I don't know" threshold, or identity lines close in meaning
  (services/identity.py), whose memories become the evidence.

With nothing nearby, or an answer the grounding guard rejects, the reply is
still "I don't know".
"""

from __future__ import annotations

from typing import Callable

from services import identity, style
from services.natural_mode import generate_natural_response

MARGIN = 0.12          # extra cosine distance allowed beyond the model's threshold
MIN_LINE_SCORE = 0.35  # identity line to question, cosine
MAX_EVIDENCE = 4
NOTICE = "In their spirit: inferred from what they believed and said. They never said this."


def allowed(persona: dict) -> bool:
    """Whether this model may give 'in their spirit' answers at all."""
    return style.settings(persona)["allow_spirit"]


def line_memories(query: str, lines: list[dict], collection, embedder) -> list[tuple]:
    """The memories behind the identity lines closest in meaning to *query*,
    as retrieval tuples (adjusted_dist, doc, meta, raw_dist), closest first."""
    own = [line for line in lines if line["voice"] != "public" and line.get("memory_id")]
    if not own:
        return []
    vectors = embedder.encode([query] + [line["text"] for line in own], normalize_embeddings=True)
    scores = vectors[1:] @ vectors[0]
    picked = [(float(s), line) for s, line in sorted(zip(scores, own), key=lambda p: -p[0]) if s >= MIN_LINE_SCORE]
    picked = picked[:MAX_EVIDENCE]
    if not picked:
        return []
    got = collection.get(where={"memory_id": {"$in": [line["memory_id"] for _, line in picked]}},
                         include=["documents", "metadatas"])
    by_id = {meta.get("memory_id"): (doc, meta) for doc, meta in zip(got["documents"], got["metadatas"])}
    return [(1 - score, *by_id[line["memory_id"]], 1 - score) for score, line in picked if line["memory_id"] in by_id]


def answer(query: str, persona: dict, collection, embedder, search: Callable[[str], list | None],
           profile_block: str, history: list[dict], style_notes: str | None, use_adapter: bool = False,
           on_token=None, length: str = "normal") -> dict | None:
    """An 'in their spirit' answer, or None when there is nothing to stand on.

    *search(query)*: memories within the looser distance (None for none)."""
    lines = identity.visible_lines(identity.get(persona, collection, embedder))
    evidence, seen = [], set()
    for memory in list(search(query) or []) + line_memories(query, lines, collection, embedder):
        key = memory[2].get("memory_id") or memory[1][:80]
        if key not in seen:
            seen.add(key)
            evidence.append(memory)
    if not evidence:
        return None
    result = generate_natural_response(
        query=query, memories=evidence[:MAX_EVIDENCE], identity_card={}, profile_block=profile_block,
        history=history, persona_name=persona["name"], style_notes=style_notes, use_adapter=use_adapter,
        embedder=embedder, on_token=on_token, length=length, spirit=True,
    )
    if result.get("mode") != "natural":  # the LLM failed or invented: not worth showing as them
        return None
    return {**result, "mode": "spirit", "confidence": "low", "fallback": False, "notice": NOTICE}
