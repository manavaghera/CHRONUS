"""
Personas — the people CHRONUS can simulate.

* Pretrained personas ship with the repo: models/<id>/persona.json (Elon Musk).
* Custom personas are built by users through the "Create your model" flow
  (consent -> upload documents -> structured interview -> build) and live in
  personas/<id>/ — git-ignored, because they hold private personal data.

Every persona has its own ChromaDB collection, so one person's memories can
never surface in another person's answers, and deleting a custom persona
removes its vectors, uploads and record in one step (the paper's deletion
requirement).
"""

from __future__ import annotations

import hashlib
import json
import re
import secrets
import shutil
import threading
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRETRAINED_DIR = ROOT / "models"
CUSTOM_DIR = ROOT / "personas"

PERSONA_ID_PATTERN = r"^[a-z0-9_]{3,48}$"
UPLOAD_TYPES = {".txt", ".md", ".pdf", ".csv", ".json"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
# Data sufficiency check before a custom model can be built (paper, Input
# Data Layer): with fewer memories it can barely answer anything.
MIN_MEMORIES_TO_BUILD = 10
EMBED_BATCH = 64

DEFAULT_STYLE_NOTES = (
    "Talk like a person in a conversation, not like an essay: plain words and "
    "concrete details instead of big abstract phrases."
)

# persona.json files are read-modify-written from concurrent requests
_lock = threading.Lock()


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _folder(persona: dict) -> Path:
    base = PRETRAINED_DIR if persona["kind"] == "pretrained" else CUSTOM_DIR
    return base / persona["id"]


def load_persona(persona_id: str) -> dict | None:
    if not re.match(PERSONA_ID_PATTERN, persona_id or ""):
        return None
    for base in (PRETRAINED_DIR, CUSTOM_DIR):
        path = base / persona_id / "persona.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    return None


def list_personas() -> list[dict]:
    found = []
    for base in (PRETRAINED_DIR, CUSTOM_DIR):
        for path in sorted(base.glob("*/persona.json")) if base.exists() else []:
            found.append(json.loads(path.read_text(encoding="utf-8")))
    return found


def save_persona(persona: dict) -> None:
    folder = _folder(persona)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "persona.json").write_text(json.dumps(persona, indent=2, ensure_ascii=False), encoding="utf-8")


def create_custom_persona(
    name: str, description: str, relationship: str, allow_cloud_llm: bool, consent_statement: str,
) -> dict:
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:30] or "persona"
    persona_id = f"{slug}_{secrets.token_hex(3)}"
    persona = {
        "id": persona_id,
        "name": name.strip(),
        "kind": "custom",
        "status": "draft",
        "description": description.strip(),
        "collection": f"persona_{persona_id}",
        # Off by default: AI voice sends evidence excerpts to the cloud LLM
        # provider, and the paper's privacy model is local-first.
        "allow_cloud_llm": allow_cloud_llm,
        "style_notes": DEFAULT_STYLE_NOTES,
        "relationship": relationship,  # creator's relationship to the person
        "consent": {"statement": consent_statement, "given_at": _now()},
        "created_at": _now(),
        "uploads": [],
        "interview_answered": [],
    }
    with _lock:
        save_persona(persona)
    return persona


def get_collection(client, persona: dict):
    return client.get_or_create_collection(name=persona["collection"], metadata={"hnsw:space": "cosine"})


def _safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._ -]", "_", Path(name).name).strip(" .")[:80]
    return cleaned or "upload.txt"


def _sanitize(value):
    """Chroma metadata only accepts str/int/float/bool."""
    if value is None:
        return ""
    return value if isinstance(value, (str, int, float, bool)) else str(value)


def ingest_document(persona: dict, collection, embedder, filename: str, data: bytes, authored_by: str) -> dict:
    """Parse, chunk and embed one uploaded document into the persona's memory.

    Re-uploading a file with the same name replaces its earlier memories.
    Raises ValueError for unsupported, oversized or empty files.
    """
    import merge_sources  # parsers + chunker; deferred so importing this module stays cheap

    name = _safe_filename(filename)
    ext = Path(name).suffix.lower()
    if ext not in UPLOAD_TYPES:
        raise ValueError(f"Unsupported file type '{ext or name}'. Use: {', '.join(sorted(UPLOAD_TYPES))}")
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError(f"File is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB")

    uploads = CUSTOM_DIR / persona["id"] / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    path = uploads / name
    path.write_bytes(data)

    if ext in (".txt", ".md"):
        records = merge_sources.parse_markdown(path)
    elif ext == ".csv":
        records = merge_sources.parse_csv_file(path)
    elif ext == ".json":
        records = merge_sources.parse_json_file(path)
    else:
        records = merge_sources.parse_pdf_file(str(path))

    # Their own writing (letters, journals, emails) is first-person evidence;
    # anything written about them is third-party (services/provenance.py).
    source_type = "personal_writing" if authored_by == "self" else "written_about"
    units = []
    for record in records:
        record.update(source_type=source_type, source_name=Path(name).stem, source_file=name)
        units.extend(merge_sources.chunk_record(record))
    units = [u for u in units if len(u["text"].strip()) >= 20]
    if not units:
        path.unlink(missing_ok=True)
        raise ValueError("No readable text found in this file")

    collection.delete(where={"source_file": name})  # replace an earlier upload of this file
    ids, docs, metas = [], [], []
    for i, unit in enumerate(units):
        memory_id = "cu_" + hashlib.md5(f"{name}|{i}|{unit['text']}".encode("utf-8")).hexdigest()[:16]
        meta = {k: _sanitize(v) for k, v in unit.items() if k not in ("text", "char_count", "word_count")}
        meta.update(memory_id=memory_id, person=persona["id"], authored_by=authored_by,
                    importance_score=merge_sources.estimate_importance(unit))
        ids.append(memory_id)
        docs.append(unit["text"])
        metas.append(meta)
    for start in range(0, len(docs), EMBED_BATCH):
        batch = slice(start, start + EMBED_BATCH)
        vectors = embedder.encode(docs[batch], normalize_embeddings=True).tolist()
        collection.upsert(ids=ids[batch], documents=docs[batch], metadatas=metas[batch], embeddings=vectors)

    entry = {"filename": name, "authored_by": authored_by, "memories": len(docs), "uploaded_at": _now()}
    with _lock:
        fresh = load_persona(persona["id"]) or persona
        fresh["uploads"] = [u for u in fresh.get("uploads", []) if u["filename"] != name] + [entry]
        save_persona(fresh)
    return entry


def record_interview_answer(persona: dict, question_id: str) -> None:
    with _lock:
        fresh = load_persona(persona["id"]) or persona
        if question_id not in fresh.setdefault("interview_answered", []):
            fresh["interview_answered"].append(question_id)
            save_persona(fresh)


def build_persona(collection, persona: dict) -> dict:
    """Mark a custom persona ready after the data sufficiency check.

    Memories are embedded as they are added, so "building" is the gate that
    makes the model available for chat, not a long training job.
    """
    count = collection.count()
    if count < MIN_MEMORIES_TO_BUILD:
        raise ValueError(
            f"Only {count} memories so far; at least {MIN_MEMORIES_TO_BUILD} are needed. "
            "Upload more documents or answer more interview questions."
        )
    with _lock:
        fresh = load_persona(persona["id"]) or persona
        fresh.update(status="ready", built_at=_now())
        save_persona(fresh)
    return fresh


def delete_custom_persona(client, persona: dict) -> None:
    """Permanently delete a custom persona: vectors, uploads and record."""
    if persona.get("kind") != "custom":
        raise PermissionError("Only custom models can be deleted")
    try:
        client.delete_collection(persona["collection"])
    except Exception:
        pass  # never had any memories
    folder = (CUSTOM_DIR / persona["id"]).resolve()
    if folder.parent == CUSTOM_DIR.resolve() and folder.exists():
        shutil.rmtree(folder)
