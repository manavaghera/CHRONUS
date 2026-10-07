"""
Encrypted export / import of a custom model: one ".chronus" file to back it
up or move it to another computer.

The file is a zip (manifest, persona record with its consent, memories with
their embeddings, uploaded files, voice recording) encrypted with
AES-256-GCM under a key derived from the user's password with scrypt. Without
the password the file is unreadable, and any tampering is detected.

A cloned voice is not carried over: its Fish Audio id belongs to the
exporting account. The recording is, so the voice can be made again.

    POST /personas/{id}/export   {password}            -> .chronus file
    POST /personas/import        {content_base64, password}
"""

from __future__ import annotations

import base64
import binascii
import io
import json
import os
import re
import zipfile
from datetime import datetime

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from fastapi import APIRouter, HTTPException
from fastapi import Path as PathParam
from fastapi.responses import Response
from pydantic import BaseModel, Field

from services import personas as ps

MAGIC = b"CHRONUS1"
FORMAT = "chronus-model"
VERSION = 1
MAX_BUNDLE_BYTES = 60 * 1024 * 1024
MAX_UNZIPPED_BYTES = 250 * 1024 * 1024
PERSONA_PATH = PathParam(pattern=ps.PERSONA_ID_PATTERN)
_ALLOWED = re.compile(r"^(manifest\.json|persona\.json|memories\.jsonl|voice/reference\.wav|uploads/[A-Za-z0-9._ -]{1,80})$")


class ExportIn(BaseModel):
    password: str = Field(min_length=8, max_length=200)


class ImportIn(BaseModel):
    content_base64: str = Field(min_length=1, max_length=MAX_BUNDLE_BYTES * 4 // 3 + 16)
    password: str = Field(min_length=8, max_length=200)


def _key(password: str, salt: bytes) -> bytes:
    return Scrypt(salt=salt, length=32, n=2**15, r=8, p=1).derive(password.encode("utf-8"))


def encrypt(data: bytes, password: str) -> bytes:
    salt, nonce = os.urandom(16), os.urandom(12)
    return MAGIC + salt + nonce + AESGCM(_key(password, salt)).encrypt(nonce, data, MAGIC)


def decrypt(blob: bytes, password: str) -> bytes:
    if not blob.startswith(MAGIC) or len(blob) < len(MAGIC) + 28 + 16:
        raise ValueError("This isn't a CHRONUS model file")
    salt, nonce = blob[8:24], blob[24:36]
    try:
        return AESGCM(_key(password, salt)).decrypt(nonce, blob[36:], MAGIC)
    except InvalidTag:
        raise ValueError("Wrong password, or the file is damaged")


def export_bundle(persona: dict, collection, embedding_model: str) -> bytes:
    """The zip (before encryption) for a custom persona."""
    folder = ps.CUSTOM_DIR / persona["id"]
    record = json.loads(json.dumps(persona))
    if record.get("voice"):
        record["voice"].pop("fish_voice_id", None)  # account-specific; the recording travels instead
    data = collection.get(include=["documents", "metadatas", "embeddings"])
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps({
            "format": FORMAT, "version": VERSION, "exported_at": datetime.now().isoformat(timespec="seconds"),
            "embedding_model": embedding_model, "memories": len(data["ids"]), "name": persona["name"],
        }, indent=2))
        z.writestr("persona.json", json.dumps(record, indent=2, ensure_ascii=False))
        lines = []
        for mid, doc, meta, emb in zip(data["ids"], data["documents"], data["metadatas"], data["embeddings"]):
            lines.append(json.dumps({"id": mid, "document": doc, "metadata": meta or {},
                                     "embedding": [round(float(x), 6) for x in emb]}, ensure_ascii=False))
        z.writestr("memories.jsonl", "\n".join(lines))
        uploads = folder / "uploads"
        if uploads.exists():
            for f in sorted(uploads.iterdir()):
                if f.is_file():
                    z.write(f, f"uploads/{f.name}")
        voice = folder / "voice" / "reference.wav"
        if voice.exists():
            z.write(voice, "voice/reference.wav")
    return buf.getvalue()


def import_bundle(raw_zip: bytes, client, embedder, embedding_model: str) -> dict:
    """Create a new custom persona from a decrypted bundle; returns it."""
    try:
        z = zipfile.ZipFile(io.BytesIO(raw_zip))
    except zipfile.BadZipFile:
        raise ValueError("The model file is damaged")
    names = z.namelist()
    if any(not _ALLOWED.match(n) for n in names) or "manifest.json" not in names or "persona.json" not in names:
        raise ValueError("This isn't a CHRONUS model file")
    if sum(i.file_size for i in z.infolist()) > MAX_UNZIPPED_BYTES:
        raise ValueError("The model file is too large")
    manifest = json.loads(z.read("manifest.json"))
    if manifest.get("format") != FORMAT or manifest.get("version", 0) > VERSION:
        raise ValueError("This model file is from a newer or different program")
    source = json.loads(z.read("persona.json"))

    persona = ps.create_custom_persona(
        str(source.get("name", "Imported model"))[:60], str(source.get("description", ""))[:300],
        source.get("relationship", "other") if source.get("relationship") in ("self", "family", "friend", "colleague", "other") else "other",
        bool(source.get("allow_cloud_llm")), (source.get("consent") or {}).get("statement", ""),
    )
    try:
        return _restore(persona, source, manifest, z, names, client, embedder, embedding_model)
    except Exception:
        ps.delete_custom_persona(client, persona)  # never leave half an import behind
        raise


def _restore(persona, source, manifest, z, names, client, embedder, embedding_model) -> dict:
    # Keep the original consent record and history, under the new id
    for key in ("consent", "style_notes", "uploads", "interview_answered", "followups_answered", "distance_threshold",
                "memorial", "created_at", "status", "built_at"):
        if key in source:
            persona[key] = source[key]
    persona["imported_at"] = datetime.now().isoformat(timespec="seconds")

    collection = ps.get_collection(client, persona)
    rows = [json.loads(line) for line in z.read("memories.jsonl").decode("utf-8").splitlines() if line.strip()] \
        if "memories.jsonl" in names else []
    reuse = manifest.get("embedding_model") == embedding_model
    for start in range(0, len(rows), ps.EMBED_BATCH):
        batch = rows[start:start + ps.EMBED_BATCH]
        docs = [str(r["document"]) for r in batch]
        metas = [{k: ps._sanitize(v) for k, v in (r.get("metadata") or {}).items()} | {"person": persona["id"]} for r in batch]
        embeddings = [r["embedding"] for r in batch] if reuse else embedder.encode(docs, normalize_embeddings=True).tolist()
        collection.upsert(ids=[str(r["id"]) for r in batch], documents=docs, metadatas=metas, embeddings=embeddings)

    folder = ps.CUSTOM_DIR / persona["id"]
    for name in names:
        if name.startswith("uploads/"):
            target = folder / "uploads" / ps._safe_filename(name.split("/", 1)[1])
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(z.read(name))
    if "voice/reference.wav" in names:
        (folder / "voice").mkdir(parents=True, exist_ok=True)
        (folder / "voice" / "reference.wav").write_bytes(z.read("voice/reference.wav"))
        persona["voice_sample_available"] = True  # re-make the cloud voice from it
    persona.pop("voice", None)
    if persona.get("status") == "ready" and collection.count() < ps.MIN_MEMORIES_TO_BUILD:
        persona["status"] = "draft"
    ps.save_persona(persona)
    return persona


def make_router(client, embedder, embedding_model: str, summarize) -> APIRouter:
    router = APIRouter(prefix="/personas", tags=["personas"])

    @router.post("/{persona_id}/export")
    def export(body: ExportIn, persona_id: str = PERSONA_PATH):
        persona = ps.load_persona(persona_id)
        if persona is None:
            raise HTTPException(status_code=404, detail=f"No model called '{persona_id}'")
        if persona["kind"] != "custom":
            raise HTTPException(status_code=403, detail="Only your own models can be exported")
        blob = encrypt(export_bundle(persona, ps.get_collection(client, persona), embedding_model), body.password)
        slug = re.sub(r"[^a-z0-9]+", "-", persona["name"].lower()).strip("-") or "model"
        return Response(content=blob, media_type="application/octet-stream",
                        headers={"Content-Disposition": f'attachment; filename="{slug}.chronus"'})

    @router.post("/import", status_code=201)
    def import_model(body: ImportIn):
        try:
            blob = base64.b64decode(body.content_base64, validate=True)
        except (binascii.Error, ValueError):
            raise HTTPException(status_code=400, detail="File content is not valid base64")
        try:
            persona = import_bundle(decrypt(blob, body.password), client, embedder, embedding_model)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except (KeyError, json.JSONDecodeError, UnicodeDecodeError):
            raise HTTPException(status_code=400, detail="The model file is damaged")
        return summarize(persona, ps.get_collection(client, persona))

    return router

