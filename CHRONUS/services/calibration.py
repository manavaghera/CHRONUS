"""
Per-model "I don't know" threshold.

The global DISTANCE_THRESHOLD was tuned on Elon's speech. Old or translated
English (Marcus Aurelius), or a small family archive, sits at different
distances from modern questions, so each model gets its own value: just
below where questions its archive can't answer start matching
(evaluation/questions.py OUT_OF_DOMAIN), never below the global value and
never above THRESHOLD_MAX. Used by figures/build_figures.py, when a custom
model is built, and by `python -m evaluation.calibrate`.
"""

from __future__ import annotations

from config import config
from evaluation.questions import OUT_OF_DOMAIN

THRESHOLD_MARGIN = 0.03
THRESHOLD_MAX = 0.68


def calibrate_threshold(collection, embedder, floor: float | None = None, cap: float = THRESHOLD_MAX) -> float:
    """Distance just below the 10th percentile of best matches for questions
    this archive can't answer, within [floor (global threshold), cap]."""
    floor = config.DISTANCE_THRESHOLD if floor is None else floor
    if collection.count() == 0:
        return floor
    vectors = embedder.encode(OUT_OF_DOMAIN, normalize_embeddings=True, show_progress_bar=False).tolist()
    found = collection.query(query_embeddings=vectors, n_results=min(12, collection.count()),
                             include=["documents", "distances"])
    best = []
    for docs, dists in zip(found["documents"], found["distances"]):
        substantive = [d for doc, d in zip(docs, dists) if len(doc.split()) >= config.MIN_EVIDENCE_WORDS]
        best.append(min(substantive or dists))  # same short-memory filter as retrieval
    p10 = sorted(best)[len(best) // 10]
    return round(min(cap, max(floor, p10 - THRESHOLD_MARGIN)), 2)

