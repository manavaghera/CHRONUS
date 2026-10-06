"""
Compare embedding models for retrieval on the evaluation set without
touching the live memory store: each candidate embeds the corpus in memory.

Every model is judged against the same relevance labels as run_eval.py:
* answer-equivalent: all-MiniLM cosine(memory, real answer) >= 0.6. The
  labeller is the current model, which slightly favours it.
* exact passage: lexical, model-independent.

    python -m evaluation.compare_embedders [model name ...]
"""

from __future__ import annotations

import sys
import time

# First: run_eval imports api_server, which loads pyarrow before torch. The
# other order crashes the process silently on Windows (see api_server.py).
from evaluation.run_eval import ANSWER_EQUIVALENT, _mean, _ranking_metrics, srv
from evaluation.ted_qa import SOURCE_IN_MEMORY, load_pairs, question_only
from services.provenance import content_words

import numpy as np  # noqa: E402
import torch  # noqa: E402
from sentence_transformers import SentenceTransformer  # noqa: E402

CANDIDATES = ["sentence-transformers/multi-qa-MiniLM-L6-cos-v1"]


def _labels(pairs, corpus):
    ids, docs, metas = corpus["ids"], corpus["documents"], corpus["metadatas"]
    stored = np.asarray(corpus["embeddings"])  # current model's vectors
    gold = srv.embedder.encode([p["answer"] for p in pairs], normalize_embeddings=True)
    interview = [(i, content_words(d)) for i, (d, m) in enumerate(zip(docs, metas)) if m.get("source_file") == SOURCE_IN_MEMORY]
    labels = []
    for pair, g in zip(pairs, gold):
        sim = stored @ g
        answer_words = content_words(pair["answer"])
        labels.append({
            "similarity": sim,
            "answer_equivalent": {ids[i] for i in np.flatnonzero(sim >= ANSWER_EQUIVALENT)},
            "exact_passage": {ids[i] for i, w in interview if w and len(w & answer_words) / len(w) >= 0.5},
        })
    return labels


def _score(query_vecs, corpus_vecs, ids, labels) -> dict:
    out = {}
    for definition in ("answer_equivalent", "exact_passage"):
        rows = []
        for q, lab in zip(query_vecs, labels):
            if not lab[definition]:
                continue
            top = np.argsort(-(corpus_vecs @ q))[:10]
            rows.append(_ranking_metrics([ids[i] for i in top], lab[definition], float(lab["similarity"][top[0]])))
        out[definition] = {k: _mean(rows, k) for k in ("p1", "hit3", "rr", "recall10")}
    return out


def main(models: list[str]) -> None:
    pairs = load_pairs()
    corpus = srv.collection.get(include=["documents", "metadatas", "embeddings"])
    ids = corpus["ids"]
    labels = _labels(pairs, corpus)
    queries = {"full turn": [p["question"] for p in pairs], "question only": [question_only(p["question"]) for p in pairs]}
    device = "cuda" if torch.cuda.is_available() else "cpu"

    results = {}
    current = np.asarray(corpus["embeddings"])
    for variant, qs in queries.items():
        results[("all-MiniLM-L6-v2 (current)", variant)] = _score(srv.embedder.encode(qs, normalize_embeddings=True), current, ids, labels)
    for name in models:
        model = SentenceTransformer(name, device=device)
        start = time.time()
        vecs = model.encode(corpus["documents"], batch_size=256, normalize_embeddings=True, show_progress_bar=False)
        print(f"embedded {len(vecs):,} memories with {name} on {device} in {time.time() - start:.0f}s")
        for variant, qs in queries.items():
            results[(name.split("/")[-1], variant)] = _score(model.encode(qs, normalize_embeddings=True), vecs, ids, labels)

    print("\n| Model | Questions | P@1 (answer-equiv.) | MRR@10 | Recall@10 | P@1 (exact) | MRR@10 (exact) |")
    print("|---|---|---|---|---|---|---|")
    for (model, variant), r in results.items():
        a, e = r["answer_equivalent"], r["exact_passage"]
        print(f"| {model} | {variant} | {a['p1']} | {a['rr']} | {a['recall10']} | {e['p1']} | {e['rr']} |")


if __name__ == "__main__":
    main(sys.argv[1:] or CANDIDATES)
