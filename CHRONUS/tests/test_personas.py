"""Custom models end to end: consent -> upload -> interview -> build -> chat -> delete."""

import base64
import io
import json

import docx
import pytest

from services import personas as ps

LETTER = """Dear Ravi,

I still remember the monsoon of 1987, when the river flooded the whole village and we carried the goats up to the temple steps.

My favourite birthday was my eighteenth. My father bought me a blue Hero bicycle, and I rode it to the market every morning for twenty years.

I became a schoolteacher because I loved watching children understand mathematics for the first time. Teaching fractions with mangoes always worked better than any textbook.

When I retired, I started a small garden with tomatoes, chillies and tulsi. Gardening taught me patience.

With love, Amma"""


def b64(data):
    return base64.b64encode(data if isinstance(data, bytes) else data.encode("utf-8")).decode()


def _docx_bytes(*paragraphs):
    document = docx.Document()
    for p in paragraphs:
        document.add_paragraph(p)
    buf = io.BytesIO()
    document.save(buf)
    return buf.getvalue()


@pytest.fixture(scope="module")
def persona(client):
    """A custom model built through the API; always deleted afterwards."""
    r = client.post("/personas", json={"name": "pytest Amma", "description": "Retired teacher", "relationship": "family", "consent": True})
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    yield pid
    client.delete(f"/personas/{pid}")
    assert ps.load_persona(pid) is None and not (ps.CUSTOM_DIR / pid).exists()


def test_elon_is_listed_as_ready(client):
    elon = next(p for p in client.get("/personas").json() if p["id"] == "elon_musk")
    assert elon["kind"] == "pretrained" and elon["status"] == "ready" and elon["memories"] > 16000


def test_consent_is_required(client):
    r = client.post("/personas", json={"name": "pytest no consent", "relationship": "self", "consent": False})
    assert r.status_code == 400


def test_new_model_is_private_draft(client, persona):
    p = client.get(f"/personas/{persona}").json()
    assert p["status"] == "draft" and p["allow_cloud_llm"] is False
    assert client.post("/chat", json={"query": "hello there friend", "persona": persona}).status_code == 409


def test_upload_text_and_word(client, persona):
    r = client.post(f"/personas/{persona}/documents", json={"filename": "letter.txt", "content_base64": b64(LETTER)})
    assert r.status_code == 200 and r.json()["upload"]["memories"] >= 3
    before = r.json()["persona"]["memories"]
    again = client.post(f"/personas/{persona}/documents", json={"filename": "letter.txt", "content_base64": b64(LETTER)})
    assert again.json()["persona"]["memories"] == before  # re-upload replaces
    word = _docx_bytes("My mother taught me never to waste food, and to cook dal for twelve people with whatever was left.",
                       "I kept every letter my students ever wrote me in a tin box under the bed.")
    r = client.post(f"/personas/{persona}/documents", json={"filename": "notes.docx", "content_base64": b64(word)})
    assert r.status_code == 200 and r.json()["upload"]["memories"] >= 1


@pytest.mark.parametrize("filename,content,status", [
    ("virus.exe", b64("x" * 50), 400), ("a.txt", "not base64!!", 400), ("fake.docx", b64("not a zip"), 400),
])
def test_bad_uploads_are_refused(client, persona, filename, content, status):
    r = client.post(f"/personas/{persona}/documents", json={"filename": filename, "content_base64": content})
    assert r.status_code == status
    assert not (ps.CUSTOM_DIR / persona / "uploads" / filename).exists()


def test_filename_cannot_escape_uploads_folder(client, persona):
    r = client.post(f"/personas/{persona}/documents", json={"filename": "../../escape.txt", "content_base64": b64(LETTER)})
    assert r.status_code == 200 and not (ps.ROOT / "escape.txt").exists()
    assert (ps.CUSTOM_DIR / persona / "uploads" / "escape.txt").exists()


def test_interview_answers_replace_not_duplicate(client, persona):
    for qid, answer in [("Q1", "I am patient and stubborn, a teacher at heart."), ("Q5", "The flood of 1987 shaped me.")]:
        r = client.post(f"/personas/{persona}/interview", json={"question_id": qid, "answer": answer})
        assert r.status_code == 200 and qid in r.json()["persona"]["interview_answered"]
    count = client.get(f"/personas/{persona}").json()["memories"]
    client.post(f"/personas/{persona}/interview", json={"question_id": "Q1", "answer": "Calm and curious.", "origin": "family"})
    assert client.get(f"/personas/{persona}").json()["memories"] == count


def test_build_then_chat_from_her_own_memories(srv, client, persona):
    assert client.post(f"/personas/{persona}/build").json()["status"] == "ready"
    d = client.post("/chat", json={"query": "What was your favourite birthday?", "persona": persona, "mode": "natural"}).json()
    assert "bicycle" in d["answer"].lower()
    assert d["mode"] == "mix_method" and "cloud" in d["notice"]  # AI voice needs the creator's opt-in
    assert d["sources"][0]["voice"] == "first_person" and d["answer"].startswith("In my own words:")
    assert all(s["source_file"] in ("letter.txt", "escape.txt", "notes.docx", "interview_protocol") for s in d["sources"])
    assert "First principles" not in d["answer"]  # no Elon-style sign-off


def _wav(seconds):
    import wave
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(16000)
        w.writeframes(b"\x00\x00" * int(16000 * seconds))
    return buf.getvalue()


def _fish_voice_id(persona):
    return ps.load_persona(persona)["voice"]["fish_voice_id"]


def test_voice_needs_consent_and_a_real_recording(client, persona, fake_fish):
    url = f"/personas/{persona}/voice"
    ok = {"content_base64": b64(_wav(8)), "consent": True, "cloud": True}
    assert client.post(url, json={**ok, "consent": False}).status_code == 400
    assert client.post(url, json={**ok, "cloud": False}).status_code == 400  # must agree to Fish Audio
    assert client.post(url, json={**ok, "content_base64": b64("not audio")}).status_code == 400
    assert client.post(url, json={**ok, "content_base64": b64(_wav(2))}).status_code == 400  # too short
    assert not fake_fish.requests  # refused recordings never leave this computer
    r = client.post(url, json=ok)
    assert r.status_code == 200 and r.json()["voice"] == {"seconds": 8.0, "provider": "Fish Audio"}
    [create] = fake_fish.requests
    assert create.method == "POST" and create.url.path == "/model"
    assert b'name="visibility"\r\n\r\nprivate' in create.content and create.headers["authorization"] == "Bearer test-key-not-real"
    assert ps.voice_path(ps.load_persona(persona)).exists() and _fish_voice_id(persona).startswith("fishvoice")


def test_new_recording_replaces_the_old_cloud_voice(client, persona, fake_fish):
    old = _fish_voice_id(persona)
    r = client.post(f"/personas/{persona}/voice", json={"content_base64": b64(_wav(9)), "consent": True, "cloud": True})
    assert r.status_code == 200 and _fish_voice_id(persona) != old
    assert [(q.method, q.url.path) for q in fake_fish.requests] == [("POST", "/model"), ("DELETE", f"/model/{old}")]


def test_speak_uses_the_private_cloud_voice(client, persona, fake_fish, monkeypatch):
    r = client.post("/speak", json={"text": "Hello Ravi.", "persona": persona})
    assert r.status_code == 200 and r.headers["content-type"] == "audio/mpeg" and r.headers["x-chronus-voice"] == "cloned"
    [call] = fake_fish.requests
    assert call.url.path == "/v1/tts" and call.headers["model"] == "s2.1-pro-free"
    assert json.loads(call.content) == {"text": "Hello Ravi.", "reference_id": _fish_voice_id(persona), "format": "mp3"}
    # Fish problems are explained instead of failing silently
    fake_fish.fail["POST"] = 402
    r = client.post("/speak", json={"text": "Another line.", "persona": persona})
    assert r.status_code == 503 and "credit" in r.json()["detail"]
    monkeypatch.delenv("FISH_API_KEY")
    r = client.post("/speak", json={"text": "A third line.", "persona": persona})
    assert r.status_code == 503 and "FISH_API_KEY" in r.json()["detail"]


def test_voice_can_be_removed(client, persona, fake_fish):
    voice_id = _fish_voice_id(persona)
    fake_fish.fail["DELETE"] = 500  # Fish down: keep everything rather than orphan the cloud copy
    assert client.delete(f"/personas/{persona}/voice").status_code == 502
    assert ps.load_persona(persona)["voice"] and ps.voice_path(ps.load_persona(persona)).exists()
    fake_fish.fail.clear()
    summary = client.delete(f"/personas/{persona}/voice").json()
    assert summary["voice"] is None and summary["stand_in_voice"] is False
    assert ("DELETE", f"/model/{voice_id}") in [(q.method, q.url.path) for q in fake_fish.requests]
    assert not ps.voice_path(ps.load_persona(persona)).exists()
    # No consented voice and no stand-in for custom models: nothing to speak with
    assert client.post("/speak", json={"text": "Hello Ravi.", "persona": persona}).status_code == 404


def test_deleting_a_model_deletes_its_cloud_voice(client, fake_fish):
    r = client.post("/personas", json={"name": "pytest Voice only", "description": "Voice test", "relationship": "self", "consent": True})
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    client.post(f"/personas/{pid}/voice", json={"content_base64": b64(_wav(7)), "consent": True, "cloud": True})
    voice_id = _fish_voice_id(pid)
    assert client.delete(f"/personas/{pid}").status_code == 200 and ps.load_persona(pid) is None
    assert ("DELETE", f"/model/{voice_id}") in [(q.method, q.url.path) for q in fake_fish.requests]


def test_elon_has_none_of_her_memories(client):
    d = client.post("/chat", json={"query": "What was your favourite birthday?", "mode": "mix_method"}).json()
    assert "letter.txt" not in [s["source_file"] for s in d["sources"]]


def test_pretrained_models_are_protected(client):
    assert client.post("/personas/elon_musk/documents", json={"filename": "x.txt", "content_base64": b64(LETTER)}).status_code == 403
    assert client.delete("/personas/elon_musk").status_code == 403
    assert client.post("/chat", json={"query": "hello there", "persona": "nobody_here"}).status_code == 404
