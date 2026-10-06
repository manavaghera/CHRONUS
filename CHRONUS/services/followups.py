"""
Adaptive interview: after each answer, suggest what to ask next.

Two kinds of suggestions, both made on this computer (no LLM, so nothing is
sent anywhere and nothing is invented about the person):
* follow-ups about what the answer itself mentions: names, places, years
  ("You mentioned Pune. What do you remember most about it?");
* the unanswered protocol questions closest in meaning to the answer.

Follow-up answers are stored like interview answers (labelled with who
answered), with their own question text.

    POST /personas/{id}/followup  {question, answer, origin}
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi import Path as PathParam
from pydantic import BaseModel, Field

from services import personas as ps
from services.provenance import content_words

PERSONA_PATH = PathParam(pattern=ps.PERSONA_ID_PATTERN)

# Capitalised words that start sentences or are just pronouns/fillers
_NOT_NAMES = frozenset("""I I'm I've I'd My Me We Our Us You Your He She His Her They Their It Its The A An And But Or So
Then When While Because If In On At For With From To Of By As This That These Those There Here What Why How Who
Yes No Not Also Even Just Every Some Many Most Mom Dad Mother Father Sunday Monday Tuesday Wednesday Thursday
Friday Saturday January February March April May June July August September October November December""".split())
_YEAR = re.compile(r"\b(1[89]\d{2}|20\d{2})\b")
_NAME = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b")


class FollowupAnswer(BaseModel):
    question: str = Field(min_length=5, max_length=300)
    answer: str = Field(min_length=1, max_length=4000)
    origin: Literal["self", "family", "friend", "colleague", "synthesized"] = "self"


def mentioned(answer: str) -> dict[str, list[str]]:
    """Names/places and years an answer mentions (in order, de-duplicated)."""
    names, seen = [], set()
    for sentence in re.split(r"(?<=[.!?])\s+", answer):
        words = sentence.split()
        for m in _NAME.finditer(sentence):
            name = m.group(1)
            first_word = words[0].strip("\"'(") if words else ""
            if name.split()[0] in _NOT_NAMES or (sentence.startswith(name) and name == first_word):
                continue  # sentence-initial capital, not a name
            if name.lower() not in seen:
                seen.add(name.lower())
                names.append(name)
    years = list(dict.fromkeys(_YEAR.findall(answer)))
    return {"names": names[:3], "years": years[:2]}


def suggest(answer: str, unanswered: list[dict], embedder=None, limit: int = 4) -> list[dict]:
    """Follow-up questions for *answer*: [{"question", "kind", "id"?}]."""
    found = mentioned(answer)
    out = [{"question": f"You mentioned {n}. What do you remember most about {n}?", "kind": "follow_up"}
           for n in found["names"]]
    out += [{"question": f"What else was happening in your life around {y}?", "kind": "follow_up"} for y in found["years"]]
    if not out:
        words = sorted(content_words(answer), key=len, reverse=True)[:1]
        if words:
            out.append({"question": f"Why does {words[0]} matter so much to you?", "kind": "follow_up"})
    if unanswered and embedder is not None:
        av = embedder.encode([answer], normalize_embeddings=True)
        qv = embedder.encode([q["question"] for q in unanswered], normalize_embeddings=True)
        order = (qv @ av[0]).argsort()[::-1][:2]
        out += [{"question": unanswered[i]["question"], "kind": "protocol", "id": unanswered[i]["id"]} for i in order]
    return out[:limit]


def make_router(client, embedder) -> APIRouter:
    router = APIRouter(prefix="/personas/{persona_id}", tags=["interview"])

    @router.post("/followup")
    def answer_followup(body: FollowupAnswer, persona_id: str = PERSONA_PATH):
        persona = ps.load_persona(persona_id)
        if persona is None:
            raise HTTPException(status_code=404, detail=f"No model called '{persona_id}'")
        if persona["kind"] != "custom":
            raise HTTPException(status_code=403, detail="Pretrained models can't be changed")
        text = f"[Interview Response] Q: {body.question.strip()} A: {body.answer.strip()}"
        question_id = "F" + hashlib.md5(body.question.strip().lower().encode()).hexdigest()[:8]
        memory_id = "int_" + hashlib.md5(text.encode("utf-8")).hexdigest()[:16]
        collection = ps.get_collection(client, persona)
        # Answering the same follow-up again replaces the earlier answer
        collection.delete(where={"$and": [{"source_type": "interview_protocol"}, {"question_id": question_id}]})
        collection.upsert(ids=[memory_id], documents=[text],
                          embeddings=embedder.encode([text], normalize_embeddings=True).tolist(),
                          metadatas=[{"source_file": "interview_protocol", "source_type": "interview_protocol",
                                      "source_name": "Structured Interview", "date": "protocol", "importance_score": 4,
                                      "memory_id": memory_id, "person": persona["id"], "question_id": question_id,
                                      "dimension": "follow_up", "origin": body.origin,
                                      "question": body.question.strip()[:300],
                                      "answered_at": datetime.now().isoformat(timespec="seconds")}])
        ps.record_followup(persona, question_id)
        return {"question_id": question_id, "memory_id": memory_id, "memories": collection.count(),
                "followups": suggest(body.answer, [], None)}

    return router
