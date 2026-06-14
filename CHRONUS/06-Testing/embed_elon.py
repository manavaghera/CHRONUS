#!/usr/bin/env python3
"""
CHRONUS - ChromaDB embedding pipeline for Elon Musk memory units.

Reads the JSONL memory-unit file, upserts documents into a persistent local
ChromaDB collection, and relies on Chroma's embedding function for both ingest
and query-time embeddings.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import chromadb


VAULT_ROOT = Path(__file__).resolve().parent.parent
MEMORY_FILE = VAULT_ROOT / "04-Memory-Units" / "elon_musk_memory_units.jsonl"
CHROMA_PATH = VAULT_ROOT / "chroma_db"
COLLECTION_NAME = "elon_musk"
BATCH_SIZE = 200


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
    """Project a memory unit into Chroma-safe metadata."""
    metadata = {
        "source_file": record.get("source_file", ""),
        "source_type": record.get("source_type", ""),
        "source_name": record.get("source_name", ""),
        "date": record.get("date", ""),
        "topic": record.get("topic", ""),
        "importance_score": record.get("importance_score", 1),
        "word_count": record.get("word_count", 0),
        "char_count": record.get("char_count", 0),
        "memory_id": record.get("memory_id", ""),
        "person": record.get("person", ""),
    }
    return {key: sanitize_value(value) for key, value in metadata.items()}


def build_ids(records: list[dict[str, Any]], start_index: int) -> list[str]:
    """Create stable IDs for Chroma upserts."""
    ids: list[str] = []
    for offset, record in enumerate(records):
        memory_id = str(record.get("memory_id") or "").strip()
        row_index = start_index + offset
        if memory_id:
            ids.append(f"{memory_id}_{row_index}")
        else:
            ids.append(f"elon_memory_{row_index}")
    return ids


def get_collection() -> chromadb.Collection:
    """Wipe and recreate for a clean build."""
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    try:
        client.delete_collection("elon_musk")
        print("Deleted old collection")
    except Exception as e:
        print(f"No old collection to delete: {e}")

    collection = client.create_collection(
        name="elon_musk",
        metadata={"hnsw:space": "cosine"},
    )
    return collection


def embed_all() -> None:
    """Upsert every memory unit into the local ChromaDB collection."""
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

        collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )

        end = start + len(batch)
        print(f"Upserted {end:,} / {len(records):,}")

    print()
    print(f"Done. Collection '{COLLECTION_NAME}' now has {collection.count():,} items.")


if __name__ == "__main__":
    embed_all()
