"""
Voice sandbox (the website's "Clone voice" page): try a cloned voice without
building a whole model.

Same rules as a custom model's voice (services/persona_routes.py):
* consent is required and recorded: the speaker (or their estate) agreed,
  and agreed to the recording going to Fish Audio (cloud);
* bodies are JSON (the recording base64-encoded), so other websites can't
  trigger a clone with a cross-site form post;
* the recording must be a 6-60 s PCM .wav (the page converts microphone
  recordings to .wav before sending);
* every voice is recorded here, and deleting one deletes it at Fish Audio
  too. Speaking is only allowed with voices in this registry.

The registry lives in personas/ (git-ignored, private data).
"""

from __future__ import annotations

import base64
import binascii
import json
import threading
from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi import Path as PathParam
from fastapi.responses import Response
from pydantic import BaseModel, Field

from services import personas as ps
from services import tts

REGISTRY_PATH = ps.CUSTOM_DIR / ".voice_sandbox.json"
VOICE_ID = PathParam(pattern=r"^[A-Za-z0-9_-]{8,64}$")
CONSENT_STATEMENT = (
    "The speaker, or their estate, agreed to this voice being cloned for testing, and to the "
    "recording being sent to Fish Audio (a cloud service). Deleting the voice deletes it there too."
)
MAX_SANDBOX_VOICES = 20

_lock = threading.Lock()


class SandboxVoiceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    content_base64: str = Field(min_length=1, max_length=ps.MAX_UPLOAD_BYTES * 4 // 3 + 16)
    consent: bool
    cloud: bool


class SandboxSpeak(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    voice_id: str = Field(pattern=r"^[A-Za-z0-9_-]{8,64}$")


def load_registry() -> list[dict]:
    try:
        data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def _save_registry(voices: list[dict]) -> None:
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = REGISTRY_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(voices, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(REGISTRY_PATH)


def _public(voice: dict) -> dict:
    return {k: voice[k] for k in ("id", "name", "seconds", "created_at") if k in voice}


def _persona_voice_ids() -> set[str]:
    return {(p.get("voice") or {}).get("fish_voice_id") for p in ps.list_personas()} - {None}


def make_router() -> APIRouter:
    router = APIRouter(prefix="/voice/sandbox", tags=["voice"])

    @router.get("")
    def list_voices():
        return [_public(v) for v in load_registry()]

    @router.post("", status_code=201)
    def create_voice(body: SandboxVoiceCreate):
        if not body.consent:
            raise HTTPException(status_code=400, detail="Voice cloning needs the speaker's (or their estate's) consent")
        if not body.cloud:
            raise HTTPException(status_code=400, detail="The voice is made by Fish Audio (cloud): please agree to "
                                                        "sending the recording there")
        try:
            data = base64.b64decode(body.content_base64, validate=True)
        except (binascii.Error, ValueError):
            raise HTTPException(status_code=400, detail="Recording is not valid base64")
        try:
            seconds = ps.check_voice_sample(data)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        if len(load_registry()) >= MAX_SANDBOX_VOICES:
            raise HTTPException(status_code=409, detail=f"At most {MAX_SANDBOX_VOICES} test voices; delete one first")
        try:
            voice_id = tts.fish_create_voice(data)
        except tts.VoiceServiceError as e:
            raise HTTPException(status_code=e.status, detail=str(e))
        voice = {"id": voice_id, "name": body.name.strip(), "seconds": round(seconds, 1),
                 "created_at": datetime.now().isoformat(timespec="seconds"),
                 "consent": {"statement": CONSENT_STATEMENT, "given_at": datetime.now().isoformat(timespec="seconds")}}
        with _lock:
            _save_registry([*load_registry(), voice])
        return _public(voice)

    @router.delete("/{voice_id}")
    def delete_voice(voice_id: str = VOICE_ID):
        """Delete a test voice here and at Fish Audio.

        Also accepts ids the page saved before the server kept a registry
        (they only lived in the browser), so those can be removed from Fish
        too. A voice that belongs to a custom model is refused: remove it
        from that model instead.
        """
        if voice_id in _persona_voice_ids():
            raise HTTPException(status_code=409, detail="This voice belongs to a model; remove it on the model's page")
        try:
            tts.fish_delete_voice(voice_id)
        except tts.VoiceServiceError as e:
            raise HTTPException(status_code=e.status, detail=f"{e}. Nothing was removed; please try again.")
        with _lock:
            _save_registry([v for v in load_registry() if v.get("id") != voice_id])
        tts.fish_speech.cache_clear()
        return {"deleted": voice_id}

    @router.post("/speak")
    def speak(body: SandboxSpeak):
        if body.voice_id not in {v.get("id") for v in load_registry()}:
            raise HTTPException(status_code=404, detail="Unknown test voice; clone it again on this page")
        try:
            audio = tts.fish_speech(body.text, body.voice_id)
        except tts.VoiceServiceError as e:
            raise HTTPException(status_code=e.status, detail=str(e))
        return Response(content=audio, media_type="audio/mpeg", headers={"X-Chronus-Voice": "cloned"})

    return router
