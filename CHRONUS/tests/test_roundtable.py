"""Roundtable (services/roundtable.py): several models, one question."""

import base64

import pytest

from services import personas as ps

TEXTS = {
    "Gardener": "In my garden I grew mangoes, tomatoes and tulsi, and gardening taught me that patience beats force every time.",
    "Teacher": "Teaching fractions with mangoes worked better than any textbook, because patience with children beats force.",
}


@pytest.fixture(scope="module")
def seats(client):
    ids = []
    for name, text in TEXTS.items():
        pid = client.post("/personas", json={"name": f"pytest {name}", "relationship": "self", "consent": True}).json()["id"]
        body = "\n\n".join([text] * 1 + [f"{text} Memory number {i} of my long life, written down for my family." for i in range(10)])
        client.post(f"/personas/{pid}/documents", json={"filename": "life.txt", "content_base64": base64.b64encode(body.encode()).decode()})
        assert client.post(f"/personas/{pid}/build").status_code == 200, client.get(f"/personas/{pid}").json()
        p = ps.load_persona(pid)
        p["distance_threshold"] = 1.0  # hash embedder in the sample setup
        ps.save_persona(p)
        ids.append(pid)
    yield ids
    for pid in ids:
        client.delete(f"/personas/{pid}")


def test_each_model_answers_from_its_own_archive(client, seats):
    r = client.post("/roundtable", json={"query": "What does patience mean to you?", "personas": seats, "mode": "mix_method"})
    assert r.status_code == 200
    answers = r.json()["answers"]
    assert [a["persona"] for a in answers] == seats and r.json()["replies"] == []
    for a in answers:
        assert all(s["source_file"] == "life.txt" for s in a["sources"])


def test_models_reply_to_each_other(client, seats):
    d = client.post("/roundtable", json={"query": "What does patience mean to you?", "personas": seats, "respond": True}).json()
    assert [(r["persona"], r["replying_to"]) for r in d["replies"]] == [(seats[0], seats[1]), (seats[1], seats[0])]


@pytest.mark.parametrize("ids,status", [(["elon_musk"], 422), (["elon_musk", "elon_musk"], 422), (["elon_musk", "nobody_here"], 404)])
def test_bad_seating(client, ids, status):
    assert client.post("/roundtable", json={"query": "Why?", "personas": ids}).status_code == status
