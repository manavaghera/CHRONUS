"""
Memory browser: see exactly what a model knows, and (for custom models)
correct or remove it. Also the "view in context" lookup behind citations,
and the per-year counts behind time travel.

    GET    /personas/{id}/memories?q=&source=&offset=&limit=   list or search
    GET    /personas/{id}/memories/{memory_id}                  one memory + its context
    PATCH  /personas/{id}/memories/{memory_id}                  edit text (custom only, re-embedded)
    DELETE /personas/{id}/memories/{memory_id}                  delete (custom only)
    DELETE /personas/{id}/documents/{filename}                  remove an upload and its memories
    GET    /personas/{id}/timeline                              memories per year

Pretrained models are read-only: their memories come from published
sources, so nobody edits what Lincoln said.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from fastapi import Path as PathParam
from pydantic import BaseModel, Field

from services import personas as ps
from services import timeline
from services.provenance import format_source_citation, voice_of

PERSONA_PATH = PathParam(pattern=ps.PERSONA_ID_PATTERN)
MEMORY_PATH = PathParam(pattern=r"^[A-Za-z0-9_.:-]{1,80}$")
FILENAME_PATH = PathParam(min_length=1, max_length=200)

# Metadata never shown in lists (large, or internal)
_HIDDEN = {"parent_text"}


class MemoryEdit(BaseModel):
    text: str = Field(min_length=3, max_length=4000)


def _item(mid: str, doc: str, meta: dict, editable: bool, distance: float | None = None) -> dict:
    meta = meta or {}
    citation = format_source_citation(meta, doc, distance)
    return {
        "id": mid,
        "text": doc,
        "citation": citation["citation"],
        "voice": voice_of(meta),
        "source_file": meta.get("source_file", ""),
        "source_type": meta.get("source_type", ""),
        "date": meta.get("date", ""),
        "page": meta.get("page"),
        "question_id": meta.get("question_id"),
        "edited_at": meta.get("edited_at"),
        "distance": citation["distance"],
        "editable": editable,
    }


def make_router(client, embedder) -> APIRouter:
    router = APIRouter(prefix="/personas/{persona_id}", tags=["memories"])

    def _persona(persona_id: str) -> dict:
        persona = ps.load_persona(persona_id)
        if persona is None:
            raise HTTPException(status_code=404, detail=f"No model called '{persona_id}'")
        return persona

    def _custom(persona_id: str) -> dict:
        persona = _persona(persona_id)
        if persona["kind"] != "custom":
            raise HTTPException(status_code=403, detail="Pretrained models are read-only: their memories come from published sources")
        return persona

    @router.get("/memories")
    def list_memories(persona_id: str = PERSONA_PATH, q: str = Query("", max_length=300),
                      source: str = Query("", max_length=200), offset: int = Query(0, ge=0),
                      limit: int = Query(20, ge=1, le=100)):
        persona = _persona(persona_id)
        collection = ps.get_collection(client, persona)
        editable = persona["kind"] == "custom"
        where = {"source_file": source} if source else None
        if q.strip():
            # Semantic search, plus exact-phrase matches it might rank lower
            n = min(collection.count(), offset + limit)
            if n == 0:
                return {"total": 0, "items": [], "sources": []}
            emb = embedder.encode([q], normalize_embeddings=True).tolist()
            raw = collection.query(query_embeddings=emb, n_results=n, where=where)
            rows = list(zip(raw["ids"][0], raw["documents"][0], raw["metadatas"][0], raw["distances"][0]))
            items = [_item(mid, doc, meta, editable, dist) for mid, doc, meta, dist in rows[offset:offset + limit]]
            return {"total": len(rows), "items": items, "query": q}
        total = len(collection.get(where=where, include=[])["ids"]) if where else collection.count()
        page = collection.get(where=where, include=["documents", "metadatas"], limit=limit, offset=offset)
        items = [_item(mid, doc, meta, editable) for mid, doc, meta in zip(page["ids"], page["documents"], page["metadatas"])]
        return {"total": total, "items": items}

    @router.get("/memories/{memory_id}")
    def get_memory(persona_id: str = PERSONA_PATH, memory_id: str = MEMORY_PATH):
        """One memory, with the text around it: the paragraph it was cut from,
        or the neighbouring pages of the same book."""
        persona = _persona(persona_id)
        collection = ps.get_collection(client, persona)
        data = collection.get(ids=[memory_id], include=["documents", "metadatas"])
        if not data["ids"]:
            raise HTTPException(status_code=404, detail="No such memory")
        doc, meta = data["documents"][0], data["metadatas"][0] or {}
        context = None
        parent = meta.get("parent_text")
        if parent and len(parent) > len(doc) + 20:
            context = {"kind": "paragraph", "text": parent}
        elif meta.get("page") and meta.get("source_file"):
            page = int(meta["page"])
            near = collection.get(where={"$and": [{"source_file": meta["source_file"]},
                                                  {"page": {"$in": [page - 1, page + 1]}}]},
                                  include=["documents", "metadatas"], limit=4)
            pages = sorted(zip(near["documents"], near["metadatas"]), key=lambda x: (x[1] or {}).get("page", 0))
            if pages:
                context = {"kind": "pages", "pages": [{"page": (m or {}).get("page"), "text": d[:1200]} for d, m in pages]}
        item = _item(memory_id, doc, meta, persona["kind"] == "custom")
        item["metadata"] = {k: v for k, v in meta.items() if k not in _HIDDEN}
        item["context"] = context
        return item

    @router.patch("/memories/{memory_id}")
    def edit_memory(body: MemoryEdit, persona_id: str = PERSONA_PATH, memory_id: str = MEMORY_PATH):
        persona = _custom(persona_id)
        collection = ps.get_collection(client, persona)
        data = collection.get(ids=[memory_id], include=["metadatas"])
        if not data["ids"]:
            raise HTTPException(status_code=404, detail="No such memory")
        meta = dict(data["metadatas"][0] or {})
        meta["edited_at"] = datetime.now().isoformat(timespec="seconds")
        meta.pop("parent_text", None)  # the original paragraph no longer matches
        text = body.text.strip()
        collection.update(ids=[memory_id], documents=[text], metadatas=[meta],
                          embeddings=embedder.encode([text], normalize_embeddings=True).tolist())
        return _item(memory_id, text, meta, True)

    @router.delete("/memories/{memory_id}")
    def delete_memory(persona_id: str = PERSONA_PATH, memory_id: str = MEMORY_PATH):
        persona = _custom(persona_id)
        collection = ps.get_collection(client, persona)
        if not collection.get(ids=[memory_id], include=[])["ids"]:
            raise HTTPException(status_code=404, detail="No such memory")
        collection.delete(ids=[memory_id])
        return {"deleted": memory_id, "memories": collection.count()}

    @router.delete("/documents/{filename}")
    def delete_document(persona_id: str = PERSONA_PATH, filename: str = FILENAME_PATH):
        persona = _custom(persona_id)
        try:
            removed = ps.delete_document(persona, ps.get_collection(client, persona), filename)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"No upload called '{filename}'")
        return {"deleted": filename, "memories_removed": removed}

    @router.get("/timeline")
    def get_timeline(persona_id: str = PERSONA_PATH):
        return timeline.histogram(ps.get_collection(client, _persona(persona_id)))

    return router
