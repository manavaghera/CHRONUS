"""Hybrid retrieval (services/hybrid.py) and the sentence-level grounding check."""

import pytest

from services import hybrid
from services.embedder import HashEmbedder
from services.provenance import semantic_support

DOCS = [
    "My father bought me a blue Hero bicycle for my eighteenth birthday and I rode it every morning.",
    "Teaching fractions with mangoes always worked better than any textbook in my classroom.",
    "When I retired I started a small garden with tomatoes, chillies and tulsi on the terrace.",
    "The monsoon of 1987 flooded the whole village and we carried the goats up to the temple steps.",
]


@pytest.fixture
def memory(srv):
    col = srv.client.get_or_create_collection("pytest_hybrid", metadata={"hnsw:space": "cosine"})
    col.add(ids=[f"m{i}" for i in range(len(DOCS))], documents=DOCS,
            embeddings=srv.embedder.encode(DOCS, normalize_embeddings=True).tolist(),
            metadatas=[{"source_type": "personal_writing", "importance_score": 1} for _ in DOCS])
    yield col
    srv.client.delete_collection("pytest_hybrid")


def test_rrf_rewards_agreement():
    scores = hybrid.rrf(["a", "b", "c"], ["c", "a"])
    assert max(scores, key=scores.get) == "a" and scores["c"] > scores["b"]


def test_bm25_index_is_rebuilt_when_memories_change(memory):
    index, ids = hybrid.bm25_index(memory)
    assert hybrid.bm25_index(memory)[0] is index  # cached
    memory.add(ids=["extra"], documents=["Gardening taught me patience."], embeddings=[[0.1] * 384])
    assert hybrid.bm25_index(memory)[0] is not index and "extra" in hybrid.bm25_index(memory)[1]


def test_keyword_candidates_respect_where(memory):
    assert hybrid.keyword_candidates(memory, "monsoon 1987 village", 2)[0] == "m3"
    assert hybrid.keyword_candidates(memory, "monsoon 1987", 2, where={"source_type": "news"}) == []


@pytest.mark.parametrize("mode", ["dense", "hybrid"])
def test_both_modes_keep_the_refusal_threshold(srv, memory, mode):
    q = "Tell me about the monsoon flood of 1987 in your village"
    found = srv.retrieve(q, memory=memory, threshold=1.5, mode=mode)
    assert found and "monsoon" in found[0][1]
    # BM25 matches "1987" strongly, but can never rescue a memory past the threshold
    assert srv.retrieve(q, memory=memory, threshold=0.0, mode=mode) is None


def test_semantic_support_counts_backed_sentences():
    emb = HashEmbedder()
    evidence = [DOCS[0]]
    faithful = "My father bought me a blue Hero bicycle for my eighteenth birthday."
    half_invented = faithful + " Then we flew to Paris and opened a bakery near the river."
    assert semantic_support(faithful, evidence, emb, 0.5) == 1.0
    assert semantic_support(half_invented, evidence, emb, 0.5) == 0.5
    assert semantic_support("Hi.", evidence, emb, 0.5) == 1.0  # nothing claim-like to check
