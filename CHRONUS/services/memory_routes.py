"""
Memory browser: see exactly what a model knows, and (for custom models)
correct or remove it. Also the "view in context" lookup behind citations,
and the per-year counts behind time travel.

    GET    /personas/{id}/memories?q=&source=&offset=&limit=   list or search
    GET    /personas/{id}/memories/{memory_id}                  one memory + its context
    PATCH  /personas/{id}/memories/{memory_id}                  edit text (custom only, re-embedded)
    PUT    /personas/{id}/memories/{memory_id}/never-quote      {"never_quote": true} (custom only)
    GET    /personas/{id}/memories/{memory_id}/history          every version, the original first
    POST   /personas/{id}/memories/{memory_id}/restore          {"seq": n}: back to the version change n replaced
    GET    /personas/{id}/history                               recent changes, deleted memories, log check

Custom models keep a tamper-evident history of every change
(services/memory_history.py), so an edit never destroys the original words.
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

from services import memory_history, timeline
from services import personas as ps
from services.provenance import format_source_citation, voice_of

PERSONA_PATH = PathParam(pattern=ps.PERSONA_ID_PATTERN)
MEMORY_PATH = PathParam(pattern=r"^[A-Za-z0-9_.:-]{1,80}$")
FILENAME_PATH = PathParam(min_length=1, max_length=200)

# Metadata never shown in lists (large, or internal)
_HIDDEN = {"parent_text"}


class MemoryEdit(BaseModel):
    text: str = Field(min_length=3, max_length=4000)


class NeverQuote(BaseModel):
    never_quote: bool


class Restore(BaseModel):
    seq: int = Field(ge=1)


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
        "never_quote": bool(meta.get("never_quote")),
        "original": citation["original"],  # the voice note or photo it came from (services/originals.py)
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
        data = collection.get(ids=[memory_id], include=["documents", "metadatas"])
        if not data["ids"]:
            raise HTTPException(status_code=404, detail="No such memory")
        before = {"text": data["documents"][0], "metadata": dict(data["metadatas"][0] or {})}
        meta = dict(data["metadatas"][0] or {})
        meta["edited_at"] = datetime.now().isoformat(timespec="seconds")
        meta.pop("parent_text", None)  # the original paragraph no longer matches
        text = body.text.strip()
        collection.update(ids=[memory_id], documents=[text], metadatas=[meta],
                          embeddings=embedder.encode([text], normalize_embeddings=True).tolist())
        memory_history.record(persona, memory_id, "edit", before, {"text": text, "metadata": meta})
        return _item(memory_id, text, meta, True)

    @router.put("/memories/{memory_id}/never-quote")
    def set_never_quote(body: NeverQuote, persona_id: str = PERSONA_PATH, memory_id: str = MEMORY_PATH):
        """Keep a memory in the archive but never quote it (services/consent.py)."""
        persona = _custom(persona_id)
        collection = ps.get_collection(client, persona)
        data = collection.get(ids=[memory_id], include=["documents", "metadatas"])
        if not data["ids"]:
            raise HTTPException(status_code=404, detail="No such memory")
        before = {"text": data["documents"][0], "metadata": dict(data["metadatas"][0] or {})}
        meta = dict(data["metadatas"][0] or {})
        meta["never_quote"] = body.never_quote
        collection.update(ids=[memory_id], metadatas=[meta])
        memory_history.record(persona, memory_id, "never_quote", before, {"text": data["documents"][0], "metadata": meta})
        return _item(memory_id, data["documents"][0], meta, True)

    @router.delete("/memories/{memory_id}")
    def delete_memory(persona_id: str = PERSONA_PATH, memory_id: str = MEMORY_PATH):
        persona = _custom(persona_id)
        collection = ps.get_collection(client, persona)
        data = collection.get(ids=[memory_id], include=["documents", "metadatas"])
        if not data["ids"]:
            raise HTTPException(status_code=404, detail="No such memory")
        collection.delete(ids=[memory_id])
        memory_history.record(persona, memory_id, "delete",
                              {"text": data["documents"][0], "metadata": dict(data["metadatas"][0] or {})}, None)
        return {"deleted": memory_id, "memories": collection.count()}

    @router.delete("/documents/{filename}")
    def delete_document(persona_id: str = PERSONA_PATH, filename: str = FILENAME_PATH):
        persona = _custom(persona_id)
        collection = ps.get_collection(client, persona)
        gone = collection.get(where={"source_file": filename}, include=["documents", "metadatas"])
        try:
            removed = ps.delete_document(persona, collection, filename)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"No upload called '{filename}'")
        for mid, doc, meta in zip(gone["ids"], gone["documents"], gone["metadatas"]):
            memory_history.record(persona, mid, "delete", {"text": doc, "metadata": dict(meta or {})}, None)
        return {"deleted": filename, "memories_removed": removed}

    @router.get("/memories/{memory_id}/history")
    def memory_versions(persona_id: str = PERSONA_PATH, memory_id: str = MEMORY_PATH):
        """Every version of a memory, the original first ("view original")."""
        persona = _custom(persona_id)
        data = ps.get_collection(client, persona).get(ids=[memory_id], include=["documents", "metadatas"])
        current = {"text": data["documents"][0], "metadata": data["metadatas"][0] or {}} if data["ids"] else None
        found = memory_history.versions(persona, memory_id, current)
        if not found:
            raise HTTPException(status_code=404, detail="No such memory")
        return {"versions": found, "log": memory_history.verify(persona)}

    @router.post("/memories/{memory_id}/restore")
    def restore_memory(body: Restore, persona_id: str = PERSONA_PATH, memory_id: str = MEMORY_PATH):
        """Bring back the version that change *seq* replaced (also undoes a delete)."""
        persona = _custom(persona_id)
        change = memory_history.find(persona, body.seq)
        if change is None or change["memory_id"] != memory_id or change["before"] is None:
            raise HTTPException(status_code=404, detail="No such version of this memory")
        collection = ps.get_collection(client, persona)
        text, meta = change["before"]["text"], dict(change["before"].get("metadata") or {})
        meta["restored_at"] = datetime.now().isoformat(timespec="seconds")
        data = collection.get(ids=[memory_id], include=["documents", "metadatas"])
        current = {"text": data["documents"][0], "metadata": dict(data["metadatas"][0] or {})} if data["ids"] else None
        collection.upsert(ids=[memory_id], documents=[text], metadatas=[meta],
                          embeddings=embedder.encode([text], normalize_embeddings=True).tolist())
        memory_history.record(persona, memory_id, "restore", current, {"text": text, "metadata": meta})
        return _item(memory_id, text, meta, True)

    @router.get("/history")
    def history(persona_id: str = PERSONA_PATH, limit: int = Query(50, ge=1, le=500)):
        """Recent changes, memories deleted (and restorable), and whether the log is intact."""
        persona = _custom(persona_id)
        log = memory_history.entries(persona)
        existing = set(ps.get_collection(client, persona).get(include=[])["ids"])
        recent = [{"seq": e["seq"], "at": e["at"], "memory_id": e["memory_id"], "action": e["action"],
                   "text": ((e["after"] or e["before"]) or {}).get("text", "")[:200]} for e in log[-limit:][::-1]]
        return {"recent": recent, "deleted": memory_history.deleted(persona, existing), "log": memory_history.verify(persona)}

    @router.get("/about")
    def about(persona_id: str = PERSONA_PATH):
        """What this model is made of: memories by voice and source, date
        range, its "I don't know" threshold, and (custom models) consent."""
        from collections import Counter

        from config import config

        persona = _persona(persona_id)
        collection = ps.get_collection(client, persona)
        voices, types, files = Counter(), Counter(), Counter()
        offset = 0
        while True:
            page = collection.get(include=["metadatas"], limit=2000, offset=offset)
            if not page["ids"]:
                break
            for meta in page["metadatas"]:
                meta = meta or {}
                voices[voice_of(meta)] += 1
                types[meta.get("source_type", "unknown")] += 1
                files[meta.get("source_file", "unknown")] += 1
            offset += 2000
        years = timeline.histogram(collection)
        dated = [int(y) for y in years["years"]]
        out = {
            "id": persona["id"], "name": persona["name"], "kind": persona["kind"],
            "description": persona.get("description", ""), "memories": collection.count(),
            "by_voice": dict(voices), "by_type": dict(types.most_common()),
            "top_sources": [{"source_file": f, "memories": n} for f, n in files.most_common(8)],
            "years": {"first": min(dated), "last": max(dated)} if dated else None,
            "threshold": persona.get("distance_threshold", config.DISTANCE_THRESHOLD),
            "sources": persona.get("sources", []), "license": persona.get("license", ""),
            "memorial": bool(persona.get("memorial")),
        }
        if persona["kind"] == "custom":
            out.update(consent_given_at=(persona.get("consent") or {}).get("given_at", ""),
                       consent_statement=(persona.get("consent") or {}).get("statement", ""),
                       created_at=persona.get("created_at", ""), built_at=persona.get("built_at", ""),
                       allow_cloud_llm=bool(persona.get("allow_cloud_llm")))
        return out

    @router.get("/timeline")
    def get_timeline(persona_id: str = PERSONA_PATH):
        return timeline.histogram(ps.get_collection(client, _persona(persona_id)))

    return router
