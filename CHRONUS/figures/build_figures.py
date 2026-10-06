"""
Build the pretrained famous-figure models from public-domain texts.

    python figures/build_figures.py --dry-run         # show what would be kept
    python figures/build_figures.py [figure_id ...]   # build (stop the API server first)

For each figure in figures/sources.json: download the Project Gutenberg
plain text (cached in figures/data/<id>/raw/), keep only the person's own
words (configured segments), clean and chunk them like the rest of CHRONUS,
embed them into a fresh ChromaDB collection "figure_<id>", and write
models/<id>/persona.json so the API lists the model as ready.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import chromadb  # noqa: E402
import pyarrow.dataset  # noqa: E402,F401  (before sentence_transformers: Windows DLL crash otherwise)
from sentence_transformers import SentenceTransformer  # noqa: E402

import merge_sources  # noqa: E402
from config import config  # noqa: E402
from evaluation.questions import OUT_OF_DOMAIN  # noqa: E402

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
USER_AGENT = {"User-Agent": "Mozilla/5.0 CHRONUS-research (public-domain texts)"}
EMBED_BATCH = 256
# Per-figure "I don't know" threshold: just below where unanswerable questions
# start for this corpus. Old or translated English sits further from modern
# questions (Marcus Aurelius' real topics scored up to 0.71), so the global
# value, tuned on Elon's speech, refused too much. Never below the global one.
THRESHOLD_MARGIN = 0.03
THRESHOLD_MAX = 0.68


def download(figure_id: str, gutenberg_id: int) -> str:
    path = DATA / figure_id / "raw" / f"pg{gutenberg_id}.txt"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        for url in (f"https://www.gutenberg.org/cache/epub/{gutenberg_id}/pg{gutenberg_id}.txt",
                    f"https://www.gutenberg.org/ebooks/{gutenberg_id}.txt.utf-8"):
            try:
                path.write_bytes(urllib.request.urlopen(urllib.request.Request(url, headers=USER_AGENT), timeout=60).read())
                break
            except Exception:
                continue
        else:
            raise RuntimeError(f"Gutenberg #{gutenberg_id} has no plain-text file")
        time.sleep(1)  # be polite to Gutenberg
    return path.read_text(encoding="utf-8-sig", errors="ignore")


def gutenberg_body(text: str) -> list[str]:
    """Lines between the *** START / *** END markers (drops the licence)."""
    body = re.split(r"\*\*\* ?START OF (?:THE|THIS) PROJECT GUTENBERG EBOOK[^\n]*\n", text)[-1]
    return re.split(r"\*\*\* ?END OF (?:THE|THIS) PROJECT GUTENBERG EBOOK", body)[0].splitlines()


def _find(lines: list[str], marker, start: int) -> int:
    pattern, nth = (marker, 1) if isinstance(marker, str) else marker
    hits = [i for i in range(start, len(lines)) if re.search(pattern, lines[i].strip())]
    if len(hits) < nth:
        raise ValueError(f"marker {marker!r} not found")
    return hits[nth - 1]


def extract(lines: list[str], segments: list) -> tuple[str, list[tuple[int, int]]]:
    parts, spans = [], []
    for start_marker, end_marker in segments:
        start = _find(lines, start_marker, 0)
        end = len(lines) if end_marker is None else _find(lines, end_marker, start + 1)
        parts.append("\n".join(lines[start:end]))
        spans.append((start, end))
    return "\n\n".join(parts), spans


def clean(text: str) -> str:
    """Rejoin hard-wrapped lines into paragraphs; drop captions, footnotes
    (often the translator's) and footnote marks."""
    paragraphs = []
    for block in re.split(r"\n\s*\n", text):
        para = " ".join(line.strip() for line in block.splitlines() if line.strip())
        if not para or re.match(r"\[+(Illustration|Footnote|Figure|Transcriber)", para):
            continue
        para = re.sub(r"\[(?:[A-Z]|\d{1,3})\]", "", para)  # footnote markers like [A] or [12]
        para = re.sub(r"^[IVXLC]+\.\s+(?=[A-Z])", "", para)  # section numbers ("XLII. It is but...")
        para = re.sub(r"_([^_]+)_", r"\1", para)          # _italics_
        paragraphs.append(re.sub(r"\s{2,}", " ", para).strip())
    return "\n\n".join(p for p in paragraphs if p)


def build_units(figure: dict) -> list[dict]:
    units = []
    for book in figure["books"]:
        lines = gutenberg_body(download(figure["id"], book["gutenberg"]))
        text, _ = extract(lines, book["segments"])
        clean_path = DATA / figure["id"] / "clean" / f"pg{book['gutenberg']}.md"
        clean_path.parent.mkdir(parents=True, exist_ok=True)
        clean_path.write_text(clean(text), encoding="utf-8")
        for record in merge_sources.parse_markdown(clean_path):
            # The person's own published words (provenance voice: first person)
            record.update(source_type="writing", source_file=clean_path.name, source_name=book["title"], date="")
            units.extend(merge_sources.chunk_record(record))
    return units


def calibrate_threshold(collection, embedder) -> float:
    """Distance just below the 10th percentile of best matches for questions
    this archive can't answer (evaluation/questions.py), within
    [config.DISTANCE_THRESHOLD, THRESHOLD_MAX]."""
    vectors = embedder.encode(OUT_OF_DOMAIN, normalize_embeddings=True, show_progress_bar=False).tolist()
    found = collection.query(query_embeddings=vectors, n_results=12, include=["documents", "distances"])
    best = []
    for docs, dists in zip(found["documents"], found["distances"]):
        substantive = [d for doc, d in zip(docs, dists) if len(doc.split()) >= config.MIN_EVIDENCE_WORDS]
        best.append(min(substantive or dists))  # same short-memory filter as retrieval
    p10 = sorted(best)[len(best) // 10]
    return round(min(THRESHOLD_MAX, max(config.DISTANCE_THRESHOLD, p10 - THRESHOLD_MARGIN)), 2)


def build(figure: dict, client, embedder) -> int:
    units = build_units(figure)
    collection_name = f"figure_{figure['id']}"
    try:
        client.delete_collection(collection_name)  # rebuild from scratch: sources may have changed
    except Exception:
        pass
    collection = client.create_collection(name=collection_name, metadata={"hnsw:space": "cosine"})
    ids, docs, metas = [], [], []
    for i, unit in enumerate(units):
        memory_id = "fig_" + hashlib.md5(f"{figure['id']}|{i}|{unit['text']}".encode("utf-8")).hexdigest()[:16]
        meta = {k: ("" if v is None else v) for k, v in unit.items() if k not in ("text", "char_count", "word_count")}
        meta.update(memory_id=memory_id, person=figure["id"], importance_score=merge_sources.estimate_importance(unit))
        ids.append(memory_id)
        docs.append(unit["text"])
        metas.append(meta)
    for start in range(0, len(docs), EMBED_BATCH):
        batch = slice(start, start + EMBED_BATCH)
        vectors = embedder.encode(docs[batch], normalize_embeddings=True, show_progress_bar=False).tolist()
        collection.upsert(ids=ids[batch], documents=docs[batch], metadatas=metas[batch], embeddings=vectors)

    persona = {
        "id": figure["id"], "name": figure["name"], "kind": "pretrained", "status": "ready",
        "description": figure["description"], "collection": collection_name, "allow_cloud_llm": True,
        "style_notes": figure["style_notes"], "suggested_questions": figure["suggested_questions"],
        "stand_in_voice": figure["stand_in_voice"],
        "sources": [{"title": b["title"], "gutenberg": b["gutenberg"],
                     "url": f"https://www.gutenberg.org/ebooks/{b['gutenberg']}"} for b in figure["books"]],
        "license": "Public domain (Project Gutenberg)",
        "distance_threshold": calibrate_threshold(collection, embedder),
    }
    folder = ROOT / "models" / figure["id"]
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "persona.json").write_text(json.dumps(persona, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return collection.count()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build famous-figure models from public-domain texts")
    parser.add_argument("ids", nargs="*", help="figure ids (default: all)")
    parser.add_argument("--dry-run", action="store_true", help="only show which part of each book is kept")
    args = parser.parse_args()
    figures = json.loads((HERE / "sources.json").read_text(encoding="utf-8"))["figures"]
    figures = [f for f in figures if not args.ids or f["id"] in args.ids]

    if args.dry_run:
        for figure in figures:
            for book in figure["books"]:
                lines = gutenberg_body(download(figure["id"], book["gutenberg"]))
                text, spans = extract(lines, book["segments"])
                for start, end in spans:
                    first = next(l.strip() for l in lines[start:] if l.strip())
                    last = next((l.strip() for l in reversed(lines[:end]) if l.strip()), "")
                    print(f"{figure['id']:20} {book['title'][:28]:28} lines {start:5}-{end:5} | starts {first[:45]!r} | ends {last[-45:]!r}")
                print(f"{'':20} {'':28} {len(clean(text).split()):,} words kept")
        return

    import torch
    embedder = SentenceTransformer(config.EMBEDDING_MODEL, device="cuda" if torch.cuda.is_available() else "cpu")
    client = chromadb.PersistentClient(path=config.CHROMA_PATH)
    for figure in figures:
        start = time.time()
        count = build(figure, client, embedder)
        threshold = json.loads((ROOT / "models" / figure["id"] / "persona.json").read_text(encoding="utf-8"))["distance_threshold"]
        print(f"{figure['name']:22} {count:6,} memories  threshold {threshold}  ({time.time() - start:.0f}s)")


if __name__ == "__main__":
    main()
