"""Encrypted .chronus export / import (services/bundle.py)."""

import base64
import io
import wave
import zipfile

import pytest

from services import bundle
from services import personas as ps

LETTER = ("My favourite birthday was my eighteenth. My father bought me a blue Hero bicycle, and I rode it to the "
          "market every morning for twenty years.\n\nTeaching fractions with mangoes always worked better than any textbook.")


def _wav(seconds=7):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(16000)
        w.writeframes(b"\x00\x00" * int(16000 * seconds))
    return buf.getvalue()


@pytest.fixture(scope="module")
def original(client):
    pid = client.post("/personas", json={"name": "pytest Export Me", "relationship": "family", "consent": True}).json()["id"]
    client.post(f"/personas/{pid}/documents", json={"filename": "letter.txt", "content_base64": base64.b64encode(LETTER.encode()).decode()})
    for i in range(1, 11):
        client.post(f"/personas/{pid}/interview", json={"question_id": f"Q{i}", "answer": f"Answer {i}."})
    client.post(f"/personas/{pid}/build")
    client.post(f"/personas/{pid}/voice", json={"content_base64": base64.b64encode(_wav()).decode(), "consent": True, "cloud": True})
    yield pid
    client.delete(f"/personas/{pid}")


def test_round_trip(client, original):
    r = client.post(f"/personas/{original}/export", json={"password": "correct horse"})
    assert r.status_code == 200 and r.headers["content-disposition"].endswith('.chronus"')
    blob = r.content
    assert blob.startswith(bundle.MAGIC) and b"bicycle" not in blob  # encrypted
    payload = base64.b64encode(blob).decode()

    assert client.post("/personas/import", json={"content_base64": payload, "password": "wrong password"}).status_code == 400
    r = client.post("/personas/import", json={"content_base64": payload, "password": "correct horse"})
    assert r.status_code == 201, r.text
    copy = r.json()
    try:
        orig = client.get(f"/personas/{original}").json()
        assert copy["id"] != original and copy["name"] == orig["name"] and copy["status"] == "ready"
        assert copy["memories"] == orig["memories"] and copy["interview_answered"] == orig["interview_answered"]
        assert copy["voice"] is None  # the cloud voice is account-specific; the recording came along
        assert (ps.CUSTOM_DIR / copy["id"] / "voice" / "reference.wav").exists()
        assert (ps.CUSTOM_DIR / copy["id"] / "uploads" / "letter.txt").read_text(encoding="utf-8") == LETTER
        assert ps.load_persona(copy["id"])["consent"] == ps.load_persona(original)["consent"]
        d = client.post("/chat", json={"query": "What was your favourite birthday?", "persona": copy["id"], "mode": "mix_method"})
        assert d.status_code == 200
    finally:
        client.delete(f"/personas/{copy['id']}")


def test_only_custom_models_export(client):
    assert client.post("/personas/elon_musk/export", json={"password": "long enough"}).status_code == 403
    assert client.post("/personas/elon_musk/export", json={"password": "short"}).status_code == 422


@pytest.mark.parametrize("files", [
    {"manifest.json": "{}", "persona.json": "{}", "../../evil.txt": "x"},  # path traversal
    {"persona.json": "{}"},                                                # no manifest
])
def test_hostile_bundles_are_refused(client, files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, text in files.items():
            z.writestr(name, text)
    blob = bundle.encrypt(buf.getvalue(), "password123")
    r = client.post("/personas/import", json={"content_base64": base64.b64encode(blob).decode(), "password": "password123"})
    assert r.status_code == 400
    assert not (ps.ROOT / "evil.txt").exists()
