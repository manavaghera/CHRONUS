"""
Text to speech for the chat's Listen button.

Pretrained models (Elon, the public-domain figures) speak in a Kokoro-82M
stand-in voice: a synthetic voice picked per model (persona.json
"stand_in_voice"), never a copy of the real person, and the website labels
it that way. Kokoro is Apache-2.0 and runs on this machine (~330 MB, loaded
on first use).

Custom models can speak in their own cloned voice when the creator uploads a
consented recording and opts in to Fish Audio (cloud, S2.1 Pro). The
recording is sent once to make a private Fish voice model; after that only
the text of each answer the user plays is sent.
"""

from __future__ import annotations

import io
import os
import re
import threading
from functools import lru_cache

import httpx

from config import config

KOKORO_REPO = "hexgrad/Kokoro-82M"
SAMPLE_RATE = 24000

# Kokoro v1.0 English voices; the first letter is the accent (a = US, b = UK)
STAND_IN_VOICES = frozenset({
    "af_heart", "af_bella", "af_nicole", "af_sarah", "am_michael", "am_fenrir", "am_puck", "am_adam",
    "am_echo", "am_eric", "am_liam", "am_onyx", "bf_emma", "bf_isabella", "bf_alice", "bf_lily",
    "bm_george", "bm_fable", "bm_lewis", "bm_daniel",
})

_lock = threading.Lock()
_kokoro: dict = {}


def _pipeline(accent: str):
    """One shared Kokoro model, one text-to-phoneme pipeline per accent."""
    if "model" not in _kokoro:
        import torch
        from kokoro import KModel
        device = "cuda" if torch.cuda.is_available() else "cpu"
        _kokoro["model"] = KModel(repo_id=KOKORO_REPO).to(device).eval()
    if accent not in _kokoro:
        from kokoro import KPipeline
        _kokoro[accent] = KPipeline(lang_code=accent, repo_id=KOKORO_REPO, model=_kokoro["model"])
    return _kokoro[accent]


@lru_cache(maxsize=32)  # pressing Listen again replays without regenerating
def stand_in_wav(text: str, voice: str) -> bytes:
    """Speak *text* in a Kokoro stand-in voice; returns 16-bit PCM WAV bytes."""
    if voice not in STAND_IN_VOICES:
        raise ValueError(f"Unknown stand-in voice '{voice}'")
    import soundfile as sf
    import torch

    with _lock:  # the API serves requests from worker threads
        chunks = [r.audio for r in _pipeline(voice[0])(text, voice=voice) if r.audio is not None]
    if not chunks:
        raise ValueError("Nothing to read aloud")
    buf = io.BytesIO()
    sf.write(buf, torch.cat(chunks).cpu().numpy(), SAMPLE_RATE, format="WAV", subtype="PCM_16")
    return buf.getvalue()


# ---- Fish Audio: consented cloned voices for custom models ----

_TRANSPORT = None  # tests swap in an httpx.MockTransport so nothing reaches Fish
_FISH_ID = re.compile(r"[A-Za-z0-9_-]{8,64}")


class VoiceServiceError(Exception):
    """Fish Audio couldn't be used; .status is the HTTP status to answer with."""

    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.status = status


def cloud_voice_configured() -> bool:
    return bool(os.environ.get("FISH_API_KEY", "").strip())


def _fish_call(method: str, path: str, action: str, **kwargs) -> httpx.Response:
    key = os.environ.get("FISH_API_KEY", "").strip()
    if not key:
        raise VoiceServiceError("Cloud voice isn't set up: add FISH_API_KEY=<your key> to CHRONUS/.env "
                                "(fish.audio/app/api-keys), then restart the server", status=503)
    try:
        with httpx.Client(base_url=config.FISH_API_URL, headers={"Authorization": f"Bearer {key}"},
                          timeout=90, transport=_TRANSPORT) as http:
            r = http.request(method, path, **kwargs)
    except httpx.HTTPError as e:
        raise VoiceServiceError(f"Can't reach Fish Audio to {action}: {type(e).__name__}")
    if r.status_code == 401:
        raise VoiceServiceError("Fish Audio rejected FISH_API_KEY in CHRONUS/.env", status=503)
    if r.status_code == 402:
        raise VoiceServiceError("Fish Audio needs credit on this account (the free S2.1 Pro period may have "
                                "ended; see FISH_TTS_MODEL in config.py)", status=503)
    if r.status_code >= 400 and not (method == "DELETE" and r.status_code == 404):
        raise VoiceServiceError(f"Fish Audio couldn't {action} (HTTP {r.status_code})")
    return r


def fish_create_voice(wav: bytes, filename: str = "reference.wav", content_type: str = "audio/wav") -> str:
    """Make a private Fish voice model from a consented recording; returns its id."""
    r = _fish_call("POST", "/model", "create the voice",
                   data={"type": "tts", "title": "CHRONUS private voice", "train_mode": "fast", "visibility": "private"},
                   files={"voices": (filename, wav, content_type)})
    try:
        voice_id = str(r.json().get("_id", ""))
    except ValueError:
        voice_id = ""
    if not _FISH_ID.fullmatch(voice_id):
        raise VoiceServiceError("Fish Audio didn't return a voice id")
    return voice_id


@lru_cache(maxsize=32)  # replaying an answer doesn't call Fish again
def fish_speech(text: str, voice_id: str) -> bytes:
    """Speak *text* in a private Fish voice model; returns MP3 bytes."""
    if not _FISH_ID.fullmatch(voice_id):
        raise VoiceServiceError("Bad voice id", status=500)
    r = _fish_call("POST", "/v1/tts", "speak", headers={"model": config.FISH_TTS_MODEL},
                   json={"text": text, "reference_id": voice_id, "format": "mp3"})
    return r.content


def fish_demo_speech(text: str) -> bytes:
    """Speak *text* using Fish Audio's base model (no voice cloning), for demo testing."""
    r = _fish_call("POST", "/v1/tts", "speak", headers={"model": config.FISH_TTS_MODEL},
                   json={"text": text, "format": "mp3"})
    return r.content


def fish_delete_voice(voice_id: str) -> None:
    """Delete a private Fish voice model (already gone counts as done)."""
    if _FISH_ID.fullmatch(voice_id):
        _fish_call("DELETE", f"/model/{voice_id}", "delete the voice")
