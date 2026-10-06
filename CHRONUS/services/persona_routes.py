"""
HTTP endpoints for personas: list pretrained and custom models, and build a
custom one (create with consent -> upload documents -> interview -> build ->
chat), or delete it.

All bodies are JSON (files arrive base64-encoded), so browsers must preflight
cross-site requests, which this server rejects: other websites can't create
models or write memories (same reasoning as the /interview endpoints).
"""

from __future__ import annotations

import base64
import binascii
from typing import Literal

from fastapi import APIRouter, HTTPException, Path as PathParam
from pydantic import BaseModel, Field

from services import personas as ps
from services import tts

PERSONA_PATH = PathParam(pattern=ps.PERSONA_ID_PATTERN)
CONSENT_STATEMENT = (
    "I am this person, or I have their permission (or their estate's) to build "
    "this model from their words."
)


class PersonaCreate(BaseModel):
    name: str = Field(min_length=2, max_length=60)
    description: str = Field(default="", max_length=300)
    relationship: Literal["self", "family", "friend", "colleague", "other"]
    allow_cloud_llm: bool = False
    consent: bool


class DocumentUpload(BaseModel):
    filename: str = Field(min_length=1, max_length=200)
    # base64 inflates by 4/3; the decoded size is checked again on ingest
    content_base64: str = Field(min_length=1, max_length=ps.MAX_UPLOAD_BYTES * 4 // 3 + 16)
    authored_by: Literal["self", "other"] = "self"


class VoiceUpload(BaseModel):
    content_base64: str = Field(min_length=1, max_length=ps.MAX_UPLOAD_BYTES * 4 // 3 + 16)
    consent: bool  # the person (or their estate) agreed to their voice being used
    cloud: bool  # ...and to the recording going to Fish Audio to make the voice (services/tts.py)


class InterviewAnswer(BaseModel):
    question_id: str = Field(pattern=r"^Q\d{1,2}$")
    answer: str = Field(min_length=1, max_length=4000)
    # Who answered: the person themselves, someone who knew them, or generated.
    origin: Literal["self", "family", "friend", "colleague", "synthesized"] = "self"


def summarize(persona: dict, collection) -> dict:
    """Public view of a persona (no consent record or internal paths)."""
    return {
        "id": persona["id"],
        "name": persona["name"],
        "kind": persona["kind"],
        "status": persona.get("status", "draft"),
        "description": persona.get("description", ""),
        "allow_cloud_llm": bool(persona.get("allow_cloud_llm")),
        "relationship": persona.get("relationship", ""),
        "created_at": persona.get("created_at", ""),
        "memories": collection.count(),
        "uploads": persona.get("uploads", []),
        "interview_answered": persona.get("interview_answered", []),
        "min_memories": ps.MIN_MEMORIES_TO_BUILD,
        # pretrained famous figures (figures/build_figures.py)
        "voice": {"seconds": persona["voice"]["seconds"], "provider": "Fish Audio"} if persona.get("voice") else None,
        # synthetic Listen voice for public figures (services/tts.py), not a clone
        "stand_in_voice": persona.get("kind") == "pretrained" and bool(persona.get("stand_in_voice")),
        "suggested_questions": persona.get("suggested_questions", []),
        "sources": persona.get("sources", []),
        "license": persona.get("license", ""),
    }


def make_router(client, embedder) -> APIRouter:
    """Endpoints bound to the server's ChromaDB client and embedding model."""
    router = APIRouter(prefix="/personas", tags=["personas"])

    def _get(persona_id: str) -> dict:
        persona = ps.load_persona(persona_id)
        if persona is None:
            raise HTTPException(status_code=404, detail=f"No model called '{persona_id}'")
        return persona

    def _custom(persona_id: str) -> dict:
        persona = _get(persona_id)
        if persona["kind"] != "custom":
            raise HTTPException(status_code=403, detail="Pretrained models can't be changed")
        return persona

    # Plain `def` endpoints: FastAPI runs them in a thread pool, so slow
    # embedding work doesn't block other requests.
    @router.get("")
    def list_all():
        return [summarize(p, ps.get_collection(client, p)) for p in ps.list_personas()]

    @router.post("", status_code=201)
    def create(body: PersonaCreate):
        if not body.consent:
            raise HTTPException(status_code=400, detail="Consent is required to build a model of a real person")
        persona = ps.create_custom_persona(
            body.name, body.description, body.relationship, body.allow_cloud_llm, CONSENT_STATEMENT,
        )
        return summarize(persona, ps.get_collection(client, persona))

    @router.get("/{persona_id}")
    def detail(persona_id: str = PERSONA_PATH):
        persona = _get(persona_id)
        return summarize(persona, ps.get_collection(client, persona))

    @router.post("/{persona_id}/documents")
    def upload(body: DocumentUpload, persona_id: str = PERSONA_PATH):
        persona = _custom(persona_id)
        try:
            data = base64.b64decode(body.content_base64, validate=True)
        except (binascii.Error, ValueError):
            raise HTTPException(status_code=400, detail="File content is not valid base64")
        try:
            entry = ps.ingest_document(
                persona, ps.get_collection(client, persona), embedder, body.filename, data, body.authored_by,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return {"upload": entry, "persona": detail(persona_id)}

    @router.post("/{persona_id}/interview")
    def interview(body: InterviewAnswer, persona_id: str = PERSONA_PATH):
        persona = _custom(persona_id)
        return {"result": embed_interview_answer(client, embedder, persona, body), "persona": detail(persona_id)}

    @router.post("/{persona_id}/voice")
    def add_voice(body: VoiceUpload, persona_id: str = PERSONA_PATH):
        persona = _custom(persona_id)
        if not body.consent:
            raise HTTPException(status_code=400, detail="Voice cloning needs the person's (or their estate's) consent")
        if not body.cloud:
            raise HTTPException(status_code=400, detail="The voice is made by Fish Audio (cloud): please agree to "
                                                        "sending the recording there")
        try:
            data = base64.b64decode(body.content_base64, validate=True)
        except (binascii.Error, ValueError):
            raise HTTPException(status_code=400, detail="Recording is not valid base64")
        try:
            ps.check_voice_sample(data)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        old_voice_id = (persona.get("voice") or {}).get("fish_voice_id")
        try:
            ps.save_voice_sample(persona, data, tts.fish_create_voice(data))
            if old_voice_id:
                tts.fish_delete_voice(old_voice_id)  # replaced: don't leave the old one at Fish
        except tts.VoiceServiceError as e:
            raise HTTPException(status_code=e.status, detail=str(e))
        return detail(persona_id)

    @router.delete("/{persona_id}/voice")
    def remove_voice(persona_id: str = PERSONA_PATH):
        persona = _custom(persona_id)
        _delete_cloud_voice(persona)
        ps.delete_voice_sample(persona)
        return detail(persona_id)

    @router.post("/{persona_id}/build")
    def build(persona_id: str = PERSONA_PATH):
        persona = _custom(persona_id)
        collection = ps.get_collection(client, persona)
        try:
            built = ps.build_persona(collection, persona)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return summarize(built, collection)

    @router.delete("/{persona_id}")
    def delete(persona_id: str = PERSONA_PATH):
        persona = _custom(persona_id)
        _delete_cloud_voice(persona)
        ps.delete_custom_persona(client, persona)
        return {"deleted": persona_id}

    return router


def _delete_cloud_voice(persona: dict) -> None:
    """Delete the persona's private Fish voice first; if that fails nothing is
    removed, so the voice is never left behind in the cloud unnoticed."""
    voice_id = (persona.get("voice") or {}).get("fish_voice_id")
    if not voice_id:
        return
    try:
        tts.fish_delete_voice(voice_id)
    except tts.VoiceServiceError as e:
        raise HTTPException(status_code=e.status, detail=f"{e}. Nothing was removed; please try again.")


def embed_interview_answer(client, embedder, persona: dict, item: InterviewAnswer) -> dict:
    """Store one interview answer in the persona's own collection.

    Answering a question again replaces the earlier answer instead of keeping
    both (the memory ID is a hash of the text, so it would otherwise pile up).
    """
    from services.interview_embedder import embed_single_response

    collection = ps.get_collection(client, persona)
    collection.delete(where={"$and": [{"source_type": "interview_protocol"}, {"question_id": item.question_id}]})
    result = embed_single_response(
        question_id=item.question_id,
        answer=item.answer.strip(),
        collection=collection,
        embedder=embedder,
        person=persona["id"],
        origin=item.origin,
    )
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Unknown error"))
    if persona["kind"] == "custom":
        ps.record_interview_answer(persona, item.question_id)
    return result
