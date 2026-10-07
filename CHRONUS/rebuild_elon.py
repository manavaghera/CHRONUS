"""
Rebuild Elon's memories from the raw sources, without damaging them.

    python rebuild_elon.py                    # writes 04-Memory-Units/elon_musk_memory_units.jsonl
    python rebuild_elon.py --embed            # ...and replaces his pipeline memories in chroma_db
    python rebuild_elon.py --refresh-sources  # re-read titles and dates from YouTube

Stop the server first and make a backup (python backup.py create). His 25
interview-protocol answers and any reviewed answers in the collection are
kept; only memories made by this pipeline ("em_" ids) are replaced.

What changed from merge_sources.py (an audit of the old units):
* Transcripts come from the raw files (elon_sources.read_transcript) with
  every word kept, each chunk's start time and video link ("Watch at
  1:02:14"), and the interview's date. Where the transcript names its
  speakers (TED, Don Lemon) only Elon's turns are kept. In the others a
  language model told the speakers apart (speaker_labels.py, cached labels,
  accuracy measured on TED and Don Lemon): only the sentences it gave Elon
  are kept, marked speaker_inferred. Without cached labels the interviewer
  can't be told apart, so those chunks are only marked speaker_verified =
  False (quotes still drop interviewers' questions, services/mix_method.py).
* Auto-captions with no punctuation (four interviews) are cut between
  caption lines, at pauses, instead of being one 10,000-word memory.
* The Isaacson biography: letters the PDF lost to fi/fl/ff ligatures ("rst",
  "nancial") are restored, and its index and photo-credit pages are dropped.
* All long texts are cut at sentence ends (44% of interview chunks used to
  end mid-sentence).
* Tweets keep the post they quote or reply to, when the archive has it
  ("Vote for @realDonaldTrump if you want humanity to make it to Mars!" was
  shown without what it answered).
* Sources carry dates (elon_sources.sources()); 97% of non-tweet memories
  used to be "unknown".
"""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import itertools
import json
import re
import shutil
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import elon_sources as es  # noqa: E402
import merge_sources  # noqa: E402
import speaker_labels  # noqa: E402

UNITS_PATH = ROOT / "04-Memory-Units" / "elon_musk_memory_units.jsonl"
TWEETS_CSV = ROOT / "02-Cleaned-Data" / "Tweet" / "elon-tweets-cleaned.csv"
RAW_TWEETS = ROOT / "01-Raw-Data" / "Tweets" / "ultraraw" / "all_musk_posts.csv"
BIOGRAPHY = ROOT / "02-Cleaned-Data" / "Books" / "Elon Musk (Walter Isaacson).pdf"
OTHER_TEXTS = [ROOT / "02-Cleaned-Data" / "Books" / "Isaacson-Quotes-cleaned.md",
               ROOT / "02-Cleaned-Data" / "Books" / "Vance-Quotes-cleaned.md",
               *sorted((ROOT / "02-Cleaned-Data" / "MINIMAX").glob("*.md"))]
TARGET_WORDS, MAX_WORDS = 45, 100
MAX_TWEETS = 10_000
LIGATURES = ("fi", "fl", "ff", "ffi", "ffl")


# ---- Sentence chunks ----

def sentence_chunks(sentences: list[str], target: int = TARGET_WORDS, max_words: int = MAX_WORDS) -> list[list[int]]:
    """Group consecutive sentences (by index) into chunks of about *target*
    words. A chunk only ever ends at a sentence end; a run-on sentence
    longer than *max_words* is its own chunk."""
    chunks, current, words = [], [], 0
    for i, sentence in enumerate(sentences):
        n = len(sentence.split())
        if current and words + n > max_words:
            chunks.append(current)
            current, words = [], 0
        current.append(i)
        words += n
        if words >= target:
            chunks.append(current)
            current, words = [], 0
    if current:
        if chunks and words < target // 3:
            chunks[-1].extend(current)  # don't leave a scrap at the end
        else:
            chunks.append(current)
    return chunks


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?:(?<=[.!?])|(?<=[.!?][\"'”’)]))\s+(?=[A-Z0-9\"'“‘(])", text) if s.strip()]


# ---- Transcripts ----

def transcript_units(sources: dict) -> list[dict]:
    units = []
    for path in sorted(es.RAW_INTERVIEWS.glob("*.txt")):
        info = sources.get(path.name)
        if info is None:
            continue
        sentences, labelled = es.read_transcript(path)
        inferred = not labelled and _infer_speakers(path.name, sentences)
        # Runs of the same speaker; with labels, only Elon's runs are kept
        runs = [list(group) for _, group in itertools.groupby(sentences, key=lambda s: s["speaker"])]
        if labelled or inferred:
            runs = [run for run in runs if run[0]["speaker"] == "Elon Musk"]
        for run in runs:
            for idx in sentence_chunks([s["text"] for s in run]):
                text = " ".join(run[i]["text"] for i in idx)
                start = run[idx[0]]["start"]
                units.append({
                    "text": text, "source_file": path.name, "source_name": info["title"], "source_type": "interview",
                    "date": info.get("date") or "", "date_kind": "published",
                    "start_seconds": start, "url": es.watch_link(info.get("url"), start) or "",
                    "speaker_verified": labelled,
                    # auto-captions with no punctuation: cut between caption lines, not at sentence ends
                    "punctuated": run[0]["punctuated"],
                    **({"speaker_inferred": True} if inferred else {}),
                })
    return units


def _infer_speakers(name: str, sentences: list[dict]) -> bool:
    """Speakers from the cached model labels (speaker_labels.py), when nearly
    every sentence has one. A sentence the model left unlabelled stays (as
    before: unknown), so nothing of Elon's is dropped for lack of a label."""
    labels = speaker_labels.trusted_labels(name, sentences)
    if not labels or labels.count(None) > 0.05 * len(labels):
        return False
    for sentence, who in zip(sentences, labels):
        sentence["speaker"] = "Other" if who == "O" else "Elon Musk"
    return True


# ---- The biography ----

def vocabulary() -> set[str]:
    """Words known to be real: from tweets, transcripts and the public-domain books."""
    words: Counter = Counter()
    texts = [TWEETS_CSV, *es.RAW_INTERVIEWS.glob("*.txt"), *(ROOT / "figures" / "data").glob("*/clean/*.md")]
    for path in texts:
        words.update(re.findall(r"[a-z]+", path.read_text(encoding="utf-8", errors="ignore").lower()))
    return {w for w, n in words.items() if n >= 2}


def repair_ligatures(text: str, vocab: set[str]) -> str:
    """Fill each "\\x00" the PDF left for a fi/fl/ff/ffi/ffl ligature with the
    letters that make a real word ("di\\x00erent" -> "different")."""
    def fix(m: re.Match) -> str:
        word = m.group(0)
        options = []
        for combo in itertools.product(LIGATURES, repeat=word.count("\x00")):
            candidate = word
            for lig in combo:
                candidate = candidate.replace("\x00", lig, 1)
            options.append(candidate)
        known = [c for c in options if all(part in vocab for part in re.findall(r"[a-z]+", c.lower()))]
        return (known or options)[0]
    return re.sub(r"[A-Za-z'’-]*\x00[A-Za-z\x00'’-]*", fix, text)


_MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
# Chapter headings: "Hardcore" then "Twitter, November 18–30, 2022" or "Pretoria, 1971–1984"
_HEADING_DATE = re.compile(rf"^[A-Z][^.!?]{{0,60}}, (?:(?:{_MONTHS})(?: \d{{1,2}}(?:[–-]\d{{1,2}})?)?,? )?\d{{4}}(?:s|[–-]\d{{2,4}})?$")
_CAPTION = re.compile(r"^(?:Clockwise|Top|Bottom|Left|Right|Above|Below|Center|Opposite|Inset)\b[^:]{0,40}:")


def _is_back_matter(lines: list[str]) -> bool:
    """Index, contents, notes, photo-credit and copyright pages."""
    if any("ISBN" in line or "Library of Congress" in line for line in lines):
        return True
    if len(lines) < 8:
        return False
    numbered = sum(bool(re.search(r"\d+(?:[–-]\d+)?[.)]?$", line)) for line in lines)
    credits = sum(line.startswith("Page ") and "Courtesy" in line for line in lines)
    return numbered / len(lines) > 0.5 or credits >= 3


def _prose_lines(lines: list[str]) -> list[str]:
    """A page's lines without chapter headings and photo captions."""
    keep = []
    for line in lines:
        if re.fullmatch(r"(?:Chapter|CHAPTER) \d+", line) or _CAPTION.match(line):
            continue
        if _HEADING_DATE.match(line):
            if keep and len(keep[-1].split()) <= 6 and not re.search(r"[.!?:,;”’\"]$", keep[-1]):
                keep.pop()  # the chapter's title, just above its place and date
            continue
        keep.append(line)
    return keep


def biography_units(info: dict) -> list[dict]:
    import pdfplumber

    vocab = vocabulary()
    pages = []
    with pdfplumber.open(BIOGRAPHY) as pdf:
        for number, page in enumerate(pdf.pages, 1):
            lines = [line.strip() for line in (page.extract_text() or "").split("\n") if line.strip()]
            if lines and lines[0] in ("Acknowledgments", "Acknowledgements") and number > len(pdf.pages) // 2:
                break  # then the author's note, sources, endnotes and index: not the biography
            if not lines or _is_back_matter(lines):
                continue
            pages.append((number, lines))
    # Running heads and bare page numbers repeat on many pages: not prose
    repeats = Counter(line for _, lines in pages for line in set(lines))
    common = {line for line, n in repeats.items() if n > len(pages) * 0.05 and len(line.split()) <= 6}
    sentences, starts = [], []
    carry, carry_page = "", None
    for number, lines in pages:
        body = _prose_lines([line for line in lines if line not in common and not re.fullmatch(r"\d{1,4}", line)])
        text = repair_ligatures(" ".join(body), vocab)
        text = re.sub(r"(\w)- (?=[a-z])", r"\1", text)  # words hyphenated across lines
        pieces = split_sentences((carry + " " + text).strip())
        if not pieces:
            continue
        for piece in pieces[:-1]:
            sentences.append(piece)
            starts.append(carry_page or number)
            carry_page = number
        carry, carry_page = pieces[-1], carry_page or number
    if carry:
        sentences.append(carry)
        starts.append(carry_page)
    return [{"text": " ".join(sentences[i] for i in idx), "source_file": BIOGRAPHY.name, "source_name": info["title"],
             "source_type": "pdf", "date": info["date"], "date_kind": "published", "page": starts[idx[0]]}
            for idx in sentence_chunks(sentences)]


# ---- Tweets ----

def _raw_tweets() -> dict:
    csv.field_size_limit(10 ** 9)
    with RAW_TWEETS.open(encoding="utf-8", errors="ignore", newline="") as handle:
        return {row["id"]: row for row in csv.DictReader(handle)}


def _quoted(row: dict) -> tuple[str, str]:
    """(author, text) of the post a tweet quotes, from the raw export."""
    try:
        quote = ast.literal_eval(row.get("quote") or "")
    except (ValueError, SyntaxError):
        return "", ""
    if not isinstance(quote, dict):
        return "", ""
    author = quote.get("author") or {}
    name = author.get("userName") or author.get("screen_name") or "" if isinstance(author, dict) else ""
    return name, str(quote.get("text") or "")


def tweet_units() -> list[dict]:
    raw = _raw_tweets()
    units = []
    with TWEETS_CSV.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            text = merge_sources.strip_timestamp_cues(str(row.get("text") or "").strip())
            if len(text) < 10 or re.match(r"^@\w{3,}", text) or text.startswith("RT @"):
                continue
            unit = {"text": text, "source_file": TWEETS_CSV.name, "source_name": "Elon Musk on X", "source_type": "tweet",
                    "date": row.get("date_str") or "", "date_kind": "posted", "url": row.get("url") or ""}
            source = raw.get(row.get("id", ""), {})
            author, quoted = _quoted(source)
            parent = raw.get(source.get("inReplyToId") or "")
            if quoted:
                unit.update(context_kind="quote", context_author=author, context_text=quoted[:400])
            elif parent:
                unit.update(context_kind="reply", context_author="elonmusk", context_text=parent["fullText"][:400])
            elif source.get("inReplyToUsername") or row.get("reply_to"):
                unit.update(context_kind="reply", context_author=source.get("inReplyToUsername") or row.get("reply_to"),
                            context_text="")
            if str(row.get("has_media")).lower() == "true":
                unit["has_media"] = True
            units.append(unit)
    return units


# ---- Everything else (quotes collected from the books, news dossiers) ----

def other_units(sources: dict) -> list[dict]:
    units = []
    for path in OTHER_TEXTS:
        info = sources.get(path.name, {})
        for record in merge_sources.parse_markdown(path):
            for idx in sentence_chunks(sentences := split_sentences(record["text"])):
                units.append({**{k: v for k, v in record.items() if k not in ("char_count", "word_count")},
                              "text": " ".join(sentences[i] for i in idx),
                              "date": info.get("date") or "", "date_kind": "published" if info else ""})
    return units


def build(refresh_sources: bool = False) -> list[dict]:
    sources = es.sources(refresh=refresh_sources)
    units = transcript_units(sources) + biography_units(sources[BIOGRAPHY.name]) + other_units(sources)
    tweets = tweet_units()
    seen, out = set(), []
    for unit in units + tweets:
        unit["char_count"], unit["word_count"] = len(unit["text"]), len(unit["text"].split())
        key = hashlib.md5(unit["text"].encode("utf-8")).hexdigest()
        if key in seen or unit["word_count"] == 0:
            continue
        seen.add(key)
        out.append(unit)
    out = merge_sources.rebalance_sources(out, max_tweets=MAX_TWEETS)
    now = datetime.now().isoformat()
    for unit in out:
        unit.update(memory_id="em_" + hashlib.md5(unit["text"].encode("utf-8")).hexdigest()[:12], person="elon_musk",
                    created_at=now, importance_score=merge_sources.estimate_importance(unit))
    return out


def save(units: list[dict]) -> Path | None:
    backup = None
    if UNITS_PATH.exists():
        backup = ROOT.parent / "_backups" / f"{datetime.now():%Y-%m-%d-%H%M}-memory-units" / UNITS_PATH.name
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(UNITS_PATH, backup)
    with UNITS_PATH.open("w", encoding="utf-8") as handle:
        for unit in units:
            handle.write(json.dumps(unit, ensure_ascii=False) + "\n")
    return backup


def embed(units: list[dict]) -> int:
    """Replace the pipeline memories ("em_") in Elon's collection; keep everything else."""
    import chromadb
    import pyarrow.dataset  # noqa: F401  (Windows: before torch)
    import torch
    from sentence_transformers import SentenceTransformer

    from config import config
    from services import chroma_index, instance_lock

    with instance_lock.InstanceLock(instance_lock.lock_path(config.CHROMA_PATH)):
        collection = chromadb.PersistentClient(path=config.CHROMA_PATH).get_or_create_collection(
            config.COLLECTION_NAME, metadata=chroma_index.COLLECTION_METADATA)
        chroma_index.ensure_saved(collection)
        new_ids = {u["memory_id"] for u in units}
        old = [i for i in collection.get(include=[])["ids"] if i.startswith("em_") and i not in new_ids]
        for start in range(0, len(old), 2000):
            collection.delete(ids=old[start:start + 2000])
        model = SentenceTransformer(config.EMBEDDING_MODEL, device="cuda" if torch.cuda.is_available() else "cpu")
        for start in range(0, len(units), 256):
            batch = units[start:start + 256]
            metas = [{k: v for k, v in u.items() if k != "text" and v is not None and v != ""} for u in batch]
            collection.upsert(ids=[u["memory_id"] for u in batch], documents=[u["text"] for u in batch], metadatas=metas,
                              embeddings=model.encode([u["text"] for u in batch], normalize_embeddings=True).tolist())
        return collection.count()


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild Elon's memories from the raw sources")
    parser.add_argument("--embed", action="store_true", help="also replace them in chroma_db (stop the server first)")
    parser.add_argument("--refresh-sources", action="store_true", help="re-read titles and dates from YouTube")
    args = parser.parse_args()
    units = build(args.refresh_sources)
    backup = save(units)
    by_type = Counter(u["source_type"] for u in units)
    print(f"{len(units):,} memory units: {dict(by_type)}" + (f" (old file kept at {backup})" if backup else ""))
    if args.embed:
        print(f"Elon's collection now has {embed(units):,} memories")


if __name__ == "__main__":
    main()
