"""The answer-quality evaluation (evaluation/answer_quality.py): each check
catches what it should, and real answers on the public-domain sample pass
(this runs in CI, on the checked-in Gutenberg texts)."""

import pytest

from evaluation import answer_quality as aq
from services.theme_classifier import _THEME_PROMPTS

THEMES = [p.split(",")[0] for p in _THEME_PROMPTS.values()]
TWEET = ("Mars is the next logical step for humanity.", {"source_type": "tweet"})
BIO = ("He walked the factory floor at two in the morning, checking every weld.",
       {"source_type": "pdf", "source_file": "Elon Musk (Walter Isaacson).pdf"})
TALK = ("What do you think about AI? I think it is the biggest risk we face.", {"source_type": "interview"})


def check(answer, memories, answerable=True, fallback=False):
    return aq.check_answer(answer, memories, answerable, fallback, THEMES)


def test_a_clean_answer_passes():
    out = check('As I\'ve said before: "Mars is the next logical step for humanity." Walter Isaacson\'s biography adds: '
                '"He walked the factory floor at two in the morning, checking every weld."', [TWEET, BIO])
    assert all(out[c] for c in aq.CHECKS), out


@pytest.mark.parametrize("answer,memories,failed", [
    ('As I\'ve said before: "Mars is the first step for all of humanity."', [TWEET], "verbatim"),
    ('As I\'ve said before: "What do you think about AI? I think it is the biggest risk we face."', [TALK], "speaker"),
    ('I\'ve talked about this: "He walked the factory floor at two in the morning, checking every weld."', [BIO], "framing"),
    (f'{THEMES[6]}, I also mentioned: "Mars is the next logical step for humanity."', [TWEET], "framing"),
    ('As I\'ve said before: "Mars is the rst logical step for humanity."', [("Mars is the rst logical step for humanity.",
                                                                            {"source_type": "tweet"})], "garbled"),
    ('As I\'ve said before: "I\'d to just give thanks to everyone here."', [("I'd to just give thanks to everyone here.",
                                                                              {"source_type": "interview"})], "garbled"),
    ('Walter Isaacson\'s biography adds: "He walked the factory floor at two in the morning, checking"',
     [("He walked the factory floor at two in the morning, checking", BIO[1])], "whole"),
])
def test_each_problem_is_caught(answer, memories, failed):
    assert check(answer, memories)[failed] is False


def test_refusals_are_scored_both_ways():
    assert check("I don't have any documented information about that.", [], answerable=False, fallback=True)["refusal"]
    assert not check("I don't have any documented information about that.", [], answerable=True, fallback=True)["refusal"]
    assert not check('As I\'ve said before: "Mars is the next logical step for humanity."', [TWEET], answerable=False)["refusal"]


def test_public_domain_sample_answers_hold_up(srv):
    collections = aq.sample_collections(srv, only=["marcus_aurelius"])
    try:
        result = aq.evaluate(srv, aq.question_set(list(collections)), collections)
    finally:
        for memory in collections.values():
            srv.client.delete_collection(memory.name)
    s = result["summary"]
    assert result["questions"] >= 6
    assert s["verbatim"]["pass_rate"] == 1.0 and s["framing"]["pass_rate"] == 1.0
    assert s["speaker"]["pass_rate"] == 1.0 and s["garbled"]["pass_rate"] == 1.0 and s["whole"]["pass_rate"] == 1.0
