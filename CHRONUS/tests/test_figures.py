"""Public-domain famous-figure models (figures/build_figures.py)."""

import json

import pytest

from services import personas as ps
from services import tts

FIGURES = [f["id"] for f in json.loads((ps.ROOT / "figures" / "sources.json").read_text(encoding="utf-8"))["figures"]]


@pytest.fixture(scope="module")
def figures(client):
    listed = {p["id"]: p for p in client.get("/personas").json()}
    missing = [f for f in FIGURES if f not in listed]
    if missing:
        pytest.skip(f"figures not built yet (python figures/build_figures.py): {missing}")
    return {f: listed[f] for f in FIGURES}


@pytest.mark.parametrize("figure_id", FIGURES)
def test_figure_is_ready_with_its_own_threshold(figures, figure_id):
    p = figures[figure_id]
    assert p["kind"] == "pretrained" and p["status"] == "ready" and p["memories"] > 100
    assert p["license"].startswith("Public domain") and len(p["suggested_questions"]) == 4
    threshold = ps.load_persona(figure_id)["distance_threshold"]
    assert 0.58 <= threshold <= 0.68
    # Listen uses a synthetic stand-in voice, never a clone of the person
    assert p["stand_in_voice"] is True and p["voice"] is None
    assert ps.load_persona(figure_id)["stand_in_voice"] in tts.STAND_IN_VOICES


@pytest.mark.parametrize("figure_id", FIGURES)
def test_suggested_questions_are_answered_from_their_own_books(client, figures, figure_id):
    p = figures[figure_id]
    titles = {s["title"] for s in p["sources"]}
    for question in p["suggested_questions"]:
        d = client.post("/chat", json={"query": question, "persona": figure_id, "mode": "mix_method"}).json()
        assert d["mode"] == "mix_method", f"{figure_id}: {question!r} fell back"
        assert d["answer"].startswith("As I wrote in ") and any(t in d["answer"].split('"')[0] for t in titles)
        assert all(s["voice"] == "first_person" and s["source_type"] == "writing" for s in d["sources"])


@pytest.mark.parametrize("figure_id", [f for f in FIGURES if f != "mahatma_gandhi"])  # his Guide to Health covers water
def test_unanswerable_question_falls_back(client, figures, figure_id):
    d = client.post("/chat", json={"query": "How do I descale a kettle?", "persona": figure_id, "mode": "mix_method"}).json()
    assert d["fallback"] is True


def test_only_their_own_words_are_kept():
    meditations = (ps.ROOT / "figures" / "data" / "marcus_aurelius" / "clean" / "pg2680.md").read_text(encoding="utf-8")
    assert meditations.startswith("THE FIRST BOOK")  # translator's introduction dropped
    assert "Of my grandfather Verus I have learned" in meditations and "GLOSSARY" not in meditations
    tesla = (ps.ROOT / "figures" / "data" / "nikola_tesla" / "clean" / "pg13476.md").read_text(encoding="utf-8")
    assert tesla.startswith("I cannot find words") and "Biographical Sketch" not in tesla
    assert "Transcriber" not in tesla and "[Illustration" not in tesla
    lincoln = (ps.ROOT / "figures" / "data" / "abraham_lincoln" / "clean" / "pg14721.md").read_text(encoding="utf-8")
    assert "ANECDOTES" not in lincoln  # stories told about him, not by him
