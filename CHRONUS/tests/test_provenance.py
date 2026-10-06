"""Who said it: voices, attribution, anchor ordering, citations, grounding score."""

import pytest

from services import provenance as pv


@pytest.mark.parametrize("source_type", ["tweet", "interview", "book", "speech", "personal_writing"])
def test_own_words(source_type):
    assert pv.voice_of({"source_type": source_type}) == pv.FIRST_PERSON


@pytest.mark.parametrize("source_type", ["pdf", "news", "document", "video", "written_about", "unknown_type"])
def test_written_by_others(source_type):
    assert pv.voice_of({"source_type": source_type}) == pv.THIRD_PARTY


@pytest.mark.parametrize("origin,voice", [
    ("synthesized", pv.SYNTHESIZED), ("self", pv.FIRST_PERSON), ("", pv.FIRST_PERSON), ("family", pv.THIRD_PARTY),
])
def test_interview_answer_voice_depends_on_who_answered(origin, voice):
    assert pv.voice_of({"source_type": "interview_protocol", "origin": origin}) == voice


def test_attribution_names_the_biographer():
    assert pv.attribution({"source_type": "pdf", "source_file": "Elon Musk (Walter Isaacson).pdf"}) == "Walter Isaacson's biography"
    assert pv.attribution({"source_type": "written_about", "source_name": "obituary"}) == 'the document "obituary"'


def _mem(source_type, dist, text="x"):
    return (0.0, text, {"source_type": source_type}, dist)


def test_close_own_words_are_quoted_first():
    ordered = pv.anchor_first([_mem("pdf", 0.30), _mem("interview", 0.40)])
    assert ordered[0][2]["source_type"] == "interview"


def test_much_better_match_keeps_its_place():
    # "describe your personality": synthesized 0.389 vs an off-topic quote at 0.548
    ordered = pv.anchor_first([_mem("interview_protocol", 0.389), _mem("interview", 0.548)])
    assert ordered[0][2]["source_type"] == "interview_protocol"


def test_citation_fields():
    c = pv.format_source_citation({"source_type": "pdf", "source_file": "Elon Musk (Walter Isaacson).pdf",
                                   "memory_id": "abc", "page": 681}, "text", 0.4567)
    assert c["voice"] == pv.THIRD_PARTY and c["memory_id"] == "abc" and c["distance"] == 0.457
    assert "Walter Isaacson's biography, not a quote" in c["citation"]


def test_grounding_score_ignores_common_words():
    evidence = ["The goal of SpaceX is to make life multiplanetary and build a city on Mars."]
    assert pv.grounding_score("Honestly I love pizza and basketball on weekends with friends.", evidence) < 0.25
    assert pv.grounding_score("SpaceX wants a city on Mars, making life multiplanetary.", evidence) > 0.6
