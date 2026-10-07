"""Mix Method: honest framing, verbatim quotes, confidence bands, custom-persona wording."""

from services.mix_method import calculate_confidence, generate_mix_method_response
from services.theme_classifier import _THEME_PROMPTS


def _mem(text, source_type="interview", dist=0.3, **meta):
    return (0.0, text, {"source_type": source_type, "source_file": "x", **meta}, dist)


def test_biography_is_never_framed_as_his_own_words():
    out = generate_mix_method_response(
        "Why Mars?", [_mem("Isaacson narration about the factory floor.", "pdf", source_file="Elon Musk (Walter Isaacson).pdf")],
        {}, "Elon Musk")
    assert out["parts"]["part1_intro_quote"].startswith("I haven't said this in so many words, but Walter Isaacson's biography")


def test_interview_answer_is_quoted_not_the_question():
    text = ("[Interview Response] Q: How would you describe your core personality in a few sentences? "
            "A: I'm an engineer at heart. I basically treat everything as an engineering problem.")
    part1 = generate_mix_method_response("personality?", [_mem(text)], {}, "Elon Musk")["parts"]["part1_intro_quote"]
    assert "Q:" not in part1 and "core personality" not in part1 and "engineer at heart" in part1


def test_single_memory_is_quoted_whole():
    text = "My favourite birthday was my eighteenth. My father bought me a blue Hero bicycle."
    out = generate_mix_method_response("birthday?", [_mem(text, "personal_writing")], {}, "Amma")
    assert out["response"] == f'In my own words: "{text}"'  # no filler part 2, no invented sign-off


def test_custom_personas_get_neutral_framing():
    mems = [_mem("I taught mathematics for thirty years in Vadodara."),
            _mem("Teaching fractions with mangoes always worked better than any textbook.", dist=0.35)]
    out = generate_mix_method_response("What did you love about your work?", mems, {}, "Amma")["response"]
    assert "the explosions" not in out and "relentless drive" not in out and "First principles" not in out


ELON_CARD = {"name": "Elon Musk", "top_beliefs": [{"belief": "Humanity must become multi-planetary"}]}


def test_no_scripted_theme_lines_in_quotes_only_answers():
    # 64% of answers once opened Part 2 with an invented line like
    # "Considering the trajectory of human civilization and what it will take to preserve it,"
    mems = [_mem("We need to become a multi-planet species to protect consciousness.", "tweet"),
            _mem("Mars is the next logical step for civilization.", "tweet", dist=0.32),
            _mem("Earth will eventually be engulfed by the sun.", "tweet", dist=0.34)]
    for question in ("Will humanity survive?", "What scares you the most?", "What was your biggest mistake?"):
        out = generate_mix_method_response(question, mems, ELON_CARD, "Elon Musk")["response"]
        assert not any(prompt.split(",")[0] in out for prompt in _THEME_PROMPTS.values()), out


def test_lead_in_matches_whose_words_follow():
    mems = [_mem("Mars is the next logical step.", "tweet"),
            _mem("He walked the factory floor at 2 a.m.", "pdf", dist=0.32, source_file="Elon Musk (Walter Isaacson).pdf"),
            _mem("Musk said the plan was risky.", "news", dist=0.34)]
    out = generate_mix_method_response("Why Mars?", mems, ELON_CARD, "Elon Musk")["response"]
    assert "talked about this" not in out and "addressed several angles" not in out
    assert "There's more context here." in out and "Walter Isaacson's biography" in out
    own = [_mem("Mars is the next logical step.", "tweet"), _mem("Becoming multiplanetary matters.", "tweet", dist=0.32),
           _mem("Life should not be confined to one planet.", "tweet", dist=0.34)]
    out = generate_mix_method_response("Why Mars?", own, ELON_CARD, "Elon Musk")["response"]
    assert "There's more context here." not in out  # all his own words: a first-person lead-in is true


def test_interviewers_questions_are_never_quoted_as_his_words():
    text = "What do you think about AI safety? I think it's the biggest risk we face. Are you worried about it?"
    out = generate_mix_method_response("AI risk?", [_mem(text, "interview")], {}, "Elon Musk")["response"]
    assert "What do you think" not in out and "Are you worried" not in out and "biggest risk" in out
    own = "So what do I think the future will be? I think it's probably Banksian."
    out = generate_mix_method_response("future?", [_mem(own, "interview")], {}, "Elon Musk")["response"]
    assert "what do I think the future will be?" in out  # his own rhetorical question stays
    # A passage that is only the host talking is skipped when there's anything else to quote
    mems = [_mem("What is your plan for Mars?", "interview", dist=0.2), _mem("Mars is the next logical step.", "tweet", dist=0.3)]
    out = generate_mix_method_response("Mars?", mems, {}, "Elon Musk")["response"]
    assert "plan for Mars" not in out and "next logical step" in out


def test_ai_voice_evidence_has_no_interviewer_questions(fake_llm):
    from services.natural_mode import generate_natural_response
    mems = [(0.0, "What do you think about AI safety? I think it's the biggest risk we face.",
             {"source_type": "interview", "source_file": "x"}, 0.3)]
    with fake_llm(content="I think it's the biggest risk we face.") as post:
        generate_natural_response("AI risk?", mems, {})
    prompt = post.call_args.kwargs["json"]["messages"][0]["content"]
    assert "biggest risk" in prompt and "What do you think about AI safety" not in prompt


def test_confidence_bands_match_calibration():
    assert calculate_confidence(0.30) == "high"
    assert calculate_confidence(0.48) == "medium"
    assert calculate_confidence(0.55) == "low"
