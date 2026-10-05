#!/usr/bin/env python3
"""
CHRONUS - ChromaDB embedding pipeline for Elon Musk memory units.

Reads the JSONL memory-unit file, upserts documents into a persistent local
ChromaDB collection. BUG 7 FIX: embeddings are computed explicitly with the
same sentence-transformers MiniLM-L6-v2 model (and same L2 normalization) that
api_server.py uses at query time — NOT Chroma's built-in default embedding
function — so ingest-time and query-time vectors live in the same space.
"""

from __future__ import annotations

import faulthandler
import json
import os
from pathlib import Path
from typing import Any

# Dump native crash stacks to a file so silent access-violation deaths
# (e.g. DLL conflicts) leave a diagnosable trace instead of empty logs.
_fault_fh = open(Path(__file__).resolve().parent.parent / "embed_crash.log", "w")
faulthandler.enable(_fault_fh)

import chromadb

# WORKAROUND: pyarrow 24.0.0 access-violates (hard native crash, no traceback)
# when pyarrow is loaded AFTER chromadb + torch have initialized their native
# DLLs — which happens via sentence_transformers -> torch/sklearn/datasets.
# Pre-loading pyarrow.dataset FIRST fixes the import order and avoids the crash.
import pyarrow.dataset  # noqa: F401  (must be imported before sentence_transformers)

from sentence_transformers import SentenceTransformer


VAULT_ROOT = Path(__file__).resolve().parent.parent
MEMORY_FILE = VAULT_ROOT / "04-Memory-Units" / "elon_musk_memory_units.jsonl"

# Task 4.2: centralized configuration (config.py at CHRONUS root)
import sys
sys.path.insert(0, str(VAULT_ROOT))
from config import config

CHROMA_PATH = config.CHROMA_PATH
COLLECTION_NAME = config.COLLECTION_NAME
BATCH_SIZE = config.BATCH_SIZE

# BUG 7 FIX: same model + device as api_server.py — both now read
# config.EMBEDDING_MODEL, so ingest/query sync is guaranteed by construction.
EMBED_MODEL = config.EMBEDDING_MODEL
embedder = SentenceTransformer(EMBED_MODEL, device="cpu")


def load_records() -> list[dict[str, Any]]:
    """Load JSONL records from disk."""
    if not MEMORY_FILE.exists():
        raise FileNotFoundError(f"Memory file not found: {MEMORY_FILE}")

    with MEMORY_FILE.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def sanitize_value(value: Any) -> Any:
    """Keep metadata values compatible with Chroma."""
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value)


def sanitize_metadata(record: dict[str, Any]) -> dict[str, Any]:
    """Project a memory unit into Chroma-safe metadata.

    TASK 2.3 FIX: Keep chunk_index, total_chunks, parent_text (and page for
    PDFs) for provenance. Only drop fields that are truly not needed or too
    large. Kept fields: source_file, source_type, source_name, date, topic,
    importance_score, memory_id, person, chunk_index, total_chunks,
    parent_text, page.
    """
    # Fields to DROP (too large, redundant, or not useful in DB)
    drop_keys = {
        "text",           # Already stored as document
        "word_count",     # Can be recalculated
        "char_count",     # Can be recalculated
        "created_at",     # Not useful for retrieval
    }

    return {
        key: sanitize_value(value)
        for key, value in record.items()
        if key not in drop_keys
    }


def build_ids(records: list[dict[str, Any]], start_index: int) -> list[str]:
    """Create stable IDs for Chroma upserts.

    BUG 6 FIX: memory_id is already an MD5 hash unique per text content, so it
    is used alone as the Chroma ID. The old f"{memory_id}_{row_index}" made the
    ID depend on file row position — re-running ingestion with a reordered file
    would mint new IDs for the same text and create duplicate embeddings.
    With content-derived IDs, re-ingestion upserts in place (idempotent).
    """
    ids: list[str] = []
    for offset, record in enumerate(records):
        memory_id = str(record.get("memory_id") or "").strip()
        row_index = start_index + offset
        if memory_id:
            # BUG 6 FIX: content-derived ID only — no positional suffix
            ids.append(memory_id)
        else:
            # Fallback for records without a memory_id (no content hash to
            # derive from); positional ID is the only option remaining here.
            ids.append(f"elon_memory_{row_index}")
    return ids


def get_collection() -> chromadb.Collection:
    """Get or create collection.

    FIX B (Phase 6): Does NOT delete existing data — uses upsert so re-runs
    are idempotent. Previously this wiped the collection on every run, which
    silently destroyed interview-protocol memories (and anything else not in
    the JSONL memory file).
    """
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def embed_all() -> None:
    """Upsert every memory unit into the local ChromaDB collection.

    NOTE: This script is now non-destructive. It upserts into the existing
    collection. To do a full wipe-and-rebuild, delete chroma_db/ manually.
    """
    records = load_records()
    collection = get_collection()

    print(f"Loaded {len(records):,} memory units from {MEMORY_FILE.name}")
    print(f"Using ChromaDB path: {CHROMA_PATH}")
    print(f"Target collection: {COLLECTION_NAME}")

    for start in range(0, len(records), BATCH_SIZE):
        batch = records[start : start + BATCH_SIZE]
        documents = [str(record.get("text", "")).strip() for record in batch]
        metadatas = [sanitize_metadata(record) for record in batch]
        ids = build_ids(batch, start)

        # BUG 7 FIX: encode with the same SentenceTransformer model and the
        # same normalize_embeddings=True setting api_server.py uses at query
        # time. Chroma's built-in default is a different MiniLM runtime (ONNX)
        # — mixing runtimes/normalization between ingest and query risks a
        # vector-space mismatch and degraded retrieval.
        embeddings = embedder.encode(documents, normalize_embeddings=True).tolist()

        collection.upsert(
            ids=ids,
            documents=documents,
            embeddings=embeddings,  # Explicit, not relying on Chroma default
            metadatas=metadatas,
        )

        end = start + len(batch)
        print(f"Upserted {end:,} / {len(records):,}")

    print()
    print(f"Done. Collection '{COLLECTION_NAME}' now has {collection.count():,} items.")


if __name__ == "__main__":
    embed_all()
