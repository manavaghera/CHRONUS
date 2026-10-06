"""
CHRONUS evaluation: reproducible numbers on the real Elon Musk corpus.

    python -m evaluation.run_eval               # no LLM calls
    python -m evaluation.run_eval --natural 10  # also score natural mode (uses LLM quota)

1. Retrieval (paper RQ1 / Table IV). For each real TED interview question,
   is a memory saying what Elon actually answered ranked first? Compared:
   raw semantic search (MiniLM), the full CHRONUS pipeline, the pipeline
   without its importance bias, hybrid semantic + BM25 retrieval
   (services/hybrid.py), and BM25 alone.
   Two relevance definitions:
   * answer-equivalent: cosine(memory, his real answer) >= 0.6, any source.
     Measured: memories carrying his answer score 0.65-0.95 (same
     interview) / 0.49-0.78 (other interviews); unrelated ones ~0.07.
   * exact passage: from that interview, >= half its content words in his
     answer (strict; the cleaned copy is a different transcription).
2. Match test. The TED interview is held out of memory; the clone answers
   each question from everything else, and its answer is compared with what
   Elon actually said (embedding cosine + content-word F1), against a
   random-memory baseline.
3. "I don't know" calibration. Best-match distance for questions he has
   answered vs questions his archive can't answer, swept over thresholds.

Writes evaluation/results/latest.json and latest.md.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import statistics
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

import api_server as srv  # noqa: E402  (loads ChromaDB + embedding model)
from evaluation.bm25 import BM25  # noqa: E402
from evaluation.ted_qa import SOURCE_IN_MEMORY, load_pairs, question_only  # noqa: E402
from services.provenance import anchor_first, content_words  # noqa: E402

RESULTS = ROOT / "evaluation" / "results"
PAPER = {"semantic_p1": 0.82, "bm25_p1": 0.41, "semantic_mrr": 0.87, "bm25_mrr": 0.49}
ANSWER_EQUIVALENT = 0.6  # cosine(memory, real answer) counted as "says what he said"
OFF_TOPIC = 0.3          # top result below this similarity to his answer = drift

from evaluation.questions import IN_DOMAIN_SHORT, OUT_OF_DOMAIN  # noqa: E402


def _ranking_metrics(ranked: list[str], relevant: set[str], top_similarity: float) -> dict:
    first = next((i for i, mid in enumerate(ranked[:10]) if mid in relevant), None)
    return {
        "p1": float(bool(ranked) and ranked[0] in relevant),
        "hit3": float(any(mid in relevant for mid in ranked[:3])),
        "p3": sum(mid in relevant for mid in ranked[:3]) / 3,
        "rr": 0.0 if first is None else 1 / (first + 1),
        "recall10": float(first is not None),
        # top result has little to do with what he actually said
        "drift": float(top_similarity < OFF_TOPIC),
    }


def _mean(rows: list[dict], key: str) -> float:
    return round(statistics.mean(r[key] for r in rows), 3) if rows else 0.0


def _f1(a: str, b: str) -> float:
    wa, wb = content_words(a), content_words(b)
    if not wa or not wb:
        return 0.0
    overlap = len(wa & wb)
    return 0.0 if not overlap else 2 * overlap / (len(wa) + len(wb))


def _cosine(a: str, b: str) -> float:
    va, vb = srv.embedder.encode([a, b], normalize_embeddings=True)
    return float((va * vb).sum())


def _without_importance(q: str) -> list[str]:
    """The dense pipeline with IMPORTANCE_WEIGHT = 0 (is the importance bias helping?)."""
    saved, srv.IMPORTANCE_WEIGHT = srv.IMPORTANCE_WEIGHT, 0.0
    try:
        return [m[2].get("memory_id", "") for m in anchor_first(srv.retrieve(q, mode="dense") or [])]
    finally:
        srv.IMPORTANCE_WEIGHT = saved


def evaluate_retrieval(pairs: list[dict], corpus: dict) -> dict:
    ids, docs, metas = corpus["ids"], corpus["documents"], corpus["metadatas"]
    embeddings = np.asarray(corpus["embeddings"])
    position = {mid: i for i, mid in enumerate(ids)}
    gold = srv.embedder.encode([p["answer"] for p in pairs], normalize_embeddings=True)
    bm25 = BM25(docs)
    interview = [(mid, content_words(doc)) for mid, doc, meta in zip(ids, docs, metas)
                 if meta.get("source_file") == SOURCE_IN_MEMORY]
    systems = ("semantic", "chronus_pipeline", "pipeline_no_importance", "hybrid", "bm25")
    rows = {"answer_equivalent": {s: [] for s in systems}, "exact_passage": {s: [] for s in systems}}
    for pair, answer_vec in zip(pairs, gold):
        similarity = embeddings @ answer_vec  # every memory vs his real answer
        answer_words = content_words(pair["answer"])
        relevance = {
            "answer_equivalent": {ids[i] for i in np.flatnonzero(similarity >= ANSWER_EQUIVALENT)},
            "exact_passage": {mid for mid, words in interview
                              if words and len(words & answer_words) / len(words) >= 0.5},
        }
        q = pair["question"]
        emb = srv.embedder.encode([q], normalize_embeddings=True).tolist()
        ranked = {
            "semantic": srv.collection.query(query_embeddings=emb, n_results=10, include=[])["ids"][0],
            "chronus_pipeline": [m[2].get("memory_id", "") for m in anchor_first(srv.retrieve(q, mode="dense") or [])],
            "pipeline_no_importance": _without_importance(q),
            "hybrid": [m[2].get("memory_id", "") for m in anchor_first(srv.retrieve(q, mode="hybrid") or [])],
            "bm25": [ids[i] for i, _ in bm25.top(q, 10)],
        }
        for definition, relevant in relevance.items():
            if not relevant:
                continue  # nothing in memory counts as his answer under this definition
            for name, order in ranked.items():
                top_sim = float(similarity[position[order[0]]]) if order and order[0] in position else 0.0
                rows[definition][name].append(_ranking_metrics(order, relevant, top_sim))
    metrics = ("p1", "hit3", "p3", "rr", "recall10", "drift")
    return {definition: {"queries": len(r["semantic"]),
                         "systems": {name: {k: _mean(v, k) for k in metrics} for name, v in r.items()}}
            for definition, r in rows.items()}


def evaluate_match(pairs: list[dict], corpus_docs: list[str], corpus_metas: list[dict], natural_n: int) -> dict:
    held_out = {"source_file": {"$ne": SOURCE_IN_MEMORY}}
    card = srv.load_mix_method_identity_card("elon_musk")
    pool = [d for d, m in zip(corpus_docs, corpus_metas) if m.get("source_file") != SOURCE_IN_MEMORY]
    rng = random.Random(42)
    rows = []
    for i, pair in enumerate(pairs):
        mems = srv.retrieve(pair["question"], where=held_out)
        if mems is None:
            mix = "I don't have any documented information about that in my available records."
        else:
            mix = srv.generate_mix_method_response(pair["question"], anchor_first(mems), card, "Elon Musk")["response"]
        random_memory = rng.choice(pool)
        row = {"id": pair["id"],
               "mix_cos": _cosine(mix, pair["answer"]), "mix_f1": _f1(mix, pair["answer"]),
               "random_cos": _cosine(random_memory, pair["answer"]), "random_f1": _f1(random_memory, pair["answer"])}
        if i < natural_n and mems is not None:
            out = srv.generate_natural_response(pair["question"], anchor_first(mems), card,
                                                profile_block=srv.profile_context_block("elon_musk"),
                                                style_notes=srv.ps.load_persona("elon_musk").get("style_notes"))
            row.update(natural_mode=out["mode"], natural_cos=_cosine(out["response"], pair["answer"]),
                       natural_f1=_f1(out["response"], pair["answer"]))
        rows.append(row)
    summary = {k: _mean(rows, k) for k in ("mix_cos", "mix_f1", "random_cos", "random_f1")}
    natural = [r for r in rows if "natural_cos" in r]
    if natural:
        summary.update(natural_n=len(natural), natural_llm_answered=sum(r["natural_mode"] == "natural" for r in natural),
                       natural_cos=_mean(natural, "natural_cos"), natural_f1=_mean(natural, "natural_f1"))
    return {"questions": len(rows), "summary": summary, "rows": rows}


def calibrate(pairs: list[dict]) -> dict:
    saved = srv.DISTANCE_THRESHOLD
    srv.DISTANCE_THRESHOLD = 2.0  # see every candidate's distance
    try:
        best = lambda q: min(m[3] for m in srv.retrieve(q))  # noqa: E731
        in_domain = [best(p["question"]) for p in pairs] + [best(q) for q in IN_DOMAIN_SHORT]
        out_domain = [best(q) for q in OUT_OF_DOMAIN]
    finally:
        srv.DISTANCE_THRESHOLD = saved
    sweep = []
    for t in [round(0.30 + 0.01 * i, 2) for i in range(81)]:
        answered = sum(d <= t for d in in_domain) / len(in_domain)
        refused = sum(d > t for d in out_domain) / len(out_domain)
        sweep.append({"threshold": t, "in_domain_answered": round(answered, 3), "out_of_domain_refused": round(refused, 3),
                      "balanced_accuracy": round((answered + refused) / 2, 3)})
    # Held-out check: choose the threshold on one half, measure it on the other
    rng = random.Random(7)
    folds = []
    for _ in range(2):
        ins, outs = in_domain[:], out_domain[:]
        rng.shuffle(ins)
        rng.shuffle(outs)
        halves = [(ins[: len(ins) // 2], outs[: len(outs) // 2]), (ins[len(ins) // 2:], outs[len(outs) // 2:])]
        for (tr_in, tr_out), (te_in, te_out) in (halves, halves[::-1]):
            t = max((r["threshold"] for r in sweep), key=lambda t: (
                (sum(d <= t for d in tr_in) / len(tr_in) + sum(d > t for d in tr_out) / len(tr_out)) / 2,
                sum(d <= t for d in tr_in)))
            folds.append({"threshold": t, "answered": sum(d <= t for d in te_in) / len(te_in),
                          "refused": sum(d > t for d in te_out) / len(te_out)})
    held_out = {"answered": round(statistics.mean(f["answered"] for f in folds), 3),
                "refused": round(statistics.mean(f["refused"] for f in folds), 3),
                "thresholds": [f["threshold"] for f in folds]}
    stats = lambda xs: {"min": round(min(xs), 3), "median": round(statistics.median(xs), 3), "max": round(max(xs), 3)}  # noqa: E731
    return {"in_domain": stats(in_domain), "out_of_domain": stats(out_domain),
            "best_balanced": max(sweep, key=lambda r: (r["balanced_accuracy"], r["in_domain_answered"])),
            "current": next(r for r in sweep if r["threshold"] == round(min(saved, 1.1), 2)),
            "held_out": held_out, "sweep": sweep, "raw": {"in_domain": in_domain, "out_of_domain": out_domain}}


def to_markdown(res: dict) -> str:
    r, m, c = res["retrieval"], res["match"]["summary"], res["calibration"]
    ae, ex = r["answer_equivalent"], r["exact_passage"]
    lines = [f"# CHRONUS evaluation ({res['date']})", "",
             f"Corpus: Elon Musk, {res['corpus_size']:,} memories. Test set: {res['pairs']} real question/answer pairs "
             "from the TED Gigafactory interview.", ""]
    for title, block in ((f"## Retrieval: answer-equivalent memories ({ae['queries']} questions)", ae),
                         (f"## Retrieval: exact passage only, strict ({ex['queries']} questions)", ex)):
        lines += [title, "", "| System | P@1 | Hit@3 | P@3 | MRR@10 | Recall@10 | Drift@1 |", "|---|---|---|---|---|---|---|"]
        for name, s in block["systems"].items():
            lines.append(f"| {name} | {s['p1']} | {s['hit3']} | {s['p3']} | {s['rr']} | {s['recall10']} | {s['drift']} |")
        lines.append("")
    qo = res["retrieval_question_only"]["answer_equivalent"]
    lines += [f"## Retrieval: answer-equivalent, question sentence only ({qo['queries']} questions)", "",
              "The interviewer's turn without its preamble, closer to what a user types.", "",
              "| System | P@1 | Hit@3 | P@3 | MRR@10 | Recall@10 | Drift@1 |", "|---|---|---|---|---|---|---|"]
    for name, s in qo["systems"].items():
        lines.append(f"| {name} | {s['p1']} | {s['hit3']} | {s['p3']} | {s['rr']} | {s['recall10']} | {s['drift']} |")
    lines.append("")
    lines += [f"Paper (Table IV, different corpus): semantic P@1 {PAPER['semantic_p1']}, BM25 P@1 {PAPER['bm25_p1']}.",
              "", "## Match test (TED interview held out)", "", "| Answer | Cosine to real answer | Content-word F1 |", "|---|---|---|",
              f"| Mix Method (clone) | {m['mix_cos']} | {m['mix_f1']} |", f"| Random memory (baseline) | {m['random_cos']} | {m['random_f1']} |"]
    if "natural_cos" in m:
        lines.append(f"| Natural mode, {m['natural_n']} questions ({m['natural_llm_answered']} answered by the LLM) | {m['natural_cos']} | {m['natural_f1']} |")
    b, cur = c["best_balanced"], c["current"]
    lines += ["", "## \"I don't know\" calibration", "",
              f"Best-match distance, answered questions: {c['in_domain']}; unanswerable questions: {c['out_of_domain']}.", "",
              f"- Current threshold {cur['threshold']}: answers {cur['in_domain_answered']:.0%} of answerable, refuses {cur['out_of_domain_refused']:.0%} of unanswerable.",
              f"- Best balanced threshold {b['threshold']}: answers {b['in_domain_answered']:.0%}, refuses {b['out_of_domain_refused']:.0%} (chosen and measured on the same questions).",
              f"- Held out (chosen on half, measured on the other half, 4 splits; thresholds {c['held_out']['thresholds']}): "
              f"answers {c['held_out']['answered']:.0%}, refuses {c['held_out']['refused']:.0%}."]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--natural", type=int, default=0, help="score natural mode on the first N questions (uses LLM quota)")
    args = parser.parse_args()

    pairs = load_pairs()
    corpus = srv.collection.get(include=["documents", "metadatas", "embeddings"])
    res = {"date": datetime.now().isoformat(timespec="seconds"), "corpus_size": len(corpus["ids"]), "pairs": len(pairs),
           "retrieval": evaluate_retrieval(pairs, corpus),
           # Same pairs, asked the way a user would: just the question sentence
           "retrieval_question_only": evaluate_retrieval(
               [{**p, "question": question_only(p["question"])} for p in pairs], corpus),
           "match": evaluate_match(pairs, corpus["documents"], corpus["metadatas"], args.natural),
           "calibration": calibrate(pairs)}
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "latest.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    (RESULTS / "latest.md").write_text(to_markdown(res), encoding="utf-8")
    print(to_markdown(res))


if __name__ == "__main__":
    main()
