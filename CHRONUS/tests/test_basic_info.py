"""Quick profile answers (BASIC_PROFILE): patterns must only match questions ABOUT the persona."""

import re
from datetime import date

import pytest


def _matched_key(srv, question):
    q = question.lower().replace("’", "'").strip()
    return next((key for pattern, key in srv.BASIC_INFO_PATTERNS.items() if re.search(pattern, q)), None)


@pytest.mark.parametrize("question", [
    # bare keywords used to hijack these ("son" in personality, "own" in town...)
    "How would you describe your personality?", "What's the reason you bought Twitter?",
    "What lessons did you learn from failure?", "Will Tesla shut down?", "Do you think the town square matters?",
    "What is your vision for the company culture?", "Is money the root of evil?", "Why do you own so many companies?",
    "Tell me about your kids", "What was your relationship with your father like?",
    "How old were you when you started SpaceX?", "Where will humans live in the future?",
    "What do you think about the school system?", "Where were your kids born?",
])
def test_rich_questions_go_to_retrieval(srv, question):
    assert _matched_key(srv, question) is None


@pytest.mark.parametrize("question,key", [
    ("When were you born?", "born"), ("hey which year are u born in ?", "born"), ("which year were u bron", "born"),
    ("When is your birthday?", "born"), ("Where were you born?", "birth_place"),
    ("where were u bron in which contry", "birth_place"), ("which contry u were born in ?", "birth_place"),
    ("Where are you from?", "birth_place"), ("How old are you?", "age"), ("What’s your name?", "full_name"),
    ("Who is your mother?", "mother"), ("Who's your dad?", "father"), ("Do you have any siblings?", "siblings"),
    ("How many kids do you have?", "children"), ("What companies do you run?", "companies"),
    ("What's your net worth?", "net_worth"), ("Where do you live?", "lives_in"),
    ("Where did you go to college?", "education"), ("What do you do for fun?", "hobbies"), ("hey", "greeting"),
])
def test_profile_questions_match(srv, question, key):
    assert _matched_key(srv, question) == key


@pytest.mark.parametrize("today,age", [(date(2026, 6, 27), "54"), (date(2026, 6, 28), "55"), (date(2026, 10, 5), "55")])
def test_age_is_computed(srv, today, age):
    assert srv.get_profile("elon_musk", today)["age"] == age


def test_profile_has_no_em_dashes(srv):
    assert not any("—" in str(v) for v in srv.get_profile("elon_musk").values())


def _ask(srv, question, persona="elon_musk"):
    answer = srv.check_basic_info(question, persona)
    return answer and answer["response"]


def test_public_personal_facts_are_answered_not_kept_private(srv):
    # A public figure's family and wealth are public record: answered with facts and dates
    kids = _ask(srv, "How many kids do you have?")
    assert re.match(r"I have \d+ children: ", kids) and "with Shivon Zilis" in kids
    assert "don't" not in kids.lower() and "private" not in kids.lower()
    assert re.search(r"net worth at about \$[\d,.]+ (billion|million) as of \d+ \w+ 20\d\d", _ask(srv, "What's your net worth?"))
    peak = _ask(srv, "What was your peak net worth?")
    assert peak.startswith("The highest estimate of my net worth") and "as of" not in peak  # not also the current one
    assert "married three times" in _ask(srv, "Were you ever married?")
    assert "Kimbal Musk" in _ask(srv, "Do you have any siblings?")
    assert _ask(srv, "Who are your grandchildren?", "mahatma_gandhi").startswith("I had 10 grandchildren")
    assert _ask(srv, "How did you die?", "mahatma_gandhi") == "I was shot and killed by Nathuram Godse on 30 January 1948."
    block = srv.profile_context_block("elon_musk")
    assert "never call them private" in block and re.search(r"- Children: \d+: ", block) and re.search(r"- Age: \d\d", block)
    assert "Net worth" in block and "Highest net worth on record" in block


@pytest.mark.parametrize("question,persona,start", [
    ("How many kids does Elon Musk have?", "elon_musk", "I have"),
    ("What's the peak net worth of Elon Musk?", "elon_musk", "The highest estimate"),
    ("What is Elon's net worth?", "elon_musk", "The latest public estimate"),
    ("Is Elon married?", "elon_musk", "I've been married"),
    ("What is Mr. Musk's net worth?", "elon_musk", "The latest public estimate"),
    ("How many kids did Gandhi have?", "mahatma_gandhi", "I had 4 sons"),
    ("When was Mahatma Gandhi born?", "mahatma_gandhi", "I was born on 2 October 1869"),
    ("How many relatives did Gandhiji have?", "mahatma_gandhi", "My family on public record"),
    ("Who are Bapu's grandchildren?", "mahatma_gandhi", "I had 10 grandchildren"),
    ("How tall was Lincoln?", "abraham_lincoln", "I was 6 feet 4 inches"),
])
def test_questions_that_name_the_person(srv, question, persona, start):
    assert _ask(srv, question, persona).startswith(start)


@pytest.mark.parametrize("question,persona", [
    ("When was Pierre Curie born?", "marie_curie"),  # her husband, not her
    ("How old is Kimbal Musk?", "elon_musk"),  # his brother
    ("How many kids does Kimbal have?", "elon_musk"),
    ("How many kids does Elon Musk have?", "mahatma_gandhi"),  # asked in someone else's chat
    ("Tell me about your wife", "elon_musk"),  # a story, not a fact: his own words answer it
])
def test_questions_about_someone_else_go_to_retrieval(srv, question, persona):
    assert srv.check_basic_info(question, persona) is None


def test_custom_personas_have_no_profile(srv):
    assert srv.check_basic_info("When were you born?", "someone_else") is None


@pytest.mark.parametrize("question,key", [
    ("When did you die?", "died"), ("Who was your wife?", "spouse"), ("Were you ever married?", "spouse"),
    ("Who were your children?", "children"), ("What was your profession?", "occupation"),
    ("What was your nationality?", "nationality"), ("Did you win the Nobel prize?", "awards"),
    ("What are you best known for?", "notable_works"), ("How old were you when you died?", "age"),
])
def test_historical_profile_questions_match(srv, question, key):
    assert _matched_key(srv, question) == key


def test_two_part_question_gets_both_answers(client):
    # The user's own example: both the year and the place, as one sentence
    for question in ("Which year were you born, and where were you born?", "Which year were you born, and where?"):
        d = client.post("/chat", json={"query": question, "persona": "mahatma_gandhi", "mode": "mix_method"}).json()
        assert d["mode"] == "basic_info" and d["answer"] == "I was born on 2 October 1869 in Porbandar, India."
    # ...labelled as public record, never as his own words
    [source] = d["sources"]
    assert source["voice"] == "third_party" and "Wikidata Q1001" in source["citation"]
    d = client.post("/chat", json={"query": "When were you born and when did you die?", "persona": "albert_einstein"}).json()
    assert d["answer"] == "I was born on 14 March 1879. I died on 18 April 1955 in Princeton, United States."


def test_figure_profiles_answer_and_feed_the_ai_voice(srv):
    assert srv.check_basic_info("Were you ever married?", "nikola_tesla")["response"] == "I never married."
    assert srv.check_basic_info("How old were you when you died?", "abraham_lincoln")["response"] == "I died in 1865, at the age of 56."
    assert srv.check_basic_info("hi", "marcus_aurelius") is None  # no "Yo." from an emperor
    block = srv.profile_context_block("marie_curie")
    assert "not your own words" in block and "Nobel Prize in Chemistry (1911)" in block


def test_every_figure_has_checked_basic_facts():
    import json

    from services import personas as ps
    figures = json.loads((ps.ROOT / "figures" / "sources.json").read_text(encoding="utf-8"))["figures"]
    for figure in figures:
        record = json.loads((ps.ROOT / "models" / figure["id"] / "profile.json").read_text(encoding="utf-8"))
        assert record["wikidata"] == figure["wikidata"] and record["license"].startswith("CC0")
        assert {"born", "birth_place", "died", "father", "mother"} <= set(record["answers"])
        assert not any("—" in v for v in record["answers"].values())  # no em dashes
