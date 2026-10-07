"""Clone-voice page (services/voice_sandbox.py): consent, JSON only, tracked, really deleted."""

import base64
import io
import wave

import pytest

from services import personas as ps
from services import voice_sandbox


def _wav(seconds):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(16000)
        w.writeframes(b"\x00\x00" * int(16000 * seconds))
    return base64.b64encode(buf.getvalue()).decode()


@pytest.fixture(autouse=True)
def registry(tmp_path, monkeypatch):
    monkeypatch.setattr(voice_sandbox, "REGISTRY_PATH", tmp_path / "voices.json")


OK = {"name": "My voice", "consent": True, "cloud": True}


def test_old_multipart_endpoint_is_gone(client, fake_fish):
    # Form uploads skip the browser's preflight, so any website could trigger a clone
    r = client.post("/voice/quick-clone", files={"audio": ("a.wav", b"RIFF", "audio/wav")})
    assert r.status_code in (404, 405) and not fake_fish.requests


def test_clone_needs_consent_and_a_real_recording(client, fake_fish):
    assert client.post("/voice/sandbox", json={**OK, "content_base64": _wav(8), "consent": False}).status_code == 400
    assert client.post("/voice/sandbox", json={**OK, "content_base64": _wav(8), "cloud": False}).status_code == 400
    assert client.post("/voice/sandbox", json={**OK, "content_base64": base64.b64encode(b"webm?").decode()}).status_code == 400
    assert client.post("/voice/sandbox", json={**OK, "content_base64": _wav(2)}).status_code == 400  # too short
    assert not fake_fish.requests  # refused recordings never leave this computer
    r = client.post("/voice/sandbox", json={**OK, "content_base64": _wav(8)})
    assert r.status_code == 201 and r.json()["seconds"] == 8.0
    [saved] = voice_sandbox.load_registry()
    assert saved["consent"]["statement"] == voice_sandbox.CONSENT_STATEMENT
    assert client.get("/voice/sandbox").json() == [r.json()]  # no consent record in the public view


def test_speak_only_with_registered_voices(client, fake_fish):
    voice = client.post("/voice/sandbox", json={**OK, "content_base64": _wav(8)}).json()
    assert client.post("/voice/sandbox/speak", json={"text": "Hi", "voice_id": "someoneelse123"}).status_code == 404
    r = client.post("/voice/sandbox/speak", json={"text": "Hi", "voice_id": voice["id"]})
    assert r.status_code == 200 and r.headers["content-type"] == "audio/mpeg"


def test_delete_removes_it_at_fish_too(client, fake_fish):
    voice = client.post("/voice/sandbox", json={**OK, "content_base64": _wav(8)}).json()
    fake_fish.fail["DELETE"] = 500
    assert client.delete(f"/voice/sandbox/{voice['id']}").status_code == 502
    assert voice_sandbox.load_registry()  # kept: never orphan the cloud copy silently
    fake_fish.fail.clear()
    assert client.delete(f"/voice/sandbox/{voice['id']}").status_code == 200
    assert ("DELETE", f"/model/{voice['id']}") in [(q.method, q.url.path) for q in fake_fish.requests]
    assert voice_sandbox.load_registry() == []
    # Voices the page saved only in the browser (before the registry) can be removed from Fish too
    assert client.delete("/voice/sandbox/legacyvoice0001").status_code == 200


def test_a_models_voice_cant_be_deleted_from_the_sandbox(client, fake_fish, monkeypatch):
    monkeypatch.setattr(voice_sandbox.ps, "list_personas",
                        lambda **_: [{"id": "x", "voice": {"fish_voice_id": "modelvoice0001"}}])
    assert client.delete("/voice/sandbox/modelvoice0001").status_code == 409
    assert not fake_fish.requests
    assert ps.load_persona("elon_musk")  # sanity: the real personas are untouched
