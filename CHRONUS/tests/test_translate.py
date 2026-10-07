"""Multilingual chat (services/translate.py)."""

from unittest import mock

import pytest

from services import translate


@pytest.mark.parametrize("text,lang", [
    ("आप मंगल ग्रह क्यों जाना चाहते हैं?", "hi"), ("તમે મંગળ પર કેમ જવા માંગો છો?", "gu"),
    ("Why Mars?", "en"), ("Mars kyun jaana hai?", "en"), ("1971?", "en"),
])
def test_detect(text, lang):
    assert translate.detect(text) == lang


def test_question_in_hindi_without_ai_is_explained(client, monkeypatch):
    monkeypatch.setattr(translate, "available", lambda persona: False)
    d = client.post("/chat", json={"query": "आप मंगल ग्रह क्यों जाना चाहते हैं?", "mode": "mix_method"}).json()
    assert d["fallback"] and d["language"] == "hi" and "Hindi" in d["notice"]


def test_hindi_round_trip(client, monkeypatch):
    calls = []

    def fake_translate(text, target, source=None):
        calls.append((target, source))
        return "When were you born?" if target == "en" else "मेरा जन्म 28 जून 1971 को हुआ था।"
    monkeypatch.setattr(translate, "available", lambda persona: True)
    monkeypatch.setattr(translate, "translate", fake_translate)
    d = client.post("/chat", json={"query": "आपका जन्म कब हुआ था?", "mode": "mix_method"}).json()
    assert calls == [("en", "hi"), ("hi", "en")]
    assert d["language"] == "hi" and "1971" in d["original_answer"] and d["answer"].startswith("मेरा")
    assert "Translated by AI" in d["notice"]


def test_english_question_answered_in_gujarati_on_request(client, monkeypatch):
    monkeypatch.setattr(translate, "available", lambda persona: True)
    monkeypatch.setattr(translate, "translate", lambda text, target, source=None: f"[{target}] {text}")
    d = client.post("/chat", json={"query": "When were you born?", "language": "gu"}).json()
    assert d["language"] == "gu" and d["answer"].startswith("[gu] ") and d["original_answer"]


def test_translation_failure_keeps_english(client, monkeypatch):
    monkeypatch.setattr(translate, "available", lambda persona: True)
    monkeypatch.setattr(translate, "translate", mock.Mock(side_effect=RuntimeError("quota")))
    d = client.post("/chat", json={"query": "When were you born?", "language": "hi"}).json()
    assert d["language"] == "en" and "Couldn't translate" in d["notice"] and "1971" in d["answer"]
