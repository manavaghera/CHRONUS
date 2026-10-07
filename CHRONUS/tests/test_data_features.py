"""Answer cache, background uploads, duplicate skipping, voice-note uploads, upload content checks."""

import base64
import time
from types import SimpleNamespace

import pytest

from services import answer_cache, stt
from services import personas as ps

LETTER = ("My favourite birthday was my eighteenth. My father bought me a blue Hero bicycle, and I rode it to the "
          "market every morning for twenty years.\n\nTeaching fractions with mangoes always worked better than any textbook.")


def b64(data):
    return base64.b64encode(data if isinstance(data, bytes) else data.encode()).decode()


@pytest.fixture
def persona(client):
    pid = client.post("/personas", json={"name": "pytest Data", "relationship": "self", "consent": True}).json()["id"]
    yield pid
    client.delete(f"/personas/{pid}")


def test_answer_cache(srv, client, monkeypatch):
    monkeypatch.setenv("CHRONUS_ANSWER_CACHE", "1")
    answer_cache.clear()
    calls = []
    real = srv.answer_from_memory
    monkeypatch.setattr(srv, "answer_from_memory", lambda *a, **k: calls.append(1) or real(*a, **k))
    first = client.post("/chat", json={"query": "How do I descale a kettle?", "mode": "mix_method"}).json()
    again = client.post("/chat", json={"query": "how do I  descale a kettle?", "mode": "mix_method"}).json()
    assert len(calls) == 1 and again["answer"] == first["answer"]
    client.post("/chat", json={"query": "How do I descale a kettle?", "mode": "mix_method", "length": "short"})
    assert len(calls) == 2  # different settings, different answer
    # a follow-up depends on the conversation: never cached
    history = [{"role": "user", "content": "Why Mars?"}, {"role": "assistant", "content": "Backup."}]
    client.post("/chat", json={"query": "why?", "mode": "mix_method", "history": history})
    client.post("/chat", json={"query": "why?", "mode": "mix_method", "history": history})
    assert len(calls) == 4
    # changing any model's memories clears it
    pid = client.post("/personas", json={"name": "pytest Cache", "relationship": "self", "consent": True}).json()["id"]
    client.delete(f"/personas/{pid}")
    client.post("/chat", json={"query": "How do I descale a kettle?", "mode": "mix_method"})
    assert len(calls) == 5


def test_background_upload_reports_progress(client, persona):
    r = client.post(f"/personas/{persona}/documents/async", json={"filename": "letter.txt", "content_base64": b64(LETTER)})
    assert r.status_code == 202
    job_id = r.json()["job_id"]
    for _ in range(50):
        job = client.get(f"/jobs/{job_id}").json()
        if job["status"] != "running":
            break
        time.sleep(0.05)
    assert job["status"] == "done" and job["progress"] == 1.0 and job["result"]["upload"]["memories"] >= 1
    bad = client.post(f"/personas/{persona}/documents/async", json={"filename": "x.exe", "content_base64": b64("hello")}).json()
    for _ in range(50):
        job = client.get(f"/jobs/{bad['job_id']}").json()
        if job["status"] != "running":
            break
        time.sleep(0.05)
    assert job["status"] == "failed" and "Unsupported" in job["error"]
    assert client.get("/jobs/0123456789abcdef").status_code == 404


def test_same_text_in_another_file_is_skipped(client, persona):
    first = client.post(f"/personas/{persona}/documents", json={"filename": "a.txt", "content_base64": b64(LETTER)}).json()["upload"]
    second = client.post(f"/personas/{persona}/documents", json={"filename": "b.txt", "content_base64": b64(LETTER)}).json()["upload"]
    assert first["memories"] >= 1 and second["memories"] == 0 and second["duplicates_skipped"] == first["memories"]


@pytest.mark.parametrize("filename,data,message", [
    ("fake.pdf", b"<html>not a pdf</html>", "real .pdf"),
    ("notes.txt", b"MZ\x90\x00 executable", "binary"),
    ("song.mp3", b"<html>", "real .mp3"),
])
def test_contents_must_match_the_name(client, persona, filename, data, message):
    r = client.post(f"/personas/{persona}/documents", json={"filename": filename, "content_base64": b64(data)})
    assert r.status_code == 400 and message in r.json()["detail"]
    assert not (ps.CUSTOM_DIR / persona / "uploads" / filename).exists()


def test_voice_note_becomes_first_person_memories(client, persona, monkeypatch):
    class FakeWhisper:
        def transcribe(self, audio, vad_filter=True, word_timestamps=False):
            return iter([SimpleNamespace(text="I remember the monsoon of 1987 flooding the village school."),
                         SimpleNamespace(text="We taught under the banyan tree for a whole month after that.")]), None
    monkeypatch.setattr(stt, "available", lambda: True)
    monkeypatch.setattr(stt, "_model", FakeWhisper())
    wav = b"RIFF" + b"\x00" * 100
    r = client.post(f"/personas/{persona}/documents", json={"filename": "memo.wav", "content_base64": b64(wav)})
    assert r.status_code == 200, r.text
    assert r.json()["upload"]["kind"] == "audio"
    items = client.get(f"/personas/{persona}/memories", params={"source": "memo.wav"}).json()["items"]
    assert items and items[0]["voice"] == "first_person" and "banyan" in items[0]["text"]
    assert items[0]["citation"].startswith("Voice note")


def test_audio_without_whisper_is_explained(client, persona, monkeypatch):
    monkeypatch.setattr(stt, "available", lambda: False)
    r = client.post(f"/personas/{persona}/documents", json={"filename": "memo.wav", "content_base64": b64(b"RIFF" + b"\x00" * 50)})
    assert r.status_code == 400 and "faster-whisper" in r.json()["detail"]
