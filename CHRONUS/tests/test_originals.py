"""Show the original (services/originals.py): voice notes keep each memory's
moment in the recording; photos and scanned letters are read on this
computer and stay viewable."""

import base64
import io
import struct
import types
import wave

import pytest

from services import originals
from services import personas as ps

LINES = ["My dearest Ravi, the monsoon came early this year.", "The river rose over the steps of the old temple."]


@pytest.fixture
def model(client):
    pid = client.post("/personas", json={"name": "pytest Originals", "description": "x", "relationship": "family",
                                         "consent": True}).json()["id"]
    yield pid
    client.delete(f"/personas/{pid}")


def _upload(client, pid, filename, data):
    return client.post(f"/personas/{pid}/documents", json={"filename": filename,
                                                          "content_base64": base64.b64encode(data).decode()})


def _letter_image():
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", (1400, 420), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=44)
    for i, line in enumerate(LINES):
        draw.text((40, 60 + i * 150), line, fill="black", font=font)
    return image


def _memories(client, pid):
    return client.get(f"/personas/{pid}/memories").json()["items"]


@pytest.mark.skipif(originals.ocr_engine() is None, reason="pip install rapidocr-onnxruntime")
def test_a_photo_of_a_letter_is_read_and_stays_viewable(client, model):
    buf = io.BytesIO()
    _letter_image().save(buf, "PNG")
    r = _upload(client, model, "letter.png", buf.getvalue())
    assert r.status_code == 200 and r.json()["upload"]["kind"] == "image"
    text = " ".join(m["text"] for m in _memories(client, model)).lower()
    assert "monsoon" in text and "temple" in text
    memory = _memories(client, model)[0]
    assert memory["original"] == {"kind": "image", "file": "letter.png"}
    original = client.get(f"/personas/{model}/uploads/letter.png/original")
    assert original.status_code == 200 and original.headers["content-type"] == "image/png"
    assert original.content == buf.getvalue()


@pytest.mark.skipif(originals.ocr_engine() is None, reason="pip install rapidocr-onnxruntime")
def test_a_scanned_pdf_with_no_text_layer_is_read(client, model):
    buf = io.BytesIO()
    _letter_image().save(buf, "PDF")  # an image-only page, like a scanner makes
    r = _upload(client, model, "scan.pdf", buf.getvalue())
    assert r.status_code == 200
    memory = _memories(client, model)[0]
    assert "monsoon" in memory["text"].lower() and memory["original"] == {"kind": "scan", "file": "scan.pdf", "page": 1}


def _wav(seconds=6.0):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(16000)
        w.writeframes(struct.pack("<h", 0) * int(16000 * seconds))
    return buf.getvalue()


def test_voice_notes_keep_each_memorys_moment(srv, client, model, monkeypatch):
    from services import stt

    said = [("My father bought me a blue bicycle when I turned eighteen, and I rode it everywhere.", 0.0, 4.2),
            ("Every Diwali I made laddoos for the whole street, and the children queued at our gate.", 64.5, 70.0)]
    segments = [types.SimpleNamespace(text=t, start=s, end=e) for t, s, e in said]
    monkeypatch.setattr(stt, "available", lambda: True)
    monkeypatch.setattr(stt, "_whisper", lambda: types.SimpleNamespace(transcribe=lambda *a, **k: (iter(segments), None)))
    monkeypatch.setattr(originals, "PARAGRAPH_CHARS", 60)  # one memory per sentence here
    data = _wav()
    assert _upload(client, model, "note.wav", data).json()["upload"]["kind"] == "audio"
    diwali = next(m for m in _memories(client, model) if "Diwali" in m["text"])
    assert diwali["original"] == {"kind": "audio", "file": "note.wav", "start": 64.5, "end": 70.0, "at": "1:04"}
    persona = ps.load_persona(model)
    answer = srv.answer_from_memory("What did you make at Diwali?", {**persona, "distance_threshold": 2.0},
                                    ps.get_collection(srv.client, persona), "mix_method", [])
    assert any((s.get("original") or {}).get("start") == 64.5 for s in answer["sources"])
    played = client.get(f"/personas/{model}/uploads/note.wav/original")
    assert played.status_code == 200 and played.headers["content-type"] == "audio/wav" and played.content == data


def test_only_a_models_own_uploads_are_served(client, model):
    assert client.get(f"/personas/{model}/uploads/persona.json/original").status_code == 404
    assert client.get(f"/personas/{model}/uploads/..%2Fpersona.json/original").status_code == 404
    assert client.get("/personas/elon_musk/uploads/x.wav/original").status_code == 404
