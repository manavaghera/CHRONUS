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


@pytest.mark.parametrize("text", [
    "मैं आत्महत्या करना चाहता हूँ", "मुझे मरना है", "अब जीना नहीं चाहती", "ख़ुदकुशी के बारे में सोचता हूं",
    "मैं खुद को खत्म कर दूंगा", "મારે આપઘાત કરવો છે", "મને હવે જીવવું નથી", "મારે મરી જવું છે",
    "mare marvu che", "mane jivvu nathi", "aapghat no vichar aave che", "atmahatya",
])
def test_crisis_language_in_hindi_and_gujarati_is_caught(text):
    assert wellbeing.needs_support(text)


@pytest.mark.parametrize("text", [
    "आपका बचपन कैसा था?", "आप कहाँ पैदा हुए थे?", "તમારું બાળપણ કેવું હતું?", "aap ghat par gaye the?",
])
def test_ordinary_hindi_and_gujarati_questions_are_not(text):
    assert not wellbeing.needs_support(text)


def test_support_message_comes_in_their_script_with_every_helpline():
    hindi, gujarati = wellbeing.support_message("मुझे मरना है"), wellbeing.support_message("મારે મરવું છે")
    assert hindi.startswith(wellbeing.SUPPORT_MESSAGE_HI) and gujarati.startswith(wellbeing.SUPPORT_MESSAGE_GU)
    assert all(wellbeing.SUPPORT_MESSAGE in m and "14416" in m and "112" in m for m in (hindi, gujarati))
    assert wellbeing.support_message("I want to die") == wellbeing.SUPPORT_MESSAGE


def test_native_script_crisis_gets_helplines_without_translation(client):
    # It used to fall through to "my archive is in English" when translation wasn't set up
    d = client.post("/chat", json={"query": "मैं आत्महत्या करना चाहता हूँ", "mode": "mix_method"}).json()
    assert d["mode"] == "support" and d["answer"].startswith(wellbeing.SUPPORT_MESSAGE_HI) and len(d["helplines"]) == 4


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
