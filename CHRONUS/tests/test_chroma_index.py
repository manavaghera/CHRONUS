"""Small collections save their search index (services/chroma_index.py): it
used to live only in memory below 1,000 items, and reloading it failed with
"Nothing found on disk" (Marie Curie, Shakespeare)."""

import subprocess
import sys
from pathlib import Path

import chromadb

from services import chroma_index


def _saved(path: Path, collection) -> bool:
    import sqlite3

    db = sqlite3.connect(f"file:{path / 'chroma.sqlite3'}?mode=ro", uri=True)
    try:
        [(segment,)] = db.execute("select id from segments where collection = ? and scope = 'VECTOR'",
                                  (str(collection.id),)).fetchall()
    finally:
        db.close()
    return (path / segment / "index_metadata.pickle").exists()


def test_new_and_old_collections_save_their_index(tmp_path):
    client = chromadb.PersistentClient(path=str(tmp_path))
    items = {"ids": ["a", "b", "c"], "embeddings": [[1.0, 0, 0], [0, 1.0, 0], [0, 0, 1.0]], "documents": ["a", "b", "c"]}
    new = client.create_collection("small_new", metadata=chroma_index.COLLECTION_METADATA)
    new.add(**items)
    old = client.create_collection("small_old", metadata={"hnsw:space": "cosine"})  # how they used to be made
    old.add(**items)
    assert _saved(tmp_path, new) and not _saved(tmp_path, old)
    # The switch-over runs when the server starts, in a fresh process (as here)
    code = ("import chromadb; from services import chroma_index as c\n"
            f"client = chromadb.PersistentClient(path={str(tmp_path)!r})\n"
            "print(c.ensure_all_saved(client), c.ensure_all_saved(client))")
    out = subprocess.run([sys.executable, "-c", code], cwd=Path(chroma_index.__file__).parent.parent,
                         capture_output=True, text=True, timeout=300)
    assert out.stdout.split() == ["1", "0"], out.stderr  # only the old one needed it; then idempotent
    assert _saved(tmp_path, old) and old.count() == 3
