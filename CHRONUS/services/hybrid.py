"""
Hybrid retrieval helpers: keyword (BM25) candidates fused with semantic ones,
and an optional cross-encoder reranker.

Why: evaluation/results/latest.md shows semantic search alone finds the
memory with Elon's real answer first only 16% of the time, and names,
numbers and rare words ("Roadster", "1987") are exactly what MiniLM blurs.
BM25 catches those. Reciprocal rank fusion (RRF) merges the two rankings
without having to make their scores comparable.

The "I don't know" calibration is untouched: every candidate, wherever it
came from, still needs a raw cosine distance under the threshold, so BM25
can add evidence but never make the model answer something it would have
refused. Switch it on with RETRIEVAL_MODE = "hybrid" (config.py) after
checking `python -m evaluation.run_eval` on your corpus.
"""

from __future__ import annotations

import threading

import numpy as np

from services.bm25 import BM25

RRF_K = 60  # standard RRF constant: dampens the weight of top ranks

_lock = threading.Lock()
_indexes: dict[str, tuple[int, BM25, list[str]]] = {}


def bm25_index(collection) -> tuple[BM25, list[str]]:
    """(BM25 over the collection's documents, their ids), cached per
    collection and rebuilt when its size changes (uploads, deletions)."""
    count = collection.count()
    cached = _indexes.get(collection.name)
    if cached and cached[0] == count:
        return cached[1], cached[2]
    with _lock:
        cached = _indexes.get(collection.name)
        if cached and cached[0] == count:
            return cached[1], cached[2]
        data = collection.get(include=["documents"])
        index = BM25(data["documents"])
        _indexes[collection.name] = (count, index, data["ids"])
        return index, data["ids"]


def keyword_candidates(collection, query: str, k: int, where: dict | None = None) -> list[str]:
    """Ids of the k best BM25 matches (filtered by *where* afterwards)."""
    index, ids = bm25_index(collection)
    ranked = [ids[i] for i, _ in index.top(query, k * 3 if where else k)]
    if where and ranked:
        allowed = set(collection.get(ids=ranked, where=where, include=[])["ids"])
        ranked = [i for i in ranked if i in allowed]
    return ranked[:k]


def fetch_with_distance(collection, ids: list[str], query_vec: list[float]) -> list[tuple[str, str, dict, float]]:
    """(id, document, metadata, cosine distance) for memories BM25 found but
    semantic search didn't return, so they can face the same threshold."""
    if not ids:
        return []
    data = collection.get(ids=ids, include=["documents", "metadatas", "embeddings"])
    q = np.asarray(query_vec, dtype=np.float32)
    out = []
    for mid, doc, meta, emb in zip(data["ids"], data["documents"], data["metadatas"], data["embeddings"]):
        v = np.asarray(emb, dtype=np.float32)
        norm = float(np.linalg.norm(v) * np.linalg.norm(q)) or 1.0
        out.append((mid, doc, meta or {}, 1.0 - float(v @ q) / norm))
    return out


def rrf(*rankings: list[str]) -> dict[str, float]:
    """Reciprocal rank fusion: id -> sum of 1 / (RRF_K + rank) over rankings."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, mid in enumerate(ranking, start=1):
            scores[mid] = scores.get(mid, 0.0) + 1.0 / (RRF_K + rank)
    return scores


class Reranker:
    """Optional cross-encoder (config.RERANKER_MODEL), loaded on first use."""

    def __init__(self, model_name: str):
        self.model_name = model_name
        self._model = None
        self._lock = threading.Lock()

    def scores(self, query: str, docs: list[str]) -> list[float]:
        if self._model is None:
            with self._lock:
                if self._model is None:
                    from sentence_transformers import CrossEncoder
                    self._model = CrossEncoder(self.model_name, device="cpu")
        return [float(s) for s in self._model.predict([(query, d) for d in docs])]
