"""
Answer-quality evaluation: does what CHRONUS says hold up?

run_eval.py scores retrieval only, so problems in the answers themselves
(invented first-person lines, the interviewer quoted as Elon, damaged text)
never showed up in any number. This puts ~145 labelled questions to the
models (Quotes only, no AI cost) and checks every answer:

  refusal   answers what the archive covers; says "I don't know" otherwise
  verbatim  every quoted span appears word for word in a memory it cites
  speaker   no quote contains an interviewer's question (transcripts)
  framing   no scripted theme lines; "I've said"-style lead-ins only before
            the persona's own words
  garbled   no damaged text: lost fi/fl letters ("rst", "nancial"), a
            deleted "like" ("I'd to just"), caption noise ("[ __ ]")
  whole     quotes end at a sentence end, or are marked "…"

    python -m evaluation.answer_quality              # real models and data
    python -m evaluation.answer_quality --sample     # CI: public-domain figures, no downloads

Results: evaluation/results/answer_quality.{json,md}. The checks
themselves are tested in tests/test_answer_quality_eval.py.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "evaluation" / "results"
CHECKS = ("refusal", "verbatim", "speaker", "framing", "garbled", "whole")

# Figures' questions the archive can't answer (it should say so)
FIGURE_UNANSWERABLE = ["How do I descale a kettle?", "What is your favourite smartphone app?"]

# Lead-ins that claim the persona said what follows
_FIRST_PERSON_LEAD = re.compile(
    r"I've been pretty clear|As I've said|I've talked about|Here's what I've actually said|I've addressed|"
    r"I also mentioned|I've said|I also said|I've also pointed out|As I wrote in|In my own words", re.IGNORECASE)
_QUOTE = re.compile(r"\"([^\"]{8,})\"")
# Words left when PDF extraction dropped a fi/fl/ff ligature ("first" -> "rst")
_LIGATURE_LOSS = re.compile(
    r"(?<!['’])\b(?:rst|nancial|nancially|nally|gure|gured|gures|eld|elds|xed|nish|nished|rms|ght|ghts|ghting|"
    r"uence|uenced|exible|ights|ying|nancing|cient|ciency|delity|xing)\b", re.IGNORECASE)
_DELETED_LIKE = re.compile(r"\b(?:I'd|you'd|we'd|they'd|he'd|she'd|would) to (?:just |really )?\w+", re.IGNORECASE)
_CAPTION_NOISE = re.compile(r"\[\s*_+\s*\]|,\s*,|\.\s*,(?!\d)|�")
_SENTENCE_END = re.compile(r"[.!?][\"'”’)]*$")


def _norm(text: str) -> str:
    text = text.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")
    return re.sub(r"\s+", " ", text).strip()


def quotes_in(answer: str) -> list[tuple[str, str]]:
    """(lead-in, quote) pairs: each quoted span and the text just before it."""
    pairs, last = [], 0
    for m in _QUOTE.finditer(answer):
        pairs.append((answer[last:m.start()], m.group(1)))
        last = m.end()
    return pairs


def fragments(quote: str) -> list[str]:
    """A quote split at its "…" gaps into the pieces that must be verbatim."""
    return [f.strip(" .,") for f in quote.split("…") if len(f.strip(" .,")) >= 12]


def check_answer(answer: str, memories: list[tuple[str, dict]], answerable: bool, fallback: bool,
                 theme_lines: list[str], verified_phrases: frozenset[str] = frozenset()) -> dict:
    """{check: True/False/None (not applicable)} for one answer.

    *memories*: (text, metadata) of each memory the answer cites.
    *verified_phrases*: closing lines checked to occur in the persona's own
    words (identity card "signature_phrases_verified"), quoted without a citation.
    """
    from services.mix_method import is_host_question, quote_text
    from services.provenance import FIRST_PERSON, voice_of

    result = {c: None for c in CHECKS}
    result["refusal"] = (not fallback) if answerable else fallback
    pairs = quotes_in(answer)
    if fallback or not pairs:
        return result
    sources = [(_norm(quote_text(text, meta)), _norm(text), meta) for text, meta in memories]
    verbatim = speaker = framing = whole = True
    for lead, quote in pairs:
        if _norm(quote) in verified_phrases or "profile summarises" in lead:
            continue  # a verified closing line, or a belief labelled as the profile's summary
        frags = fragments(_norm(quote))
        owner = None
        if "�" in quote:
            verbatim = False  # a character lost in conversion, not the person's words
        for frag in frags:
            hit = next((s for s in sources if frag in s[0] or frag in s[1]), None)
            if hit is None:
                verbatim = False
                continue
            owner = owner or hit
            if hit[2].get("source_type") in ("interview", "video"):
                if any(is_host_question(s) for s in re.split(r"(?<=[.!?])\s+", frag)):
                    speaker = False
        if _FIRST_PERSON_LEAD.search(lead) and owner is not None and voice_of(owner[2]) != FIRST_PERSON:
            framing = False
        # A whole tweet may end without a full stop; a cut passage must say so with "…"
        complete_unit = owner is not None and owner[2].get("source_type") in ("tweet", "interview_protocol")
        if not (_SENTENCE_END.search(quote.strip()) or quote.strip().endswith("…") or complete_unit):
            whole = False
    if any(line and line in answer for line in theme_lines):
        framing = False
    result.update(verbatim=verbatim, speaker=speaker, framing=framing, whole=whole,
                  garbled=not (_LIGATURE_LOSS.search(answer) or _DELETED_LIKE.search(answer)
                               or _CAPTION_NOISE.search(answer)))
    return result


def question_set(personas: list[str]) -> list[dict]:
    """[{persona, question, answerable}] for the models available."""
    from evaluation.questions import IN_DOMAIN_SHORT, OUT_OF_DOMAIN
    from evaluation.ted_qa import load_pairs, question_only
    from services import personas as ps

    items = []
    if "elon_musk" in personas:
        ted = [question_only(p["question"]) for p in load_pairs()]
        items += [{"persona": "elon_musk", "question": q, "answerable": True} for q in IN_DOMAIN_SHORT + ted if q]
        items += [{"persona": "elon_musk", "question": q, "answerable": False} for q in OUT_OF_DOMAIN]
    for pid in personas:
        persona = ps.load_persona(pid)
        if pid == "elon_musk" or not persona:
            continue
        items += [{"persona": pid, "question": q, "answerable": True} for q in persona.get("suggested_questions", [])]
        items += [{"persona": pid, "question": q, "answerable": False} for q in FIGURE_UNANSWERABLE]
    return items


def evaluate(srv, items: list[dict], collections: dict | None = None) -> dict:
    """Answer each item with api_server.answer_from_memory (Quotes only) and check it."""
    from services import personas as ps
    from services.theme_classifier import _THEME_PROMPTS

    theme_lines = [p.split(",")[0] for p in _THEME_PROMPTS.values()]
    rows = []
    for item in items:
        persona = ps.load_persona(item["persona"])
        memory = (collections or {}).get(item["persona"]) or ps.get_collection(srv.client, persona)
        out = srv.answer_from_memory(item["question"], persona, memory, "mix_method", [])
        ids = [s.get("memory_id") for s in out["sources"] if s.get("memory_id")]
        got = memory.get(where={"memory_id": {"$in": ids}}, include=["documents", "metadatas"]) if ids else None
        cited = list(zip(got["documents"], got["metadatas"])) if got else []
        card = srv.load_mix_method_identity_card(persona["id"])
        verified = frozenset(_norm(p["phrase"]) for p in card.get("signature_phrases_verified", []))
        checks = check_answer(out["response"], cited, item["answerable"], out["fallback"], theme_lines, verified)
        rows.append({**item, "answer": out["response"], "mode": out["mode"], "checks": checks})
    summary = {}
    for check in CHECKS:
        applicable = [r["checks"][check] for r in rows if r["checks"][check] is not None]
        summary[check] = {"pass_rate": round(sum(applicable) / len(applicable), 3) if applicable else None,
                          "applicable": len(applicable)}
    answerable = [r for r in rows if r["answerable"]]
    unanswerable = [r for r in rows if not r["answerable"]]
    summary["answered_when_answerable"] = round(sum(r["checks"]["refusal"] for r in answerable) / len(answerable), 3) \
        if answerable else None
    summary["refused_when_unanswerable"] = round(sum(r["checks"]["refusal"] for r in unanswerable) / len(unanswerable), 3) \
        if unanswerable else None
    return {"date": date.today().isoformat(), "questions": len(rows), "summary": summary, "rows": rows}


def sample_collections(srv, only: list[str] | None = None) -> dict:
    """CI: the public-domain figures from their checked-in texts, embedded with
    whatever embedder the server has (the tests' HashEmbedder: no download).
    *only*: these figure ids."""
    import hashlib

    import merge_sources
    from services import chroma_index
    from services import personas as ps

    collections = {}
    for folder in sorted((ROOT / "figures" / "data").glob("*/clean")):
        figure_id = folder.parent.name
        persona = ps.load_persona(figure_id)
        if persona is None or (only and figure_id not in only):
            continue
        name = f"pytest_quality_{figure_id}"
        try:
            srv.client.delete_collection(name)
        except Exception:
            pass
        memory = srv.client.create_collection(name, metadata=chroma_index.COLLECTION_METADATA)
        docs, metas = [], []
        for path in sorted(folder.glob("*.md")):
            for record in merge_sources.parse_markdown(path):
                record.update(source_type="writing", source_file=path.name, source_name=persona["name"], date="")
                for unit in merge_sources.chunk_record(record):
                    mid = "q_" + hashlib.md5(f"{figure_id}|{len(docs)}|{unit['text']}".encode()).hexdigest()[:16]
                    docs.append(unit["text"])
                    metas.append({"source_type": "writing", "source_file": path.name, "source_name": record["source_name"],
                                  "memory_id": mid})
        for start in range(0, len(docs), 256):
            batch = slice(start, start + 256)
            memory.add(ids=[m["memory_id"] for m in metas[batch]], documents=docs[batch], metadatas=metas[batch],
                       embeddings=srv.embedder.encode(docs[batch], normalize_embeddings=True).tolist())
        collections[figure_id] = memory
    return collections


def write_report(result: dict) -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "answer_quality.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    s = result["summary"]
    lines = [f"# Answer quality ({result['date']}, {result['questions']} questions, Quotes only)", "",
             "| Check | Pass rate | Answers checked |", "|---|---|---|"]
    lines += [f"| {c} | {s[c]['pass_rate']} | {s[c]['applicable']} |" for c in CHECKS]
    lines += ["", f"Answered when answerable: {s['answered_when_answerable']}; "
              f"refused when unanswerable: {s['refused_when_unanswerable']}", "", "## Failures (up to 5 per check)", ""]
    for check in CHECKS:
        failed = [r for r in result["rows"] if r["checks"][check] is False][:5]
        for r in failed:
            lines.append(f"- **{check}** · {r['persona']} · {r['question'][:80]!r}: {r['answer'][:220]!r}")
    (RESULTS / "answer_quality.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--sample", action="store_true", help="public-domain figures only, from checked-in texts")
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT))
    import pyarrow.dataset  # noqa: F401  (Windows: before torch)

    import api_server as srv
    from services import personas as ps

    collections = sample_collections(srv) if args.sample else None
    personas = list(collections) if collections else [p["id"] for p in ps.list_personas() if p["kind"] == "pretrained"]
    result = evaluate(srv, question_set(personas), collections)
    write_report(result)
    print(json.dumps(result["summary"], indent=2))


if __name__ == "__main__":
    main()
