"""
ChromaDB collections that always save their search index.

By default Chroma writes a collection's HNSW index to disk only after 1,000
additions. Smaller collections (four of the seven figures, every typical
custom model) kept theirs in memory only, and when Chroma reloaded it,
queries failed with "Error creating hnsw segment reader: Nothing found on
disk" (seen on Marie Curie and Shakespeare). Collections are therefore
created with a sync threshold of 2, which saves the index after every add,
and older ones are switched over once at startup (ensure_saved).
"""

from __future__ import annotations

SYNC_THRESHOLD = 2
# batch_size (the in-memory buffer before items join the index) must not exceed it
COLLECTION_METADATA = {"hnsw:space": "cosine", "hnsw:sync_threshold": SYNC_THRESHOLD, "hnsw:batch_size": SYNC_THRESHOLD}


def ensure_saved(collection) -> bool:
    """Switch an older collection to save its index, and save it now.
    Returns True if it had to be changed."""
    hnsw = (getattr(collection, "configuration_json", None) or {}).get("hnsw") or {}
    if hnsw.get("sync_threshold", 1000) <= SYNC_THRESHOLD:
        return False
    collection.modify(configuration={"hnsw": {"sync_threshold": SYNC_THRESHOLD, "batch_size": SYNC_THRESHOLD}})
    # Re-saving one unchanged item makes Chroma write the whole index now
    item = collection.get(limit=1, include=["embeddings", "documents", "metadatas"])
    if item["ids"]:
        collection.upsert(ids=item["ids"], embeddings=[list(item["embeddings"][0])], documents=item["documents"],
                          metadatas=item["metadatas"])
    return True


def ensure_all_saved(client) -> int:
    """ensure_saved for every collection; returns how many were switched over."""
    changed = 0
    for listed in client.list_collections():
        name = getattr(listed, "name", listed)
        changed += ensure_saved(client.get_collection(name))
    return changed
