"""Consent that can change (services/consent.py): pause, revoke, review date,
off-limits topics and never-quote memories."""

import base64
from datetime import date, timedelta

import pytest

from services import personas as ps

DIARY = "\n\n".join([
    "The divorce papers are in the steel cupboard in the hall, under the old photo albums.",
    "My favourite birthday was my eighteenth, when my father gave me a blue bicycle.",
    "I taught mathematics at the village school for thirty years and loved every morning of it.",
    "Every Diwali I made besan laddoos for the whole street and the children queued at our gate.",
    "The monsoon of 1987 flooded the village and we carried the goats up to the temple steps.",
    "When I retired I grew tomatoes, chillies and tulsi in a small garden behind the house.",
    "My mother taught me never to waste food and to cook dal for twelve people from almost nothing.",
    "I kept every letter my students ever wrote me in a tin box under the bed.",
    "On Sunday mornings we walked to the lake and your grandfather named every bird we saw.",
    "The proudest day of my life was when my first student became a doctor and came back to teach.",
    "Teaching fractions with mangoes always worked better than any textbook ever did.",
    "I learned to ride a scooter at fifty and drove it to the market every single day after that.",
])


@pytest.fixture(scope="module")
def model(client):
    r = client.post("/personas", json={"name": "pytest Consent", "description": "x", "relationship": "family", "consent": True})
    pid = r.json()["id"]
    client.post(f"/personas/{pid}/documents", json={"filename": "diary.txt",
                                                    "content_base64": base64.b64encode(DIARY.encode()).decode()})
    assert client.post(f"/personas/{pid}/build").status_code == 200
    yield pid
    client.delete(f"/personas/{pid}")


def _ask(client, pid, question):
    return client.post("/chat", json={"query": question, "persona": pid, "mode": "mix_method"})


def test_off_limits_topics_are_refused_and_never_quoted(client, model):
    r = client.put(f"/personas/{model}/off-limits", json={"topics": ["divorce", "Divorce"]})
    assert r.status_code == 200 and r.json()["off_limits"] == ["divorce"]  # duplicates dropped
    d = _ask(client, model, "Where are the divorce papers?").json()
    assert d["mode"] == "off_limits" and d["sources"] == [] and "divorce papers are" not in d["answer"].lower()
    # Another question that would reach the same memory never quotes it either
    d = _ask(client, model, "What is in the steel cupboard in the hall?").json()
    assert "divorce" not in d["answer"].lower()
    client.put(f"/personas/{model}/off-limits", json={"topics": []})


def test_never_quote_memories_stay_out_of_answers(client, model):
    found = client.get(f"/personas/{model}/memories", params={"q": "blue bicycle birthday"}).json()["items"][0]
    assert "bicycle" in found["text"]
    r = client.put(f"/personas/{model}/memories/{found['id']}/never-quote", json={"never_quote": True})
    assert r.status_code == 200 and r.json()["never_quote"] is True
    d = _ask(client, model, "What was your favourite birthday?").json()
    assert found["id"] not in [s["memory_id"] for s in d["sources"]] and "blue bicycle" not in d["answer"]
    client.put(f"/personas/{model}/memories/{found['id']}/never-quote", json={"never_quote": False})


def test_pause_resume_and_review_date(client, model):
    assert client.post(f"/personas/{model}/consent", json={"action": "pause"}).json()["status"] == "paused"
    r = _ask(client, model, "What did you teach?")
    assert r.status_code == 423 and "paused" in r.json()["detail"]
    assert client.post(f"/personas/{model}/consent", json={"action": "resume"}).json()["status"] == "active"
    assert _ask(client, model, "What did you teach?").status_code == 200
    # Past the review date the model pauses itself until consent is renewed
    ps.update_persona(model, consent_review_by=(date.today() - timedelta(days=1)).isoformat())
    assert _ask(client, model, "What did you teach?").status_code == 423
    assert client.post(f"/personas/{model}/consent", json={"action": "resume"}).status_code == 409
    renewed = client.post(f"/personas/{model}/consent", json={"action": "renew"}).json()
    assert renewed["review_due"] is False and renewed["review_by"] > date.today().isoformat()
    assert _ask(client, model, "What did you teach?").status_code == 200
    history = client.get(f"/personas/{model}/consent").json()["history"]
    statuses = [e["consent_status"] for e in history if "consent_status" in e]
    assert statuses[:3] == ["paused", "active", "active"] and any("off_limits" in e for e in history)  # every change kept


def test_revoking_consent_deletes_the_model(client):
    pid = client.post("/personas", json={"name": "pytest Revoke", "description": "x", "relationship": "family",
                                         "consent": True}).json()["id"]
    assert client.post(f"/personas/{pid}/consent", json={"action": "revoke"}).json() == {"deleted": pid}
    assert ps.load_persona(pid) is None and client.get(f"/personas/{pid}").status_code == 404


def test_pretrained_models_have_no_consent_to_change(client):
    assert client.post("/personas/elon_musk/consent", json={"action": "pause"}).status_code == 403
    assert client.put("/personas/albert_einstein/off-limits", json={"topics": ["relativity"]}).status_code == 403
    assert client.put("/personas/elon_musk/memories/x/never-quote", json={"never_quote": True}).status_code == 403


def test_consent_is_recorded_in_the_language_it_was_read_in(client):
    gujarati = client.get("/consent-text", params={"lang": "gu"}).json()
    assert gujarati["language"] == "gu" and "પરવાનગી" in gujarati["model"] and "Fish Audio" in gujarati["voice"]
    assert "अनुमति" in client.get("/consent-text", params={"lang": "hi"}).json()["model"]
    assert client.get("/consent-text", params={"lang": "xx"}).status_code == 422
    pid = client.post("/personas", json={"name": "pytest Gujarati", "description": "x", "relationship": "family",
                                         "consent": True, "language": "gu"}).json()["id"]
    try:
        record = ps.load_persona(pid)["consent"]
        assert record["language"] == "gu" and record["statement"] == gujarati["model"]  # exactly what was shown
    finally:
        client.delete(f"/personas/{pid}")
