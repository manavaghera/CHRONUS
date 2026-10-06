"""Listen voices (services/tts.py): Kokoro stand-ins and the Fish Audio client."""

import httpx
import pytest

from services import tts


def test_stand_in_voice_is_real_speech():
    pytest.importorskip("kokoro")
    wav = tts.stand_in_wav("Hello there.", "bm_george")
    assert wav[:4] == b"RIFF" and wav[8:12] == b"WAVE"
    assert len(wav) > tts.SAMPLE_RATE * 2 * 0.5  # at least half a second of 16-bit audio
    with pytest.raises(ValueError):
        tts.stand_in_wav("Hello there.", "../../voices/someone")


def test_fish_voice_ids_are_checked_before_use(fake_fish):
    tts.fish_delete_voice("../../account")  # not an id: ignored, never put in a URL
    with pytest.raises(tts.VoiceServiceError):
        tts.fish_speech("hi", "bad id/../x")
    assert not fake_fish.requests


def test_fish_errors_become_clear_messages(fake_fish, monkeypatch):
    fake_fish.fail["DELETE"] = 404
    tts.fish_delete_voice("fishvoice00000099")  # already gone counts as deleted
    fake_fish.fail["POST"] = 401
    with pytest.raises(tts.VoiceServiceError, match="rejected FISH_API_KEY") as e:
        tts.fish_create_voice(b"RIFF")
    assert e.value.status == 503

    def offline(request):
        raise httpx.ConnectError("no network")
    monkeypatch.setattr(tts, "_TRANSPORT", httpx.MockTransport(offline))
    with pytest.raises(tts.VoiceServiceError, match="Can't reach Fish Audio") as e:
        tts.fish_speech("hi", "fishvoice00000001")
    assert e.value.status == 502
