"""
CHRONUS - Shared memory-store helpers.

BUG 10 FIX: extracted from api_server.py so lightweight scripts (chat_elon.py)
can write Q&A memories WITHOUT importing api_server, which loads FastAPI, a
~90MB SentenceTransformer, and a ChromaDB PersistentClient at module level.
Nothing heavy is imported here — callers inject their already-loaded embedder
and collection, so shared resources are never loaded twice.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from typing import Any

import chromadb
from sentence_transformers import SentenceTransformer

logger = logging.getLogger("chronus.memory_store")


def add_to_memory(
    query: str,
    answer: str,
    sources: list[dict],
    embedder: SentenceTransformer,
    collection: chromadb.Collection,
) -> bool:
    """Add a new Q&A pair as a memory unit in ChromaDB.

    BUG 10 FIX: extracted from api_server.py for reuse by chat_elon.py without
    the double-loading cost. `embedder` and `collection` are injected by the
    caller (whoever loaded them first) — this module never creates its own.

    This is real auto-training — future queries will retrieve this as evidence.
    """
    qa_text = f"Q: {query}\nA: {answer}"
    qa_emb = embedder.encode([qa_text], normalize_embeddings=True).tolist()
    qa_id = "qa_" + hashlib.md5(qa_text.encode()).hexdigest()[:12]

    source_names = [s.get("source_file", "unknown") for s in sources[:3]]
    qa_metadata: dict[str, Any] = {
        "source_file": "auto_trained_qa",
        "source_type": "auto_trained",
        "source_name": "Past conversation",
        "topic": "auto_trained",
        "date": datetime.now().isoformat(),
        "importance_score": 3,
        "person": "elon_musk",
        "original_sources": ", ".join(source_names),
        "query": query[:200],
    }

    try:
        collection.add(
            embeddings=qa_emb,
            documents=[qa_text],
            metadatas=[qa_metadata],
            ids=[qa_id],
        )
        logger.info(f"Auto-trained: {qa_id} ({collection.count():,} total units)")
        return True
    except Exception as e:
        logger.error(f"Auto-train failed: {e}")
        return False
