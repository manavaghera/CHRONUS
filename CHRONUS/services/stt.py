"""
Speech to text for voice input (the chat's microphone and the interview).

Runs locally with faster-whisper (optional: pip install faster-whisper), so
recordings never leave this computer. The model downloads once on first use
(config.STT_MODEL, "base" is ~150 MB). Without it, the website falls back to
the browser's own speech recognition, and says that may use a cloud service.

    POST /transcribe  {content_base64 (16-bit WAV), language?}
"""

from __future__ import annotations

import base64
import binascii
import importlib.util
import io
import threading
import wave
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from config import config

MAX_SECONDS = 120
MAX_BYTES = 10 * 1024 * 1024

_lock = threading.Lock()
_model = None
MODEL_DIR = Path(__file__).resolve().parent.parent / "models" / ".whisper"  # downloaded speech model (git-ignored)


class TranscribeIn(BaseModel):
    content_base64: str = Field(min_length=1, max_length=MAX_BYTES * 4 // 3 + 16)
    language: str | None = Field(default=None, pattern=r"^[a-z]{2}$")  # "en", "hi", "gu"...


def available() -> bool:
    return importlib.util.find_spec("faster_whisper") is not None


def _whisper():
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                from faster_whisper import WhisperModel
                # Its own plain folder: the shared Hugging Face cache links files with
                # symlinks, which Windows refuses without Developer Mode (WinError 1314)
                _model = WhisperModel(config.STT_MODEL, device="cpu", compute_type="int8",
                                      download_root=str(MODEL_DIR))
    return _model


def wav_seconds(data: bytes) -> float:
    try:
        with wave.open(io.BytesIO(data)) as w:
            return w.getnframes() / float(w.getframerate())
    except (wave.Error, EOFError, ZeroDivisionError):
        raise ValueError("Please send a 16-bit PCM .wav recording")


def transcribe(data: bytes, language: str | None = None) -> dict:
    segments, info = _whisper().transcribe(io.BytesIO(data), language=language, vad_filter=True)
    text = " ".join(s.text.strip() for s in segments).strip()
    return {"text": text, "language": getattr(info, "language", language)}


def make_router() -> APIRouter:
    router = APIRouter(tags=["voice"])

    @router.post("/transcribe")
    def transcribe_endpoint(body: TranscribeIn):
        if not available():
            raise HTTPException(status_code=503, detail="Local speech recognition isn't installed: pip install faster-whisper")
        try:
            data = base64.b64decode(body.content_base64, validate=True)
        except (binascii.Error, ValueError):
            raise HTTPException(status_code=400, detail="Recording is not valid base64")
        try:
            seconds = wav_seconds(data)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        if not 0.3 <= seconds <= MAX_SECONDS:
            raise HTTPException(status_code=400, detail=f"Recordings must be under {MAX_SECONDS} seconds")
        return transcribe(data, body.language)

    return router
