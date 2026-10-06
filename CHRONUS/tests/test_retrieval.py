"""Retrieval on the real Elon corpus: filters, follow-ups, threshold."""

import pytest


def test_short_tweets_skipped_when_better_evidence_exists(srv):
    # "Why Mars?" used to return "Mars is The New World" (5 words)
    memories = srv.retrieve("Why Mars?")
    assert all(len(doc.split()) >= srv.config.MIN_EVIDENCE_WORDS for _, doc, _, _ in memories)


@pytest.mark.parametrize("question", ["What is the goal of SpaceX?", "Why did you buy Twitter?", "Tell me about your childhood"])
def test_supporting_memories_are_close_to_the_best(srv, question):
    dists = [m[3] for m in srv.retrieve(question)]
    assert max(dists) - min(dists) <= srv.config.SUPPORT_MARGIN


def test_no_duplicate_texts(srv):
    docs = [" ".join(doc.lower().split()) for _, doc, _, _ in srv.retrieve("What is the goal of SpaceX?")]
    assert len(docs) == len(set(docs))


def test_clearly_unanswerable_question_returns_none(srv):
    assert srv.retrieve("How do I descale a kettle?") is None


def test_where_filter_holds_a_source_out(srv):
    held_out = srv.retrieve("What is the goal of SpaceX?", where={"source_file": {"$ne": "Joe Rogan podcast clean.md"}})
    assert all(m[2]["source_file"] != "Joe Rogan podcast clean.md" for m in held_out)


@pytest.mark.parametrize("question,follow_up", [
    ("why was it hard?", True), ("Why?", True), ("which state?", True), ("Is that true?", True),
    ("Was it worth it?", True), ("What do you think about that?", True),
    ("Why Mars?", False), ("How do you handle failure?", False), ("Tell me about your childhood", False),
    ("Is AI dangerous?", False), ("Is it hard to run Tesla?", False),
])
def test_follow_up_detection(srv, question, follow_up):
    assert srv.is_follow_up(question) is follow_up


def test_follow_up_search_uses_previous_exchange(srv):
    history = [srv.ChatTurn(role="user", content="Tell me about your childhood"),
               srv.ChatTurn(role="assistant", content="I got bullied a lot.")]
    assert srv.retrieval_query("why was it hard?", history) == "Tell me about your childhood I got bullied a lot. why was it hard?"
    mars = [srv.ChatTurn(role="user", content="Why Mars?"), srv.ChatTurn(role="assistant", content="A city on Mars.")]
    assert srv.retrieval_query("How do you handle failure?", mars) == "How do you handle failure?"
