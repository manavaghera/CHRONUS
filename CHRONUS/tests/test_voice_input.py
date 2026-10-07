"""Voice input (services/stt.py) and the adaptive interview (services/followups.py)."""

import base64
import io
import wave
from types import SimpleNamespace

import pytest

from services import followups, stt


def _wav(seconds):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(16000)
        w.writeframes(b"\x00\x00" * int(16000 * seconds))
    return base64.b64encode(buf.getvalue()).decode()


def test_status_reports_speech_to_text(client):
    s = client.get("/voice/status").json()["speech_to_text"]
    assert s["where"] == "local" and isinstance(s["available"], bool)


def test_transcribe_without_whisper_explains(client, monkeypatch):
    monkeypatch.setattr(stt, "available", lambda: False)
    r = client.post("/transcribe", json={"content_base64": _wav(2)})
    assert r.status_code == 503 and "faster-whisper" in r.json()["detail"]


def test_transcribe_runs_locally(client, monkeypatch):
    class FakeWhisper:
        def transcribe(self, audio, language=None, vad_filter=True):
            assert audio.read(4) == b"RIFF"
            return iter([SimpleNamespace(text=" Why did you "), SimpleNamespace(text="build rockets? ")]), SimpleNamespace(language="en")
    monkeypatch.setattr(stt, "available", lambda: True)
    monkeypatch.setattr(stt, "_model", FakeWhisper())
    assert client.post("/transcribe", json={"content_base64": _wav(2)}).json() == {"text": "Why did you build rockets?", "language": "en"}
    assert client.post("/transcribe", json={"content_base64": base64.b64encode(b"webm").decode()}).status_code == 400
    assert client.post("/transcribe", json={"content_base64": _wav(0.1)}).status_code == 400


def test_mentions_skip_sentence_starts_and_pronouns():
    found = followups.mentioned("My brother Ravi moved to Pune in 1979. Then Kamla came. We visited Mumbai often.")
    assert found == {"names": ["Ravi", "Pune", "Mumbai"], "years": ["1979"]}


def test_suggestions(srv):
    questions = [{"id": "Q9", "question": "Who has been the most influential person in your life and why?"},
                 {"id": "Q13", "question": "What gets you genuinely excited to wake up in the morning?"}]
    out = followups.suggest("My brother Ravi taught me to swim in 1979.", questions, srv.embedder)
    assert out[0]["question"].startswith("You mentioned Ravi") and any(o["kind"] == "protocol" for o in out)
    assert followups.suggest("ok", [], None) == []
    assert followups.suggest("Gardening taught me patience", [], None)[0]["question"] == "Why does gardening matter so much to you?"


@pytest.fixture(scope="module")
def persona(client):
    pid = client.post("/personas", json={"name": "pytest Followups", "relationship": "self", "consent": True}).json()["id"]
    yield pid
    client.delete(f"/personas/{pid}")


def test_interview_answer_returns_followups_and_followups_are_stored(client, persona):
    r = client.post(f"/personas/{persona}/interview", json={"question_id": "Q5", "answer": "The flood in Surat in 2006 changed me."})
    assert r.status_code == 200 and any("Surat" in f["question"] for f in r.json()["followups"])
    q = "You mentioned Surat. What do you remember most about Surat?"
    first = client.post(f"/personas/{persona}/followup", json={"question": q, "answer": "The water came up to our balcony.", "origin": "family"})
    assert first.status_code == 200
    again = client.post(f"/personas/{persona}/followup", json={"question": q, "answer": "The water reached the second floor."}).json()
    assert again["memories"] == first.json()["memories"]  # replaced, not duplicated
    assert client.get(f"/personas/{persona}").json()["followups_answered"] == 1
    assert client.post("/personas/elon_musk/followup", json={"question": q, "answer": "x"}).status_code == 403
