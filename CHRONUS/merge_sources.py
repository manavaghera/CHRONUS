#!/usr/bin/env python3
"""
CHRONUS - Data Ingestion Pipeline
Merges cleaned sources into:
1. a flat master dataset for inspection in Obsidian/CSV
2. chunked JSONL memory units for downstream embedding
"""

import csv
import hashlib
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

# TASK 2.1 FIX: PDF support for the Isaacson biography (and future PDFs)
import pdfplumber


VAULT_ROOT = Path(__file__).parent
CLEANED_DIR = VAULT_ROOT / "02-Cleaned-Data"
MEMORY_DIR = VAULT_ROOT / "04-Memory-Units"
MEMORY_DIR.mkdir(exist_ok=True)

MASTER_CSV = CLEANED_DIR / "master-elon-data.csv"
MASTER_MD = CLEANED_DIR / "master-elon-data.md"
MEMORY_JSONL = MEMORY_DIR / "elon_musk_memory_units.jsonl"

# Raw or superseded copies that sit next to their cleaned versions in
# 02-Cleaned-Data/. Ingesting both put every interview in the database 2-3
# times, so retrieval returned near-duplicate chunks and the noisy raw text.
# Paths are relative to CLEANED_DIR.
SUPERSEDED_FILES = {
    # Raw transcripts — byte-identical to 01-Raw-Data/Interviews/; each has a
    # cleaned sibling ("... clean.md", "TED2022 CLEAN.md", "TED TEST fractory.md")
    "Interviews/2025 shareholders.txt",
    "Interviews/ALL-IN-ONE-MULTI.txt",
    "Interviews/ALL-in-One online.txt",
    "Interviews/All-In Summit 2024.txt",
    "Interviews/Don Lemon.txt",
    "Interviews/Dwarkesh patel.txt",
    "Interviews/Joe Rogan podcast.txt",
    "Interviews/Lex Fridman Podcast.txt",
    "Interviews/Nikhil.txt",
    "Interviews/TED Tesla fract.txt",
    "Interviews/TED2022.txt",
    # Same as "Lex Fridman Podcast clean.md" minus some "basically"/"mhm"
    "Interviews/Lex Fridman Podcast processed.md",
    # Raw quote list, includes lines said by other people; the -cleaned file
    # keeps only Elon's quotes
    "Books/Isaacson-Quotes.md",
    # Superset of Tweet/elon-tweets-cleaned.csv that also contains retweets
    "ELON/elon_musk_tweetsmain.csv",
}


def extract_date_from_filename(name: str) -> str:
    """Extract date from filename using multiple patterns.

    TASK 2.4 FIX: Expanded to handle more date formats. Previously only a
    bare 4-digit year was matched (normalized to YYYY-01-01); most records
    fell through to "unknown".

    Note: this intentionally deviates from the naive group-count approach in
    the task spec — the spec's last pattern captures only the century prefix
    ("20") and its US-format branch would treat the month as the year.
    Instead, each pattern carries an explicit field layout, and month/day
    values are range-validated before being accepted.
    """
    patterns = [
        # ISO: 2023-03-15 → y, m, d
        (re.compile(r"(\d{4})-(\d{2})-(\d{2})(?!\d)"), "ymd"),
        # Compact ISO: 20230315 → y, m, d
        (re.compile(r"(?<!\d)(\d{4})(\d{2})(\d{2})(?!\d)"), "ymd"),
        # Year-month: 2023-03
        (re.compile(r"(\d{4})-(\d{2})(?!\d)"), "ym"),
        # US: 03-15-2023 or 03/15/2023 → m, d, y
        (re.compile(r"(?<!\d)(\d{1,2})[-/](\d{1,2})[-/](\d{4})(?!\d)"), "mdy"),
        # Year in parentheses or brackets: (2023), [2023]
        (re.compile(r"[\(\[]((?:19|20)\d{2})[\)\]]"), "y"),
        # Standalone 4-digit year at word boundary (19xx / 20xx only)
        (re.compile(r"\b((?:19|20)\d{2})\b"), "y"),
    ]

    def _valid_month(m: str) -> bool:
        return m.isdigit() and 1 <= int(m) <= 12

    def _valid_day(d: str) -> bool:
        return d.isdigit() and 1 <= int(d) <= 31

    for pattern, layout in patterns:
        match = pattern.search(name)
        if not match:
            continue
        groups = match.groups()

        if layout == "ymd":
            y, m, d = groups
            if _valid_month(m) and _valid_day(d):
                return f"{y}-{m}-{d}"
        elif layout == "ym":
            y, m = groups
            if _valid_month(m):
                return f"{y}-{m}"
        elif layout == "mdy":
            m, d, y = groups
            if _valid_month(m) and _valid_day(d):
                return f"{y}-{m.zfill(2)}-{d.zfill(2)}"
        elif layout == "y":
            return groups[0]

    return "unknown"


def clean_source_name(file_path: Path) -> str:
    """Normalize source names for display/export."""
    name = file_path.stem
    name = re.sub(r"(?i)-?clean(?:ed)?$", "", name).strip(" -_")
    return name or file_path.stem


def strip_timestamp_cues(text: str) -> str:
    """TASK 2.6 FIX: Remove timestamp patterns from transcript text.

    Interview transcripts contain raw timestamp cues like "00:50:52.839" or
    "1:23:45" that got embedded as memory text — wasting embedding space and
    polluting verbatim quotes in the Mix Method output. Applied AFTER text
    extraction and BEFORE chunking in every parse_* function.
    """
    # HH:MM:SS.mmm format (e.g. 00:50:52.839)
    text = re.sub(r"\b\d{2}:\d{2}:\d{2}\.\d{1,3}\b", "", text)
    # HH:MM:SS format (e.g. 1:23:45)
    text = re.sub(r"\b\d{1,2}:\d{2}:\d{2}\b", "", text)
    # MM:SS format (standalone, not part of a longer number/timestamp)
    text = re.sub(r"(?<!\d)\b\d{1,2}:\d{2}\b(?!\d)", "", text)
    # Clean up resulting extra whitespace
    text = re.sub(r"  +", " ", text)
    text = re.sub(r"\n\s*\n\s*\n", "\n\n", text)
    return text.strip()


def infer_source_type(file_path: Path) -> str:
    """Infer source type from filename + folder + content hints."""
    name_lower = file_path.stem.lower()
    parts = {part.lower() for part in file_path.parts}
    suffix = file_path.suffix.lower()
    if "books" in parts or "book" in parts:
        return "book"
    if "tweet" in name_lower or "tweetsmain" in name_lower:
        return "tweet"
    if suffix == ".csv":
        return "tweet"
    interview_keywords = [
        "joe rogan", "lex fridman", "all-in", "all in",
        "dwarkesh", "don lemon", "podcast", "interview",
        "summit", "shareholders", "shareholder",
    ]
    if any(kw in name_lower for kw in interview_keywords):
        return "interview"
    # TED talks ("TED2022 CLEAN", "TED TEST fractory") — anchored so words
    # merely containing "ted" don't match
    if re.match(r"ted(\d|\b)", name_lower):
        return "interview"
    news_keywords = ["news", "dossier", "duckduckgo", "osint"]
    if any(kw in name_lower for kw in news_keywords):
        return "news"
    if "youtube" in name_lower or "yt" in name_lower:
        return "video"
    return "document"


def infer_topic(text: str) -> str:
    """Simple keyword-based topic tagging.

    # DEPRECATED: Topic tagging is noisy and unused in retrieval. Kept for potential future use.
    # TASK 2.7: chunks no longer carry a "topic" field — infer_topic is NOT called
    # anywhere in the pipeline anymore. Verified: embed_elon.py only *stores*
    # topic in Chroma metadata via record.get("topic", "") (safe with missing
    # key), and api_server.py never reads it for retrieval or response
    # generation (its only "topic" match is the unrelated hardcoded
    # "topic_tag" key for auto-trained Q&A units).
    """
    text_lower = text.lower()
    topic_keywords = {
        "ai_safety": ["ai", "artificial intelligence", "agi", "existential risk", "alignment"],
        "mars_space": ["mars", "spacex", "rocket", "space", "starship", "colonization"],
        "tesla_ev": ["tesla", "electric vehicle", "ev", "autopilot", "fsd", "battery"],
        "twitter_x": ["twitter", "x platform", "social media", "free speech"],
        "work_culture": ["work", "hardcore", "factory", "sleep", "hours", "engineer"],
        "physics": ["physics", "first principles", "thermodynamics", "math"],
        "philosophy": ["meaning", "consciousness", "universe", "simulation", "reality"],
        "politics": ["government", "regulation", "policy", "democrat", "republican"],
        "education": ["education", "college", "degree", "learning", "school"],
    }

    for topic, keywords in topic_keywords.items():
        if any(keyword in text_lower for keyword in keywords):
            return topic
    return "general"


def parse_markdown(file_path: Path) -> List[Dict[str, Any]]:
    """Parse transcripts, quotes, and cleaned documents - tolerant of all formats."""
    # TASK 2.6 FIX: strip timestamp cues right after extraction, before chunking
    text = strip_timestamp_cues(file_path.read_text(encoding="utf-8", errors="ignore"))
    if not text:
        return []

    chunks = []

    if "#" in text:
        chunks = re.split(r"\n#{1,3}\s+", text)

    if len(chunks) < 3:
        chunks = re.split(r"\n\s*\n+", text)

    if not chunks or all(len(c) > 5000 for c in chunks):
        chunks = re.split(
            r"\n(?=\[?(Elon|Interviewer|Host|Question|Q|A|Lex|Joe|Rogan|Dwarkesh|Don)[\]\s:])",
            text, flags=re.IGNORECASE,
        )

    if not chunks or all(len(c) > 5000 for c in chunks):
        sentences = re.split(r"(?<=[.!?])\s+", text)
        chunks = [" ".join(sentences[i:i+6]) for i in range(0, len(sentences), 6)]

    final = []
    for c in chunks:
        c = c.strip()
        if len(c) >= 50:
            final.append(c)

    if not final:
        return []

    source_type = infer_source_type(file_path)
    source_name = clean_source_name(file_path)

    return [
        {
            "text": chunk,
            "source_file": file_path.name,
            "source_name": source_name,
            "source_type": source_type,
            "date": extract_date_from_filename(file_path.name),
            # TASK 2.7 FIX: "topic" removed from output chunks (noisy, unused)
            "char_count": len(chunk),
            "word_count": len(chunk.split()),
        }
        for chunk in final
    ]


def parse_csv_file(file_path: Path) -> List[Dict[str, Any]]:
    """Parse CSV files, primarily tweet datasets."""
    records: List[Dict[str, Any]] = []
    source_type = infer_source_type(file_path)
    source_name = clean_source_name(file_path)

    with file_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            # TASK 2.6 FIX: strip timestamp cues from tweet text fields
            text = str(row.get("text") or row.get("tweet") or row.get("content") or "").strip()
            text = strip_timestamp_cues(text)
            if len(text) < 10:
                continue
            if re.match(r"^@\w{3,}", text):
                continue
            # Retweets are someone else's words, not Elon's
            if text.startswith("RT @"):
                continue

            date_value = (
                row.get("date")
                or row.get("date_str")
                or row.get("created_at")
                or extract_date_from_filename(file_path.name)
            )

            records.append(
                {
                    "text": text,
                    "source_file": file_path.name,
                    "source_name": source_name,
                    "source_type": source_type,
                    "date": date_value,
                    # TASK 2.7 FIX: "topic" removed from output chunks (noisy, unused)
                    "char_count": len(text),
                    "word_count": len(text.split()),
                }
            )

    return records


def parse_json_file(file_path: Path) -> List[Dict[str, Any]]:
    """Parse JSON files (list of objects or {items: [...]} shape)."""
    try:
        data = json.loads(file_path.read_text(encoding="utf-8", errors="ignore"))
    except json.JSONDecodeError:
        return []
    if isinstance(data, dict):
        for key in ("items", "data", "records", "chunks", "memories"):
            if key in data and isinstance(data[key], list):
                data = data[key]
                break
        else:
            return []
    if not isinstance(data, list):
        return []
    source_type = infer_source_type(file_path)
    source_name = clean_source_name(file_path)
    out = []
    for item in data:
        if not isinstance(item, dict):
            continue
        # TASK 2.6 FIX: strip timestamp cues from JSON text fields
        text = str(item.get("text") or item.get("content") or item.get("tweet") or "").strip()
        text = strip_timestamp_cues(text)
        if len(text) < 10:
            continue
        out.append({
            "text": text,
            "source_file": file_path.name,
            "source_name": source_name,
            "source_type": source_type,
            "date": item.get("date") or extract_date_from_filename(file_path.name),
            # TASK 2.7 FIX: "topic" removed from output chunks (noisy, unused)
            "char_count": len(text),
            "word_count": len(text.split()),
        })
    return out


# ---------------------------------------------------------------------------
# TASK 2.1 FIX: PDF parser
# ---------------------------------------------------------------------------
def parse_pdf_file(file_path: str) -> list[dict]:
    """Extract text from PDF files with page-level tracking.

    Args:
        file_path: Path to PDF file

    Returns:
        List of chunks with source metadata
    """
    chunks = []
    filename = os.path.basename(file_path)

    try:
        with pdfplumber.open(file_path) as pdf:
            print(f"  PDF: {filename} ({len(pdf.pages)} pages)")

            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text()

                if not text or len(text.strip()) < 50:
                    continue

                # TASK 2.6 FIX: strip timestamp cues from extracted PDF text
                text = strip_timestamp_cues(text)
                # Strip NUL artifacts: some embedded fonts map ligatures
                # (ﬁ ﬂ ﬀ …) to unassigned glyph codes, which pdfplumber
                # surfaces as "\x00". NULs are never legitimate prose.
                text = text.replace("\x00", "")

                chunks.append({
                    "text": text,
                    "source_file": filename,
                    "source_type": "pdf",
                    "source_name": filename.replace(".pdf", ""),
                    "page": page_num,
                    "date": "unknown",
                    # TASK 2.7 FIX: "topic" not included (deprecated, unused)
                    "char_count": len(text),
                    "word_count": len(text.split()),
                })

    except Exception as e:
        print(f"  ERROR parsing PDF {filename}: {e}")

    return chunks


def smart_chunk(text: str, max_words: int = 80, overlap: int = 15) -> List[str]:
    """Chunk text into overlapping windows for embeddings."""
    words = text.split()
    if len(words) <= max_words:
        return [text]

    chunks: List[str] = []
    start = 0
    step = max_words - overlap
    while start < len(words):
        end = min(start + max_words, len(words))
        chunks.append(" ".join(words[start:end]))
        start += step

    return chunks


def chunk_record(record: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Split long records into smaller memory units."""
    chunks = smart_chunk(record["text"])
    if len(chunks) == 1:
        return [record.copy()]

    return [
        {
            **record,
            "text": chunk,
            "chunk_index": index,
            "total_chunks": len(chunks),
            "parent_text": record["text"][:200] + ("..." if len(record["text"]) > 200 else ""),
            "char_count": len(chunk),
            "word_count": len(chunk.split()),
        }
        for index, chunk in enumerate(chunks)
    ]


def estimate_importance(record: Dict[str, Any]) -> int:
    """Score 1-5 based on length, source curation, and quoting.

    TASK 2.7 FIX: the old "topic specificity" bonus (record["topic"] != "general")
    was removed along with the deprecated topic tagging — it rewarded chunks for
    keyword-stuffed tagging rather than actual content quality.
    """
    score = 1

    if record["word_count"] > 50:
        score += 1
    if record["word_count"] > 100:
        score += 1
    if '"' in record["text"] or "'" in record["text"]:
        score += 1
    if record["source_type"] in {"book", "interview"}:
        score += 1

    return min(score, 5)


def rebalance_sources(memory_records, max_tweets=10000):
    """Cap tweet volume so long-form content can compete at retrieval."""
    tweets = [r for r in memory_records if r.get("source_type") == "tweet"]
    non_tweets = [r for r in memory_records if r.get("source_type") != "tweet"]
    print(f"\nBefore cap: {len(tweets):,} tweets + {len(non_tweets):,} non-tweet = {len(memory_records):,}")
    if len(tweets) > max_tweets:
        tweets.sort(key=lambda r: (r.get("importance_score", 1), r.get("word_count", 0)), reverse=True)
        tweets = tweets[:max_tweets]
    rebalanced = tweets + non_tweets
    print(f"After cap:  {len(tweets):,} tweets + {len(non_tweets):,} non-tweet = {len(rebalanced):,}")
    return rebalanced


def process_all_sources() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Walk through cleaned data and build raw plus chunked datasets."""
    raw_records: List[Dict[str, Any]] = []
    memory_records: List[Dict[str, Any]] = []
    generated_outputs = {MASTER_CSV.resolve(), MASTER_MD.resolve()}
    missing = sorted(p for p in SUPERSEDED_FILES if not (CLEANED_DIR / p).exists())
    if missing:
        print(f"WARNING: SUPERSEDED_FILES entries not found (renamed?): {missing}")

    for file_path in sorted(CLEANED_DIR.rglob("*")):
        if file_path.is_dir():
            continue
        if file_path.resolve() in generated_outputs:
            print(f"Skipping generated file: {file_path.relative_to(VAULT_ROOT)}")
            continue
        if file_path.relative_to(CLEANED_DIR).as_posix() in SUPERSEDED_FILES:
            print(f"Skipping superseded file: {file_path.relative_to(VAULT_ROOT)}")
            continue

        suffix = file_path.suffix.lower()
        print(f"Processing: {file_path.relative_to(VAULT_ROOT)}")

        if suffix == ".md" or suffix == ".txt":
            records = parse_markdown(file_path)
        elif suffix == ".csv":
            records = parse_csv_file(file_path)
        elif suffix == ".json":
            records = parse_json_file(file_path)
        elif suffix == ".pdf":
            # TASK 2.1 FIX: route PDFs (e.g. the Isaacson biography) to the new parser
            records = parse_pdf_file(str(file_path))
        else:
            print(f"  Skipped unsupported format: {suffix}")
            continue

        raw_records.extend(records)

        chunk_total = 0
        for record in records:
            chunked_records = chunk_record(record)
            memory_records.extend(chunked_records)
            chunk_total += len(chunked_records)

        print(f"  Extracted {len(records)} records -> {chunk_total} chunks")

    return raw_records, memory_records


def save_master_csv(records: List[Dict[str, Any]]) -> None:
    """Save the flat merged dataset as CSV."""
    fieldnames = [
        "source_type",
        "source_name",
        "source_file",
        "date",
        # TASK 2.7 FIX: "topic" column removed — deprecated noisy tagging
        "char_count",
        "word_count",
        "text",
    ]

    with MASTER_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow({field: record.get(field, "") for field in fieldnames})


def save_master_markdown(records: List[Dict[str, Any]]) -> None:
    """Save a human-readable master note for Obsidian."""
    counts = {
        "interview": sum(1 for record in records if record["source_type"] == "interview"),
        "book": sum(1 for record in records if record["source_type"] == "book"),
        "tweet": sum(1 for record in records if record["source_type"] == "tweet"),
        "document": sum(1 for record in records if record["source_type"] == "document"),
    }

    with MASTER_MD.open("w", encoding="utf-8") as handle:
        handle.write("# Elon Musk Master Dataset\n")
        handle.write(f"# Total entries: {len(records)}\n\n")
        handle.write("| interviews | books | tweets | documents |\n")
        handle.write("|---|---|---|---|\n")
        handle.write(
            f"| {counts['interview']} | {counts['book']} | {counts['tweet']} | {counts['document']} |\n\n"
        )
        handle.write("---\n\n")

        for record in records:
            handle.write(f"[{record['source_type']}][{record['source_name']}]\n")
            handle.write(f"{record['text']}\n\n")


def save_memory_units(records: List[Dict[str, Any]]) -> None:
    """Save chunked memory units as JSONL."""
    with MEMORY_JSONL.open("w", encoding="utf-8") as handle:
        for record in records:
            enriched = dict(record)
            enriched["memory_id"] = "em_" + hashlib.md5(record["text"].encode("utf-8")).hexdigest()[:12]
            enriched["person"] = "elon_musk"
            enriched["created_at"] = datetime.now().isoformat()
            enriched["importance_score"] = estimate_importance(record)
            handle.write(json.dumps(enriched, ensure_ascii=False) + "\n")


def print_stats(raw_records: List[Dict[str, Any]], memory_records: List[Dict[str, Any]]) -> None:
    """Print a compact summary."""
    total_words = sum(record["word_count"] for record in memory_records)
    by_source: Dict[str, int] = {}
    # TASK 2.7 FIX: "Top Topics" breakdown removed along with the deprecated,
    # noisy topic tagging (infer_topic no longer runs, chunks carry no "topic").

    for record in memory_records:
        by_source[record["source_file"]] = by_source.get(record["source_file"], 0) + 1
        # TASK 2.7 FIX: per-record topic counting removed (deprecated tagging)

    source_type_counts: Dict[str, int] = {}
    for record in raw_records:
        source_type_counts[record["source_type"]] = source_type_counts.get(record["source_type"], 0) + 1

    print("\n" + "=" * 60)
    print("CHRONUS - ELON MUSK MEMORY DATABASE")
    print("=" * 60)
    print(f"Raw Records: {len(raw_records):,}")
    print(f"Memory Units: {len(memory_records):,}")
    print(f"Total Words: {total_words:,}")
    print(f"Average Words/Unit: {(total_words // len(memory_records)) if memory_records else 0:,}")
    print("\nBy Source Type:")
    for source_type, count in sorted(source_type_counts.items(), key=lambda item: (-item[1], item[0])):
        print(f"  {source_type:12s} -> {count:4d} records")
    print("\nTop Source Files:")
    for source_file, count in sorted(by_source.items(), key=lambda item: (-item[1], item[0]))[:10]:
        print(f"  {source_file:30s} -> {count:4d} units")
    # TASK 2.7 FIX: "Top Topics:" print block removed (see comment above)
    print("=" * 60)


def main() -> None:
    print("CHRONUS Data Ingestion Pipeline")
    print("=" * 60)

    raw_records, memory_records = process_all_sources()
    memory_records = rebalance_sources(memory_records, max_tweets=10000)

    seen = set()
    unique = []
    for r in memory_records:
        content_key = hashlib.md5(r["text"].encode("utf-8")).hexdigest()
        if content_key not in seen:
            seen.add(content_key)
            unique.append(r)
    memory_records = unique
    print(f"After dedup: {len(memory_records):,} unique units")
    save_master_csv(raw_records)
    save_master_markdown(raw_records)
    save_memory_units(memory_records)
    print_stats(raw_records, memory_records)

    print("\nSaved to:")
    print(f"  {MASTER_CSV.relative_to(VAULT_ROOT)}")
    print(f"  {MASTER_MD.relative_to(VAULT_ROOT)}")
    print(f"  {MEMORY_JSONL.relative_to(VAULT_ROOT)}")


if __name__ == "__main__":
    main()
