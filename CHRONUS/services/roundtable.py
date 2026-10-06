"""
Roundtable: put one question to 2-4 models at once, and optionally let each
respond to another's answer.

Every reply is still answered only from that model's own memories: in the
second round a model searches its archive for what it has said about the
other's answer, so Lincoln "replying" to Einstein quotes Lincoln, never an
invented opinion about Einstein. If its archive has nothing related, it says
so instead of replying.

    POST /roundtable  {query, personas: [ids], mode, respond: bool}
"""

from __future__ import annotations

import re
from typing import Callable, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field, field_validator

from services import personas as ps

MAX_SEATS = 4


class RoundtableRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    personas: list[str] = Field(min_length=2, max_length=MAX_SEATS)
    mode: Literal["natural", "mix_method"] = "mix_method"
    respond: bool = False  # second round: each replies to the previous speaker

    @field_validator("personas")
    @classmethod
    def _unique_ids(cls, ids: list[str]) -> list[str]:
        if len(set(ids)) != len(ids):
            raise ValueError("each model can only take one seat")
        for pid in ids:
            if not re.fullmatch(ps.PERSONA_ID_PATTERN, pid):
                raise ValueError(f"bad model id '{pid}'")
        return ids

    @field_validator("query")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query must not be blank")
        return value.strip()


def _plain(text: str, limit: int = 300) -> str:
    text = re.sub(r"\s*\[\d{1,2}\]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "…"


def make_router(load_ready: Callable[[str], dict], collection_for: Callable[[dict], object],
                answer: Callable[..., dict], log: Callable[..., str]) -> APIRouter:
    """*answer*: api_server.answer_from_memory; *log*: the Q&A logger."""
    router = APIRouter(tags=["roundtable"])

    @router.post("/roundtable")
    def roundtable(req: RoundtableRequest):
        seats = [load_ready(pid) for pid in req.personas]  # 404 / 409 before any work
        first = []
        for persona in seats:
            result = answer(req.query, persona, collection_for(persona), req.mode, [])
            result["id"] = log(req.query, result["response"], result["sources"], persona=persona["id"],
                               mode=result["mode"], confidence=result["confidence"], fallback=result["fallback"],
                               faithfulness=result["faithfulness"], roundtable=True) or ""
            first.append({"persona": persona["id"], "name": persona["name"], **result})

        replies = []
        if req.respond:
            for i, persona in enumerate(seats):
                other = first[i - 1]  # reply to the previous speaker (the first replies to the last)
                if other["fallback"]:
                    continue
                prompt = (f'{other["name"]} was asked "{req.query}" and answered: "{_plain(other["response"])}". '
                          f"What do you say to that?")
                result = answer(prompt, persona, collection_for(persona), req.mode, [])
                replies.append({"persona": persona["id"], "name": persona["name"], "replying_to": other["persona"],
                                "replying_to_name": other["name"], **result})
        return {"query": req.query, "answers": first, "replies": replies}

    return router

