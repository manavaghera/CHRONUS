"""Retrieval on the real Elon corpus: filters, follow-ups, threshold."""

import pytest


@pytest.mark.corpus
def test_short_tweets_skipped_when_better_evidence_exists(srv):
    # "Why Mars?" used to return "Mars is The New World" (5 words)
    memories = srv.retrieve("Why Mars?")
    assert all(len(doc.split()) >= srv.config.MIN_EVIDENCE_WORDS for _, doc, _, _ in memories)


@pytest.mark.corpus
@pytest.mark.parametrize("question", ["What is the goal of SpaceX?", "Why did you buy Twitter?", "Tell me about your childhood"])
def test_supporting_memories_are_close_to_the_best(srv, question):
    dists = [m[3] for m in srv.retrieve(question)]
    assert max(dists) - min(dists) <= srv.config.SUPPORT_MARGIN


@pytest.mark.corpus
def test_no_duplicate_texts(srv):
    docs = [" ".join(doc.lower().split()) for _, doc, _, _ in srv.retrieve("What is the goal of SpaceX?")]
    assert len(docs) == len(set(docs))


@pytest.mark.corpus
def test_clearly_unanswerable_question_returns_none(srv):
    assert srv.retrieve("How do I descale a kettle?") is None


@pytest.mark.corpus
def test_where_filter_holds_a_source_out(srv):
    held_out = srv.retrieve("What is the goal of SpaceX?", where={"source_file": {"$ne": "Joe Rogan podcast.txt"}})
    assert all(m[2]["source_file"] != "Joe Rogan podcast.txt" for m in held_out)


@pytest.mark.parametrize("question,follow_up", [
    ("why was it hard?", True), ("Why?", True), ("which state?", True), ("Is that true?", True),
    ("Was it worth it?", True), ("What do you think about that?", True),
    ("Why Mars?", False), ("How do you handle failure?", False), ("Tell me about your childhood", False),
    ("Is AI dangerous?", False), ("Is it hard to run Tesla?", False),
])
def test_follow_up_detection(srv, question, follow_up):
    assert srv.is_follow_up(question) is follow_up


@pytest.mark.parametrize("question,follow_up", [
    ("Tell me more", True), ("tell me more about that", True), ("What else?", True), ("Go on", True),
    ("Anything else?", True), ("Can you elaborate?", True), ("Tell me more about Mars", False),
])
def test_continuations_are_follow_ups(srv, question, follow_up):
    # "Tell me more" wasn't recognised: "tell" and "more" counted as its topic
    assert srv.is_follow_up(question) is follow_up


class _Memory:
    def __init__(self, docs):
        self.docs = docs

    def get(self, ids, include):
        return {"documents": [self.docs[i] for i in ids if i in self.docs]}


def test_follow_up_searches_from_the_cited_memories_not_the_template(srv):
    template = 'Look, I\'ve talked about this: "Mars is the next step." I\'ve also talked about this a few times.'
    cited = srv.ChatTurn(role="assistant", content=template, memory_ids=["m7"])
    history = [srv.ChatTurn(role="user", content="Why Mars?"), cited]
    memory = _Memory({"m7": "A self-sustaining city on Mars makes life multiplanetary."})
    text = srv.retrieval_query("tell me more", history, memory)
    assert "self-sustaining city" in text and "talked about this" not in text
    # older clients send no ids: only the quoted words are used, never the framing
    plain = [history[0], srv.ChatTurn(role="assistant", content=template)]
    text = srv.retrieval_query("tell me more", plain)
    assert "Mars is the next step." in text and "talked about this" not in text


def test_follow_ups_skip_quotes_already_used(srv):
    memory = srv.client.get_or_create_collection("pytest_followup", metadata={"hnsw:space": "cosine"})
    try:
        texts = ["Mars is the next logical step for humanity and a backup for civilization on Earth.",
                 "A city on Mars would make humanity a multiplanetary species for the very long term.",
                 "Going to Mars is about making life multiplanetary so that consciousness survives.",
                 "Why Mars? Because a self-sustaining city on Mars protects humanity from a single point of failure.",
                 "Starship is the rocket that will carry people to Mars and build the first city there.",
                 "Mars has the resources to make fuel, so ships can return from Mars to Earth."]
        ids = [f"m{i}" for i in range(1, len(texts) + 1)]
        memory.add(ids=ids, documents=texts, embeddings=srv.embedder.encode(texts, normalize_embeddings=True).tolist(),
                   metadatas=[{"source_type": "tweet", "memory_id": i} for i in ids])
        persona = {"id": "pytest_followup", "name": "Test", "distance_threshold": 2.0}
        first = srv.answer_from_memory("Why Mars?", persona, memory, "mix_method", [])
        shown = [s["memory_id"] for s in first["sources"]]
        history = [srv.ChatTurn(role="user", content="Why Mars?"),
                   srv.ChatTurn(role="assistant", content=first["response"][:2000], memory_ids=shown)]
        more = srv.answer_from_memory("Tell me more", persona, memory, "mix_method", history)
        assert more["sources"] and not set(shown) & {s["memory_id"] for s in more["sources"]}
        history.append(srv.ChatTurn(role="user", content="Tell me more"))
        history.append(srv.ChatTurn(role="assistant", content="...", memory_ids=ids))
        last = srv.answer_from_memory("What else?", persona, memory, "mix_method", history)
        assert last["response"] == "That's everything my records have on this." and last["sources"] == []
    finally:
        srv.client.delete_collection("pytest_followup")


def test_memory_ids_in_history_are_validated(client):
    turn = {"role": "assistant", "content": "x", "memory_ids": ["../../etc/passwd"]}
    assert client.post("/chat", json={"query": "tell me more", "history": [turn]}).status_code == 422


def test_follow_up_search_uses_previous_exchange(srv):
    history = [srv.ChatTurn(role="user", content="Tell me about your childhood"),
               srv.ChatTurn(role="assistant", content="I got bullied a lot.")]
    assert srv.retrieval_query("why was it hard?", history) == "Tell me about your childhood I got bullied a lot. why was it hard?"
    mars = [srv.ChatTurn(role="user", content="Why Mars?"), srv.ChatTurn(role="assistant", content="A city on Mars.")]
    assert srv.retrieval_query("How do you handle failure?", mars) == "How do you handle failure?"
