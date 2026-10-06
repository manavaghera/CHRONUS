"""Mix Method: honest framing, verbatim quotes, confidence bands, custom-persona wording."""

from services.mix_method import _after_comma, calculate_confidence, generate_mix_method_response


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


def test_phrase_after_theme_prompt_is_lowercased():
    assert _after_comma("About my work,", "Along those lines:") == "About my work, along those lines:"
    assert _after_comma("About my work,", "I also mentioned:") == "About my work, I also mentioned:"
    assert _after_comma("", "Along those lines:") == "Along those lines:"


def test_confidence_bands_match_calibration():
    assert calculate_confidence(0.30) == "high"
    assert calculate_confidence(0.48) == "medium"
    assert calculate_confidence(0.55) == "low"
