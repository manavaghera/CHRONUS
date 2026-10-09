"""
The person model: identity profile (services/identity.py), "in their spirit"
answers (services/spirit.py), the style layer (services/style.py,
lora/pipeline.py) and their endpoints (services/person_routes.py).
Every LLM call is mocked; nothing trains.
"""

import json
from datetime import datetime, timedelta, timezone

import pytest

import lora.pipeline as pipeline
from services import identity, spirit, style
from services import personas as ps
from services.embedder import HashEmbedder


class FakeCollection:
    """Just enough of a Chroma collection: get(where=...) and count()."""

    def __init__(self, rows):
        self.rows = rows  # [(doc, meta)]

    def count(self):
        return len(self.rows)

    def get(self, where=None, include=None, **_):
        def match(meta):
            if not where:
                return True
            key, value = next(iter(where.items()))
            return meta.get(key) in value["$in"] if isinstance(value, dict) else meta.get(key) == value
        rows = [(d, m) for d, m in self.rows if match(m)]
        return {"documents": [d for d, _ in rows], "metadatas": [m for _, m in rows]}


def _interview(qid, dimension, answer, origin="self", question="How would you describe yourself?"):
    meta = {"source_type": "interview_protocol", "question_id": qid, "dimension": dimension, "origin": origin,
            "memory_id": f"int_{qid}", "parent_text": question}
    return (f"[Interview Response] Q: {question} A: {answer}", meta)


# ---- Identity profile ----

def test_searched_sentences_must_be_clean_first_person_statements():
    assert identity._usable("I care about the truth very much, more than anything else.", spoken=False)
    assert not identity._usable("The truth matters a great deal to everyone in the room.", spoken=False)  # not about them
    assert not identity._usable("Honestly, sometimes I wonder what what's wrong with me.", spoken=True)  # stutter
    assert not identity._usable("I think, you know, that is how I work every single day.", spoken=True)  # filler
    assert not identity._usable("Do I really care about the truth that much these days?", spoken=False)


def test_interview_answers_become_lines_by_dimension_and_voice():
    rows = [
        _interview("Q1", "personality", "I am stubborn and kind. I never give up on a student."),
        _interview("Q9", "relationships", "She adored her grandchildren more than anything.", origin="family"),
        _interview("Q17", "beliefs_values", "Honesty above all, always and in everything.", origin="synthesized"),
    ]
    lines = identity._interview_lines(FakeCollection(rows), HashEmbedder())
    by_q = {line["memory_id"]: line for line in lines}
    assert by_q["int_Q1"]["section"] == "temperament" and by_q["int_Q1"]["voice"] == "own"
    assert by_q["int_Q9"]["section"] == "people" and by_q["int_Q9"]["voice"] == "about"
    assert "int_Q17" not in by_q  # an LLM's stand-in answer is never who they are


def test_prompt_block_labels_lines_and_respects_hidden():
    profile = {"lines": [
        {"id": "a" * 10, "section": "values", "text": "Honesty first.", "voice": "own", "memory_id": "m1"},
        {"id": "b" * 10, "section": "people", "text": "She loved her grandchildren.", "voice": "about", "memory_id": "m2"},
        {"id": "c" * 10, "section": "about", "text": "Born: 1950", "voice": "public", "memory_id": "profile"},
    ], "hidden": []}
    block = identity.prompt_block(profile)
    assert block.startswith("WHO YOU ARE") and '"Honesty first."' in block
    assert "said about you by someone who knew you" in block
    assert "Born: 1950" not in block  # public facts come from profile.profile_context_block()
    assert "Honesty first." not in identity.prompt_block({**profile, "hidden": ["a" * 10]})
    assert identity.prompt_block({"lines": []}) == ""


# ---- "In their spirit" ----

def test_spirit_is_opt_in_for_personal_models():
    assert spirit.allowed({"id": "elon_musk", "kind": "pretrained"})
    assert not spirit.allowed({"id": "x", "kind": "custom"})
    assert spirit.allowed({"id": "x", "kind": "custom", "allow_spirit": True})


def _spirit_call(monkeypatch, search_result, llm_mode="natural"):
    calls = []
    monkeypatch.setattr(identity, "get", lambda *a, **k: {"lines": []})

    def fake_llm(**kwargs):
        calls.append(kwargs)
        return {"response": "I never really talked about that, but honesty matters [1].", "mode": llm_mode,
                "sources": [{"citation": "x"}], "confidence": "medium", "faithfulness": 0.6, "fallback": False}
    monkeypatch.setattr(spirit, "generate_natural_response", fake_llm)
    result = spirit.answer("What would you think of crypto?", {"id": "p", "name": "Amma", "kind": "custom"},
                           FakeCollection([]), HashEmbedder(), search=lambda q: search_result,
                           profile_block="", history=[], style_notes=None)
    return result, calls


def test_spirit_answer_is_labelled_and_built_on_nearby_memories(monkeypatch):
    nearby = [(0.6, "I always saved for a rainy day.", {"memory_id": "m1", "source_type": "personal_writing"}, 0.6)]
    result, calls = _spirit_call(monkeypatch, nearby)
    assert result["mode"] == "spirit" and result["notice"] == spirit.NOTICE and result["confidence"] == "low"
    assert calls[0]["spirit"] is True and calls[0]["memories"] == nearby


def test_spirit_says_nothing_without_something_real_or_when_the_guard_rejects(monkeypatch):
    assert _spirit_call(monkeypatch, None) == (None, [])
    nearby = [(0.6, "I always saved.", {"memory_id": "m1", "source_type": "personal_writing"}, 0.6)]
    assert _spirit_call(monkeypatch, nearby, llm_mode="mix_method_fallback")[0] is None


def test_chat_uses_spirit_only_when_asked(client, srv, monkeypatch):
    monkeypatch.setattr(srv, "retrieve", lambda *a, **k: None)  # nothing in the archive covers it
    monkeypatch.setattr(spirit, "answer", lambda *a, **k: {
        "response": "I never talked about that, but...", "sources": [], "faithfulness": 0.7, "confidence": "low",
        "fallback": False, "mode": "spirit", "notice": spirit.NOTICE})
    body = {"query": "What do you think of my pottery class?", "persona": "elon_musk", "mode": "natural"}
    inferred = client.post("/chat", json={**body, "spirit": True}).json()
    assert inferred["mode"] == "spirit" and spirit.NOTICE in inferred["notice"]
    assert client.post("/chat", json=body).json()["mode"] == "fallback"
    assert client.post("/chat", json={**body, "mode": "mix_method", "spirit": True}).json()["mode"] == "fallback"


# ---- Style layer ----

@pytest.fixture
def custom(tmp_path, monkeypatch):
    monkeypatch.setattr(style, "folder", lambda persona: tmp_path / "adapters")
    return {"id": "pytest_style", "kind": "custom", "name": "Amma"}


def test_style_settings_default_off_for_personal_models(custom):
    assert style.settings(custom) == {"learn_style": False, "allow_spirit": False, "frozen": False}
    assert style.settings({"kind": "pretrained"})["learn_style"] is True


def test_only_a_promoted_adapter_is_used_and_only_on_the_local_model(custom, tmp_path, monkeypatch):
    persona = {**custom, "learn_style": True}
    (tmp_path / "adapters" / "v2").mkdir(parents=True)
    (tmp_path / "adapters" / "v2" / "adapter_config.json").write_text("{}")
    monkeypatch.setattr(style.config, "LLM_PROVIDER", "local")
    assert style.adapter_for(persona) is False  # trained but never promoted
    (tmp_path / "adapters" / "current.json").write_text(json.dumps({"version": 2, "path": "v2"}))
    assert style.adapter_for(persona).endswith("v2")
    assert style.adapter_for({**persona, "learn_style": False}) is False
    monkeypatch.setattr(style.config, "LLM_PROVIDER", "openrouter")
    assert style.adapter_for(persona) is False


def test_a_run_that_stopped_reporting_counts_as_failed(custom, tmp_path):
    (tmp_path / "adapters").mkdir()
    old = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()
    (tmp_path / "adapters" / "run.json").write_text(json.dumps({"state": "running", "started": old, "updated": old}))
    assert style.run_state(custom)["state"] == "failed"


def test_auto_train_waits_for_consent_enough_words_and_the_local_model(custom, monkeypatch):
    started = []
    monkeypatch.setattr(style, "start", lambda persona: started.append(persona["id"]))
    many = [{"question": "q", "answer": "word " * 80, "memory_id": f"m{i}"} for i in range(style.MIN_PAIRS)]
    monkeypatch.setattr(style, "own_pairs", lambda collection: many)
    monkeypatch.setattr(style.config, "LLM_PROVIDER", "local")
    assert not style.maybe_auto_train(custom, None) and "Learn their style" in style.status(custom, None)["reason"]
    persona = {**custom, "learn_style": True}
    assert style.maybe_auto_train(persona, None) and started == ["pytest_style"]
    assert not style.maybe_auto_train({**persona, "frozen": True}, None)
    monkeypatch.setattr(style, "own_pairs", lambda collection: many[:3])
    assert "Needs" in style.status(persona, None)["reason"]


def test_exam_verdict():
    base = {"cosine": 0.40, "kept": 0.30}
    assert pipeline.verdict({"base": base, "candidate": {"cosine": 0.45, "kept": 0.30}})[0]
    assert not pipeline.verdict({"base": base, "candidate": {"cosine": 0.405, "kept": 0.30}})[0]  # no real gain
    assert not pipeline.verdict({"base": base, "candidate": {"cosine": 0.50, "kept": 0.10}})[0]   # less faithful
    assert not pipeline.verdict({"base": base, "candidate": {"cosine": 0.45, "kept": 0.30},
                                 "current": {"cosine": 0.47, "kept": 0.3}})[0]                    # worse than in use


def test_pairs_are_their_own_conversations_without_duplicates():
    rows = [
        _interview("Q1", "personality", "I am stubborn and kind and I never give up."),
        _interview("Q2", "personality", "Someone else answered this for them.", origin="family"),
        ("Exactly right, and it should be done this year.", {"source_type": "tweet", "memory_id": "t1",
                                                              "context_text": "We should build more rockets now https://x.co"}),
        ("Exactly right, and it should be done this year.", {"source_type": "tweet", "memory_id": "t2",
                                                              "context_text": "Another post saying the same thing here"}),
        ("A tweet that answered nothing at all today.", {"source_type": "tweet", "memory_id": "t3"}),
    ]
    pairs = pipeline.pairs_for(FakeCollection(rows))
    assert {p["memory_id"] for p in pairs} == {"int_Q1", "t1"}
    assert next(p for p in pairs if p["memory_id"] == "t1")["question"] == "We should build more rockets now"


def test_exam_questions_are_held_out_and_bounded():
    rows = [{"user": str(i)} for i in range(500)]
    train, exam = pipeline.split(rows)
    assert len(exam) == pipeline.EXAM_MAX and not {r["user"] for r in train} & {r["user"] for r in exam}
    assert len(pipeline.split(rows[:20])[1]) == pipeline.EXAM_MIN
    assert pipeline.split(rows) == (train, exam)  # same split every run


# ---- Endpoints ----

@pytest.fixture(scope="module")
def amma(client):
    r = client.post("/personas", json={"name": "pytest Person Model", "relationship": "family", "consent": True})
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    answer = {"question_id": "Q1", "answer": "I am stubborn but kind, and I never give up on a student."}
    assert client.post(f"/personas/{pid}/interview", json=answer).status_code == 200
    yield pid
    client.delete(f"/personas/{pid}")
    assert ps.load_persona(pid) is None


def test_identity_endpoint_and_hiding_a_line(client, amma):
    profile = client.get(f"/personas/{amma}/identity").json()
    line = next(ln for ln in profile["lines"] if "stubborn" in ln["text"])
    assert line["section"] == "temperament" and line["voice"] == "own" and not line["hidden"]
    hidden = client.put(f"/personas/{amma}/identity/lines/{line['id']}", json={"hidden": True}).json()
    assert next(ln for ln in hidden["lines"] if ln["id"] == line["id"])["hidden"]
    rebuilt = client.post(f"/personas/{amma}/identity/rebuild").json()  # a reviewer's choice survives rebuilds
    assert next(ln for ln in rebuilt["lines"] if ln["id"] == line["id"])["hidden"]
    assert client.put(f"/personas/{amma}/identity/lines/{'0' * 10}", json={"hidden": True}).status_code == 404


def test_settings_are_consent_decisions_on_personal_models_only(client, amma):
    assert client.put("/personas/elon_musk/person-settings", json={"allow_spirit": False}).status_code == 403
    assert client.put(f"/personas/{amma}/person-settings", json={}).status_code == 422
    flags = client.put(f"/personas/{amma}/person-settings", json={"allow_spirit": True, "learn_style": True}).json()
    assert flags == {"learn_style": True, "allow_spirit": True, "frozen": False}
    assert client.get(f"/personas/{amma}").json()["person_settings"]["allow_spirit"] is True
    history = ps.load_persona(amma, any_owner=True)["consent_history"]
    assert history[-1]["allow_spirit"] is True and history[-1]["learn_style"] is True


def test_style_endpoint_explains_what_is_missing(client, amma):
    state = client.get(f"/personas/{amma}/style").json()
    assert state["pairs"] == 1 and not state["ready"] and state["reason"]
    refused = client.post(f"/personas/{amma}/style/train")
    assert refused.status_code == 409 and refused.json()["detail"] == state["reason"]
    assert client.post("/personas/elon_musk/style/train").status_code == 403
