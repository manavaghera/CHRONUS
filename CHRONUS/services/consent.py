"""
Consent that can change, for custom models of real people.

Consent used to be one checkbox at creation that could never be taken back.
Now the person (or family) who gave it can:

* pause the model (nobody can chat with it) and resume it,
* revoke consent: the model and everything in it is deleted, as with Delete,
* renew it by a review date (a year after it was given): past that date the
  model pauses itself until someone renews,
* mark topics off limits: questions about them are refused, and memories
  that mention them are never quoted (a test asked about "the divorce
  papers" and the answer quoted them),
* mark single memories "never quote" (memory browser).

    GET  /personas/{id}/consent
    POST /personas/{id}/consent      {"action": "pause" | "resume" | "renew" | "revoke"}
    PUT  /personas/{id}/off-limits   {"topics": ["divorce", "the hospital"]}

Every change is recorded in the model's consent history. Pretrained models
(public figures) have none of this: they are built from published texts.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi import Path as PathParam
from pydantic import BaseModel, Field, field_validator

from services import personas as ps

REVIEW_DAYS = 365
MAX_TOPICS = 30
PERSONA_PATH = PathParam(pattern=ps.PERSONA_ID_PATTERN)


class ConsentAction(BaseModel):
    action: Literal["pause", "resume", "renew", "revoke"]


class OffLimits(BaseModel):
    topics: list[str] = Field(default_factory=list, max_length=MAX_TOPICS)

    @field_validator("topics")
    @classmethod
    def _clean(cls, topics: list[str]) -> list[str]:
        out = []
        for topic in topics:
            topic = re.sub(r"\s+", " ", topic).strip()
            if not 2 <= len(topic) <= 60:
                raise ValueError("each topic must be 2-60 characters")
            if topic.lower() not in (t.lower() for t in out):
                out.append(topic)
        return out


def review_by(persona: dict) -> date | None:
    if persona.get("kind") != "custom":
        return None
    if persona.get("consent_review_by"):
        return date.fromisoformat(persona["consent_review_by"])
    given = (persona.get("consent") or {}).get("given_at") or persona.get("created_at") or ""
    try:
        return datetime.fromisoformat(given).date() + timedelta(days=REVIEW_DAYS)
    except ValueError:
        return None


def state(persona: dict, today: date | None = None) -> dict:
    today = today or date.today()
    due = review_by(persona)
    return {"status": persona.get("consent_status", "active"), "review_by": due.isoformat() if due else None,
            "review_due": bool(due and today > due), "off_limits": persona.get("off_limits", []),
            "history": persona.get("consent_history", [])[-20:]}


def unavailable(persona: dict, today: date | None = None) -> str | None:
    """Why nobody may chat with this model now, or None."""
    if persona.get("kind") != "custom":
        return None
    if persona.get("consent_status") == "paused":
        return f"{persona['name']} is paused by the person who gave consent."
    s = state(persona, today)
    if s["review_due"]:
        return f"Consent for {persona['name']} was due for review on {s['review_by']}. Renew it on the model's page to use it again."
    return None


def _topic_pattern(topic: str) -> re.Pattern:
    words = [re.escape(w) for w in topic.lower().split()]
    # whole words; a final word may take an ending ("divorce" also finds "divorced")
    return re.compile(r"\b" + r"\s+".join(words) + r"\w{0,3}\b", re.IGNORECASE)


def off_limits_topic(persona: dict, text: str) -> str | None:
    """The first off-limits topic *text* mentions, or None."""
    for topic in persona.get("off_limits", []):
        if _topic_pattern(topic).search(text or ""):
            return topic
    return None


def blocked(persona: dict, doc: str, meta: dict) -> bool:
    """May this memory never be quoted?"""
    return bool((meta or {}).get("never_quote")) or off_limits_topic(persona, doc) is not None


def _record(persona_id: str, change: dict) -> dict:
    return ps.record_consent_change(persona_id, change)


def make_router(delete_model) -> APIRouter:
    """*delete_model(persona)*: deletes everything (persona_routes, also the cloud voice)."""
    router = APIRouter(prefix="/personas/{persona_id}", tags=["consent"])

    def _custom(persona_id: str) -> dict:
        persona = ps.load_persona(persona_id)
        if persona is None:
            raise HTTPException(status_code=404, detail=f"No model called '{persona_id}'")
        if persona["kind"] != "custom":
            raise HTTPException(status_code=403, detail="Pretrained models have no consent to change")
        return persona

    @router.get("/consent")
    def get_consent(persona_id: str = PERSONA_PATH):
        return state(_custom(persona_id))

    @router.post("/consent")
    def change_consent(body: ConsentAction, persona_id: str = PERSONA_PATH):
        persona = _custom(persona_id)
        if body.action == "revoke":
            delete_model(persona)
            return {"deleted": persona_id}
        if body.action == "pause":
            persona = _record(persona_id, {"consent_status": "paused"})
        elif body.action == "resume":
            if state(persona)["review_due"]:
                raise HTTPException(status_code=409, detail="Consent is due for review: renew it to resume")
            persona = _record(persona_id, {"consent_status": "active"})
        else:  # renew: consent confirmed again, for another year
            persona = _record(persona_id, {"consent_status": "active",
                                           "consent_review_by": (date.today() + timedelta(days=REVIEW_DAYS)).isoformat()})
        return state(persona)

    @router.put("/off-limits")
    def set_off_limits(body: OffLimits, persona_id: str = PERSONA_PATH):
        _custom(persona_id)
        return state(_record(persona_id, {"off_limits": body.topics}))

    return router
