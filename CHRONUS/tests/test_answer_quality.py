"""Answer quality: focused quotes, cleanup, honest framing, ranking (services/mix_method.py, api_server.retrieve)."""

import numpy as np
import pytest

from evaluation.verify_signatures import verify
from services import mix_method as mm


def _mem(text, source_type="interview", dist=0.3, **meta):
    return (0.0, text, {"source_type": source_type, "source_file": "x", **meta}, dist)


@pytest.mark.parametrize("raw,clean", [
    ("I I think um the the rocket, uh, works", "I think the rocket works"),
    ("Yes, that's that's it.", "Yes, that's it."),
    ("very very good", "very very good"),  # emphasis is kept
    ("See [00:12:34] it at 12:30 okay", "See it at 12:30 okay"),  # real times stay, timestamps go
    ("@elonmusk @nasa Great work! https://t.co/abc", "Great work!"),
    ("at the pointat which it is availableto anyone", "at the point at which it is available to anyone"),
    ("a dierent and condent team with $100,000and more", "a different and confident team with $100,000 and more"),
    ("Uh-huh, right.", "Uh-huh, right."),
])
def test_clean_for_display(raw, clean):
    assert mm.clean_for_display(raw) == clean


def test_focused_excerpt_quotes_the_relevant_sentences():
    text = ("of the market in general, however, and this matters a lot. We had a lot of problems with the factory. "
            "Mars matters because life needs a backup plan beyond Earth. The weather was nice that day in Texas.")
    out = mm.focused_excerpt(text, "Why does Mars matter?", 120)
    assert "Mars matters because life needs a backup" in out and out.startswith("…")
    assert mm.focused_excerpt("Short and whole.", "anything", 120) == "Short and whole."


def test_theme_framing_only_when_the_question_names_a_theme():
    from services.theme_classifier import classify_theme
    assert not mm.theme_is_clear(classify_theme("What was your favourite birthday?"))
    assert not mm.theme_is_clear(classify_theme("Why Mars?"))  # only "why" matched
    assert mm.theme_is_clear(classify_theme("How do you handle failure?"))


def test_no_invented_closing_lines():
    card = {"signature_phrases": ["First principles, basically."], "top_beliefs": []}
    mems = [_mem("Rockets should be reusable like airplanes, otherwise space travel stays absurdly expensive."),
            _mem("Making rockets reusable is the key breakthrough for getting to Mars.", dist=0.35)]
    out = mm.generate_mix_method_response("Why reusable rockets?", mems, card, "Elon Musk")
    assert "First principles, basically" not in out["response"] and out["parts"]["part3_closing_signature"] == ""


def test_verified_closing_line_only_when_related():
    card = {"signature_phrases_verified": [{"phrase": "Physics is the law, everything else is a recommendation.",
                                            "source_file": "Lex Fridman Podcast clean.md"}]}
    mems = [_mem("Engineering starts from physics, then you work up from there to what is possible.")]
    related = mm.generate_mix_method_response("What does physics mean to you?", mems, card, "Elon Musk")
    assert related["parts"]["part3_closing_signature"].endswith('"Physics is the law, everything else is a recommendation."')
    assert any(s["source"] == "Lex Fridman Podcast clean.md" for s in related["sources"])
    unrelated = mm.generate_mix_method_response("Tell me about your childhood", mems, card, "Elon Musk")
    assert unrelated["parts"]["part3_closing_signature"] == ""


def test_supporting_quotes_skip_near_duplicates_and_vary_attribution():
    fam = {"origin": "family"}
    mems = [_mem("I love the garden and the tulsi plants in the morning sun.", "personal_writing"),
            _mem("I love the garden and the tulsi plants in the morning sun!", "interview_protocol", **fam),
            _mem("[Interview Response] Q: x A: She hummed old film songs while cooking dal.", "interview_protocol", **fam),
            _mem("[Interview Response] Q: y A: She walked to the temple every evening at six.", "interview_protocol", **fam)]
    out = mm.generate_mix_method_response("Tell me about her days", mems, {}, "Amma")["response"]
    assert out.count("tulsi") == 1
    assert out.count("An interview with their family adds:") <= 1 and "And from the same source:" in out


def test_length_short_is_one_quote():
    mems = [_mem("First memory about rockets and engines."), _mem("Second memory about rockets.", dist=0.33)]
    out = mm.generate_mix_method_response("rockets?", mems, {"signature_phrases_verified": []}, "Elon Musk", length="short")
    assert out["parts"]["part2_theme_explanation"] == "" and out["response"].count('"') == 2


def test_weak_matches_are_not_introduced_as_certain():
    # "I've been pretty clear about this:" before a 45% match about dinner, asked about lasagne
    dinner = "Dinner in an old Belgian ironmongery, and the best menu art I have ever seen anywhere."
    weak = mm.generate_mix_method_response("What is your favourite lasagne recipe?", [_mem(dinner, dist=0.55)], {},
                                           "Elon Musk", threshold=0.56)
    assert weak["confidence"] == "low"
    assert any(weak["response"].startswith(f) for f in mm._INTRO_FRAMES_LOW)
    sure = mm.generate_mix_method_response("What is your favourite dinner?", [_mem(dinner, dist=0.3)], {}, "Elon Musk")
    assert any(sure["response"].startswith(f) for f in mm._INTRO_FRAMES)
    letter = mm.generate_mix_method_response("Lasagne?", [_mem(dinner, "personal_writing", dist=0.57)], {}, "Amma")
    assert letter["response"].startswith(mm._INTRO_WRITTEN_LOW)
    # A model whose own threshold is higher (old writing matches loosely) isn't hedged as early
    sonnet = mm.generate_mix_method_response("What is love?", [_mem(dinner, "writing", dist=0.567, source_name="Sonnets")],
                                             {}, "William Shakespeare", threshold=0.62)
    assert sonnet["response"].startswith("As I wrote in Sonnets:")


def test_confidence_bands_follow_the_models_threshold():
    assert mm.calculate_confidence(0.47) == "medium" and mm.calculate_confidence(0.47, 0.62) == "high"
    assert mm.calculate_confidence(0.55, 0.56) == "low" and mm.calculate_confidence(0.55, 0.65) == "medium"


def test_verify_signatures():
    memories = [{"text": "Well, physics is the law, everything else is a recommendation.", "source_type": "interview",
                 "source_file": "lex.md", "memory_id": "m1"},
                {"text": "First principles, basically.", "source_type": "pdf", "source_file": "bio.pdf"}]  # a biographer, not him
    ok, rejected = verify(["Physics is the law, everything else is a recommendation.", "First principles, basically."], memories)
    assert [v["memory_id"] for v in ok] == ["m1"] and rejected == ["First principles, basically."]


def _vec_at(q, distance, seed):
    rng = np.random.default_rng(seed)
    o = rng.normal(size=q.shape)
    o -= (o @ q) * q
    o /= np.linalg.norm(o)
    sim = 1 - distance
    return (sim * q + np.sqrt(1 - sim ** 2) * o).tolist()


@pytest.fixture
def memory(srv):
    col = srv.client.get_or_create_collection("pytest_quality", metadata={"hnsw:space": "cosine"})
    yield col
    srv.client.delete_collection("pytest_quality")


def test_importance_only_breaks_near_ties(srv, memory):
    q = "what did you love about teaching mathematics"
    qv = np.asarray(srv.embedder.encode([q], normalize_embeddings=True)[0])
    memory.add(ids=["letter", "interview"],
               documents=["A letter about loving mathematics teaching and fractions with mangoes every day.",
                          "An interview answer about life in general and many other things entirely."],
               embeddings=[_vec_at(qv, 0.30, 1), _vec_at(qv, 0.42, 2)],
               metadatas=[{"source_type": "personal_writing", "importance_score": 1},
                          {"source_type": "interview_protocol", "importance_score": 5}])
    top = srv.retrieve(q, memory=memory, threshold=1.0, mode="dense")
    assert top[0][2]["source_type"] == "personal_writing"  # 0.12 closer beats max importance (bonus <= 0.08)


def test_retrieval_skips_near_duplicates(srv, memory):
    q = "tell me about the rocket landing"
    qv = np.asarray(srv.embedder.encode([q], normalize_embeddings=True)[0])
    docs = ["The rocket landing on the drone ship was the best moment of the whole year for the team.",
            "The rocket landing on the drone ship was the best moment of the whole year for our team!",
            "Engine testing in Texas takes months of careful work before any rocket flies at all."]
    memory.add(ids=["a", "b", "c"], documents=docs, embeddings=[_vec_at(qv, 0.30, 3), _vec_at(qv, 0.31, 4), _vec_at(qv, 0.40, 5)],
               metadatas=[{"source_type": "tweet"}] * 3)
    ids = [m[1] for m in srv.retrieve(q, n=3, memory=memory, threshold=1.0, mode="dense")]
    assert ids == [docs[0], docs[2]]


def test_raw_captions_only_when_nothing_cleaner_passed(srv, memory):
    # Auto-captions with no named speakers ran the host's words into Elon's answer
    q = "why did you start the rocket company"
    qv = np.asarray(srv.embedder.encode([q], normalize_embeddings=True)[0])
    docs = ["you know it was a little more than fifty thousand but lets ask about the rocket company okay well",
            "I started the rocket company because life needs to become multiplanetary to last in the long run."]
    memory.add(ids=["caption", "clean"], documents=docs, embeddings=[_vec_at(qv, 0.30, 6), _vec_at(qv, 0.40, 7)],
               metadatas=[{"source_type": "interview", "speaker_verified": False, "punctuated": False},
                          {"source_type": "interview", "speaker_verified": False, "punctuated": True}])
    assert [m[1] for m in srv.retrieve(q, n=3, memory=memory, threshold=1.0, mode="dense")] == [docs[1]]
    memory.delete(ids=["clean"])  # with nothing else to go on, the caption still answers
    assert [m[1] for m in srv.retrieve(q, n=3, memory=memory, threshold=1.0, mode="dense")] == [docs[0]]


def test_custom_models_get_their_own_threshold(client):
    import base64
    pid = client.post("/personas", json={"name": "pytest Calibrated", "relationship": "self", "consent": True}).json()["id"]
    try:
        text = "\n\n".join(f"Memory number {i}: I walked to the river and watched the boats go by until sunset." for i in range(12))
        client.post(f"/personas/{pid}/documents", json={"filename": "walks.txt", "content_base64": base64.b64encode(text.encode()).decode()})
        client.post(f"/personas/{pid}/build")
        from services import personas as ps
        assert 0.58 <= ps.load_persona(pid)["distance_threshold"] <= 0.68
    finally:
        client.delete(f"/personas/{pid}")


def test_length_is_validated(client):
    assert client.post("/chat", json={"query": "hey", "length": "epic"}).status_code == 422
    assert client.post("/chat", json={"query": "hey", "length": "short"}).status_code == 200
