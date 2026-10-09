"""
The person model's own endpoints: identity profile, style layer, switches.

    GET  /personas/{id}/identity                 profile, rebuilt first if the archive changed
    POST /personas/{id}/identity/rebuild         personal models
    PUT  /personas/{id}/identity/lines/{line}    {"hidden": bool}; personal models
    GET  /personas/{id}/style                    adapter in use, past runs and exams, what's needed next
    POST /personas/{id}/style/train              start a run now; personal models, when ready
    PUT  /personas/{id}/person-settings          {"learn_style", "allow_spirit", "frozen"}; personal models

The switches are consent decisions (training on someone's words; answers
they never gave), so each change is kept in the model's consent history.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi import Path as PathParam
from pydantic import BaseModel

from services import identity, style
from services import personas as ps

PERSONA_PATH = PathParam(pattern=ps.PERSONA_ID_PATTERN)
LINE_PATH = PathParam(pattern=r"^[0-9a-f]{10}$")


class LineUpdate(BaseModel):
    hidden: bool


class PersonSettings(BaseModel):
    learn_style: Optional[bool] = None
    allow_spirit: Optional[bool] = None
    frozen: Optional[bool] = None


def view(built: dict) -> dict:
    """The profile as the model page shows it: sections in order, hidden flags."""
    hidden = set(built.get("hidden", []))
    headings = {"about": "About", **{key: heading for key, (heading, _, _) in identity.SECTIONS.items()}}
    return {
        "built_at": built.get("built_at", ""),
        "sections": [[key, heading] for key, heading in headings.items()],
        "lines": [{**{k: v for k, v in line.items() if k != "score"}, "hidden": line["id"] in hidden}
                  for line in built.get("lines", [])],
    }


def make_router(client, embedder) -> APIRouter:
    router = APIRouter(prefix="/personas/{persona_id}", tags=["person model"])

    def _persona(persona_id: str) -> dict:
        persona = ps.load_persona(persona_id)
        if persona is None:
            raise HTTPException(status_code=404, detail=f"No model called '{persona_id}'")
        return persona

    def _custom(persona_id: str) -> dict:
        persona = _persona(persona_id)
        if persona["kind"] != "custom":
            raise HTTPException(status_code=403, detail="Pretrained models can't be changed")
        return persona

    @router.get("/identity")
    def get_identity(persona_id: str = PERSONA_PATH):
        persona = _persona(persona_id)
        return view(identity.get(persona, ps.get_collection(client, persona), embedder))

    @router.post("/identity/rebuild")
    def rebuild_identity(persona_id: str = PERSONA_PATH):
        persona = _custom(persona_id)
        return view(identity.build(persona, ps.get_collection(client, persona), embedder))

    @router.put("/identity/lines/{line_id}")
    def hide_line(body: LineUpdate, persona_id: str = PERSONA_PATH, line_id: str = LINE_PATH):
        persona = _custom(persona_id)
        identity.get(persona, ps.get_collection(client, persona), embedder)  # current before changing it
        try:
            return view(identity.set_hidden(persona, line_id, body.hidden))
        except KeyError:
            raise HTTPException(status_code=404, detail="No such line in this profile")

    @router.get("/style")
    def get_style(persona_id: str = PERSONA_PATH):
        persona = _persona(persona_id)
        return style.status(persona, ps.get_collection(client, persona))

    @router.post("/style/train", status_code=202)
    def train_now(persona_id: str = PERSONA_PATH):
        persona = _custom(persona_id)
        collection = ps.get_collection(client, persona)
        state = style.status(persona, collection)
        if state["run"] and state["run"].get("state") == "running":
            raise HTTPException(status_code=409, detail="A training run is already going")
        if not state["ready"]:
            raise HTTPException(status_code=409, detail=state["reason"])
        style.start(persona)
        return style.status(persona, collection)

    @router.put("/person-settings")
    def change_settings(body: PersonSettings, persona_id: str = PERSONA_PATH):
        persona = _custom(persona_id)
        change = {k: v for k, v in body.model_dump().items() if v is not None}
        if not change:
            raise HTTPException(status_code=422, detail="Nothing to change")
        fresh = ps.record_consent_change(persona["id"], change)
        return style.settings(fresh)

    return router
