"""HTTP API: validation, security, and the Phase 6 regression checks (no live server needed)."""

import re
from unittest import mock

import pytest

from services.mix_method import clean_for_display
from services.theme_classifier import classify_theme

FALLBACK_MSG = "I don't have any documented information about that in my available records."


def _chat(client, query, **extra):
    r = client.post("/chat", json={"query": query, "mode": "mix_method", **extra})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.parametrize("body", [
    {"query": "   "}, {"query": "hi there", "mode": "foo"}, {"query": "Mars?", "n_results": 500},
    {"query": "Mars?", "history": [{"role": "user", "content": "x"}] * 21}, {"query": "a" * 1001},
    {"query": "Mars?", "persona": "../etc"},
])
def test_chat_rejects_bad_input(client, body):
    assert client.post("/chat", json=body).status_code == 422


def test_interview_writes_need_json(srv, client):
    # Patch the whole write path: it deletes the old answer before saving
    with mock.patch.object(srv, "embed_interview_answer", return_value={"dimension": "personality", "memory_id": "x"}) as emb:
        assert client.post("/interview/answer?question_id=Q1&answer=fake").status_code == 422
        r = client.post("/interview/answer", content='{"question_id":"Q1","answer":"fake"}', headers={"content-type": "text/plain"})
        assert r.status_code == 422  # cross-site form posts can't send JSON without a preflight
        assert client.post("/interview/answer", json={"question_id": "Q1", "answer": "x", "origin": "family"}).status_code == 200
    assert emb.call_count == 1 and emb.call_args.args[3].origin == "family"


def test_speak_never_clones_public_figures(srv, client):
    # No client-supplied file paths any more
    assert client.post("/speak", json={"text": "hi", "speaker_wav": "../../.env"}).status_code == 422
    assert client.post("/speak", json={"text": "hi", "persona": "nobody_here"}).status_code == 404
    # Elon gets his labelled synthetic stand-in voice, never the cloning path
    with mock.patch.object(srv.tts, "stand_in_wav", return_value=b"RIFF....WAVE") as stand_in, \
            mock.patch.object(srv.tts, "fish_speech") as fish:
        r = client.post("/speak", json={"text": "hi", "persona": "elon_musk"})
    assert r.status_code == 200 and r.headers["content-type"] == "audio/wav"
    assert r.headers["x-chronus-voice"] == "stand-in" and r.content == b"RIFF....WAVE"
    stand_in.assert_called_once_with("hi", "am_michael")
    fish.assert_not_called()


def test_stats_reports_real_models(srv, client):
    stats = client.get("/stats").json()
    assert stats["llm_model"] == srv.config.OPENAI_MODEL and stats["embedding_model"] == srv.config.EMBEDDING_MODEL


def test_root_serves_the_react_site(srv, client):
    if not (srv.SITE_DIR / "index.html").exists():
        pytest.skip("website not built (npm run build)")
    r = client.get("/")
    assert r.status_code == 200 and '<div id="root">' in r.text
    assert r.headers["cache-control"] == "no-cache"  # so browsers never keep showing an old page
    assert client.get("/health").status_code == 200  # API routes still win over the site mount


# ---- Phase 6 regression (originally 06-Testing/_phase6_tests.py) ----

@pytest.mark.corpus
def test_6_1_high_confidence_query(client):
    d = _chat(client, "What is the goal of SpaceX?")
    assert not d["fallback"] and d["confidence"] == "high" and d["sources"]
    assert 0 < d["faithfulness"] <= 1


@pytest.mark.corpus
def test_6_2_unanswerable_question_falls_back(client):
    # Calibrated threshold (config.DISTANCE_THRESHOLD). The original pizza
    # question sits in the grey zone (0.51; he tweets about food) and is
    # answered with medium confidence instead; see evaluation/run_eval.py.
    d = _chat(client, "How do I descale a kettle?")
    assert d["fallback"] is True and d["confidence"] == "low" and d["answer"] == FALLBACK_MSG and d["sources"] == []


@pytest.mark.parametrize("question,theme", [
    ("Tell me about your kids", "love_relationships"), ("What's the mission of Tesla?", "work_purpose"),
    ("What scares you the most?", "fear_resilience"), ("What is the meaning of life?", "meaning"),
    ("What was your biggest mistake?", "failure_growth"), ("Why did you buy Twitter?", "change_decisions"),
    ("Will humanity survive?", "humanity_society"),
])
def test_6_3_theme_classification(question, theme):
    assert classify_theme(question)["theme"] == theme


@pytest.mark.corpus
def test_6_4_quote_is_verbatim_from_its_source(srv, client):
    d = _chat(client, "What do you think about artificial intelligence?")
    source = d["sources"][0]
    assert {"citation", "quote", "source_type", "source_file", "voice", "memory_id", "distance"} <= source.keys()
    part1 = d["answer"].split("\n\n")[0]
    quote = part1[part1.find('"') + 1: part1.rfind('"')].strip("…")
    full = srv.collection.get(ids=[source["memory_id"]])["documents"][0]
    norm = lambda s: re.sub(r"\s+", " ", s).strip().lower()  # noqa: E731
    # Quotes are the memory's own words with transcript noise removed (clean_for_display)
    assert quote and norm(quote) in norm(clean_for_display(full))


@pytest.mark.corpus
def test_6_6_interview_answers_are_retrievable_and_labelled(client):
    d = _chat(client, "How would you describe your personality?")
    interview = [s for s in d["sources"] if s["source_type"] == "interview_protocol"]
    assert interview and all(s["voice"] == "synthesized" for s in interview)
    assert d["answer"].startswith("My interview profile, which is a summary rather than a direct quote")
