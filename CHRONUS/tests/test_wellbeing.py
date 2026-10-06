"""Wellbeing safeguards (services/wellbeing.py)."""

import pytest

from services import wellbeing


@pytest.mark.parametrize("text", [
    "I want to die", "sometimes I think about ending my life", "I can't go on without you", "I'll join you soon",
    "everyone would be better off without me", "I've been self-harming again", "suicidal thoughts", "main marna chahti hoon",
])
def test_crisis_language_is_caught(text):
    assert wellbeing.needs_support(text)


@pytest.mark.parametrize("text", [
    "Why did the rocket die on the pad?", "How did you handle the death of your father?", "What killed the Roadster deal?",
    "Tell me about your childhood", "Is AI dangerous?",
])
def test_ordinary_questions_are_not(text):
    assert not wellbeing.needs_support(text)


def test_chat_steps_out_of_character_and_withholds_the_message(srv, client, monkeypatch):
    logged = []
    monkeypatch.setattr(srv, "log_qa", lambda *a, **k: logged.append((a, k)) or "abc")
    d = client.post("/chat", json={"query": "I want to die so I can be with you again", "mode": "natural"}).json()
    assert d["mode"] == "support" and "14416" in d["answer"] and "988" in d["answer"] and d["sources"] == []
    assert len(d["helplines"]) == 4
    [(args, _)] = logged
    assert "die" not in args[0]  # the message itself isn't stored


def test_memorial_style_and_flag(client):
    p = {"style_notes": "Warm."}
    assert wellbeing.style_for(p) == "Warm."
    assert "Never claim to be alive" in wellbeing.style_for({**p, "memorial": True})
    r = client.post("/personas", json={"name": "pytest Memorial", "relationship": "family", "consent": True, "memorial": True})
    try:
        assert r.json()["memorial"] is True
    finally:
        client.delete(f"/personas/{r.json()['id']}")
