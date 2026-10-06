"""Natural mode (LLM mocked): failure fallbacks, grounding guard, voice clean-up, prompt rules."""

import pytest

import services.natural_mode as nm
from post_process import scrub


@pytest.fixture(scope="module")
def spacex(srv):
    return srv.retrieve("What is the goal of SpaceX?"), srv.load_mix_method_identity_card()


@pytest.mark.parametrize("label,kwargs", [
    ("null content (old crash)", {"content": None}),
    ("empty content", {"content": ""}),
    ("cut off mid-sentence", {"content": "I mean, the exact", "finish": "length"}),
    ("no credits (402)", {"status": 402}),
    ("invented answer (grounding guard)", {"content": "Honestly I love pizza and basketball on weekends with friends."}),
])
def test_bad_llm_replies_fall_back_to_quotes(fake_llm, spacex, label, kwargs):
    memories, card = spacex
    with fake_llm(**kwargs):
        out = nm.generate_natural_response("Why Mars?", memories, card)
    assert out["mode"] == "mix_method_fallback", label
    assert all({"citation", "voice", "memory_id", "distance"} <= s.keys() for s in out["sources"])


def test_good_reply_is_used_and_cleaned(fake_llm, spacex):
    memories, card = spacex
    with fake_llm(content="Mars is the goal—a backup for life."):
        out = nm.generate_natural_response("Why Mars?", memories, card)
    assert out["mode"] == "natural" and out["response"] == "Mars is the goal, a backup for life."


def test_cut_off_reply_keeps_complete_sentences(fake_llm, spacex):
    memories, card = spacex
    with fake_llm(content="The goal of SpaceX is life on Mars. And then we", finish="length"):
        out = nm.generate_natural_response("What is the goal of SpaceX?", memories, card)
    assert out["response"] == "The goal of SpaceX is life on Mars."


def test_answers_capped_at_four_sentences(fake_llm, spacex):
    memories, card = spacex
    reply = "The goal of SpaceX is life on Mars. Rockets must be reusable. Earth needs a backup. Mars is the goal. Five. Six."
    with fake_llm(content=reply):
        out = nm.generate_natural_response("What is the goal of SpaceX?", memories, card)
    assert out["response"].endswith("Mars is the goal.")


def test_history_and_settings_reach_the_llm(fake_llm, spacex):
    memories, card = spacex
    with fake_llm(content="Making life multiplanetary.") as post:
        nm.generate_natural_response("Why?", memories, card, history=[{"role": "user", "content": "Why Mars?"}])
    sent = post.call_args.kwargs["json"]
    assert sent["messages"][1] == {"role": "user", "content": "Why Mars?"}
    assert sent["reasoning"] == {"enabled": False} and sent["max_tokens"] == nm.NATURAL_MAX_TOKENS


def test_local_provider_runs_on_device_with_adapter(spacex, monkeypatch):
    from unittest import mock
    memories, card = spacex
    monkeypatch.setattr(nm.config, "LLM_PROVIDER", "local")
    with mock.patch("services.local_llm.generate", return_value=("The goal of SpaceX is life on Mars.", False)) as gen, \
         mock.patch.object(nm.requests, "post") as cloud:
        out = nm.generate_natural_response("What is the goal of SpaceX?", memories, card, use_adapter=True)
    assert out["mode"] == "natural" and not cloud.called  # nothing sent to a cloud service
    assert gen.call_args.kwargs["use_adapter"] is True and gen.call_args.args[1] == nm.LOCAL_MAX_TOKENS


def test_prompt_rules():
    prompt = nm.build_system_prompt("Elon Musk", "[1] YOUR OWN WORDS (Interview): test", "", style_notes="Dry and direct.")
    assert "—" not in prompt and "–" not in prompt  # models copy dashes
    assert "building the answer from YOUR OWN WORDS" in prompt and "Answer the actual question" in prompt
    assert "Dry and direct." in prompt and "Nietzsche" not in prompt  # no pasted style quotes


@pytest.mark.parametrize("raw,clean", [
    ("Mars is the New World—we need a backup.", "Mars is the New World, we need a backup."),
    ("Rockets must be reusable. Overall, that's the key.", "Rockets must be reusable."),
    ("Plus, it's fun.", "And it's fun."),
    ("Sure, the factory is the product.", "The factory is the product."),
    ("Basically, it has to be reusable.", "Basically, it has to be reusable."),  # his real habit
    (None, ""),
])
def test_scrub(raw, clean):
    assert scrub(raw) == clean
