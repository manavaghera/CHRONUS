#!/usr/bin/env python3
"""
Embed interview protocol responses into the elon_musk ChromaDB collection.

Usage:
    cd CHRONUS
    python 06-Testing/embed_interview.py
"""

import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import chromadb

# WORKAROUND (same as embed_elon.py): pyarrow 24.0.0 access-violates when
# loaded AFTER chromadb + torch have initialized their native DLLs (which
# happens via sentence_transformers). Pre-loading pyarrow.dataset first
# fixes the import order and avoids the hard native crash.
import pyarrow.dataset  # noqa: F401  (must be imported before sentence_transformers)

from sentence_transformers import SentenceTransformer

from services.interview_embedder import embed_from_file

# Config
CHROMA_PATH = str(Path(__file__).parent.parent / "chroma_db")
COLLECTION_NAME = "elon_musk"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # Same model as api_server.py (BUG 7 sync)
INTERVIEW_FILE = str(Path(__file__).parent.parent / "models" / "elon_musk" / "interview_responses.json")


def main():
    print("CHRONUS Interview Response Embedder")
    print("=" * 50)

    # Load embedder
    print(f"\nLoading embedding model: {EMBEDDING_MODEL}")
    embedder = SentenceTransformer(EMBEDDING_MODEL, device="cpu")
    print("Model loaded.")

    # Connect to ChromaDB
    print(f"\nConnecting to ChromaDB: {CHROMA_PATH}")
    client = chromadb.PersistentClient(path=CHROMA_PATH)

    # Get or create collection (use existing, don't wipe!)
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"}
    )

    print(f"Collection: {COLLECTION_NAME} ({collection.count():,} existing memories)")

    # Embed interview responses
    print(f"\nEmbedding interview responses from: {INTERVIEW_FILE}")
    result = embed_from_file(INTERVIEW_FILE, collection, embedder, person="elon_musk")

    print(f"\nFinal collection size: {collection.count():,} memories")

    if result["success"]:
        print(f"\n[OK] Success: {result['embedded']} interview responses embedded")
        if result["errors"]:
            print(f"[WARN] Errors: {result['errors']}")
    else:
        print(f"\n[FAIL] Failed: {result.get('error', 'unknown')}")

    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
