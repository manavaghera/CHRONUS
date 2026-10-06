"""
Training data for the Elon Musk LoRA adapter: only text that is
unmistakably his own words.

* his tweets in memory (retweets were already removed by merge_sources.py)
* his direct quotes in the Isaacson and Vance biographies

Left out: interview transcripts (host and Elon are mixed, with no speaker
labels), the 25 LLM-written interview answers, and the TED Gigafactory
interview (the match test's answer key, evaluation/ted_qa.py).

    python lora/prepare_data.py   ->  lora/data/train.jsonl, val.jsonl
"""

from __future__ import annotations

import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import chromadb  # noqa: E402

from config import config  # noqa: E402

OUT = Path(__file__).resolve().parent / "data"
QUOTE_FILES = ["Isaacson-Quotes-cleaned.md", "Vance-Quotes-cleaned.md"]
# Neutral prompts: the adapter should learn how he talks, not a topic mapping
PROMPTS = ["What's on your mind?", "Share a thought.", "What do you think?", "Say it in your own words."]
MIN_WORDS = 6
VAL_SHARE = 0.05


def clean_tweet(text: str) -> str:
    text = re.sub(r"https?://\S+", "", text)          # links say nothing about his voice
    text = re.sub(r"&amp;", "&", text)
    return re.sub(r"\s+", " ", text).strip()


def main() -> None:
    collection = chromadb.PersistentClient(path=config.CHROMA_PATH).get_collection(config.COLLECTION_NAME)
    tweets = collection.get(where={"source_type": "tweet"}, include=["documents"])["documents"]
    quotes = collection.get(where={"source_file": {"$in": QUOTE_FILES}}, include=["documents"])["documents"]

    texts, seen = [], set()
    for kind, raw in [("tweet", t) for t in tweets] + [("quote", q) for q in quotes]:
        text = clean_tweet(raw) if kind == "tweet" else re.sub(r"\s+", " ", raw).strip()
        key = text.lower()
        if len(text.split()) >= MIN_WORDS and key not in seen:
            seen.add(key)
            texts.append({"kind": kind, "text": text})

    rng = random.Random(42)
    rng.shuffle(texts)
    for item in texts:
        item["prompt"] = rng.choice(PROMPTS)
    n_val = max(50, int(len(texts) * VAL_SHARE))
    OUT.mkdir(parents=True, exist_ok=True)
    for name, rows in (("val", texts[:n_val]), ("train", texts[n_val:])):
        with (OUT / f"{name}.jsonl").open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
    kinds = {k: sum(t["kind"] == k for t in texts) for k in ("tweet", "quote")}
    print(f"{len(texts):,} examples ({kinds['tweet']:,} tweets, {kinds['quote']:,} quotes): "
          f"{len(texts) - n_val:,} train / {n_val:,} validation -> {OUT}")


if __name__ == "__main__":
    main()
