"""
The website's public forms: join the waitlist, contact us, report a model.

    POST /site/waitlist  {email, name?, plan, people, country?, agree}
    POST /site/contact   {name, email, topic, message, agree}
    POST /site/report    {name, email, model, relationship, reason, details, truthful}

They work without signing in (services/access.py PUBLIC_PREFIXES), because
the people who use them don't have an account yet, or are reporting a model
someone else made. What protects them instead:
* the cross-site guard (services/access.py): other websites can't post here
* FORMS_PER_HOUR submissions per client address (off when rate limits are)
* a hidden "website" field people never see: a bot that fills it in gets a
  normal-looking answer and nothing is saved

Submissions are personal data, kept only on this server as JSON lines in
site_data/ (owner-only files, git-ignored), with no IP address. A waitlist
email is stored once. Export for whoever runs CHRONUS:

    python -m services.site_forms export waitlist > waitlist.csv
"""

from __future__ import annotations

import csv
import json
import secrets
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from services import access

DATA_DIR = Path(__file__).resolve().parent.parent / "site_data"
FORMS_PER_HOUR = 5
EMAIL = r"^[^@\s]{1,64}@[^@\s]{1,255}\.[^@\s]{2,}$"
_lock = threading.Lock()


class Waitlist(BaseModel):
    email: str = Field(max_length=320, pattern=EMAIL)
    name: str = Field(default="", max_length=80)
    plan: Literal["words", "voice", "legacy", "unsure"] = "unsure"
    people: int = Field(default=1, ge=1, le=50)
    country: str = Field(default="", max_length=60)
    agree: bool  # may we email them about the launch
    website: str = Field(default="", max_length=200)  # spam trap: people never see it


class Contact(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    email: str = Field(max_length=320, pattern=EMAIL)
    topic: Literal["general", "partnership", "press", "support", "privacy"] = "general"
    message: str = Field(min_length=10, max_length=4000)
    agree: bool  # may we use these details to reply
    website: str = Field(default="", max_length=200)


class Report(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    email: str = Field(max_length=320, pattern=EMAIL)
    model: str = Field(min_length=2, max_length=300)  # the model's name or link
    relationship: Literal["me", "family", "representative", "other"]
    reason: Literal["no_consent", "deceased_no_agreement", "impersonation", "harmful", "other"]
    details: str = Field(min_length=10, max_length=4000)
    truthful: bool  # the reporter confirms it is true to the best of their knowledge
    website: str = Field(default="", max_length=200)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _path(kind: str) -> Path:
    return DATA_DIR / f"{kind}.jsonl"


def read(kind: str) -> list[dict]:
    path = _path(kind)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _save(kind: str, entry: dict) -> None:
    with _lock:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with _path(kind).open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _check(request: Request) -> None:
    """Per-address limit on submissions (off when rate limits are)."""
    if access._rate_limit() <= 0:
        return
    client = request.client.host if request.client else "unknown"
    if not access.limiter.allow(f"forms:{client}", FORMS_PER_HOUR, window=3600):
        raise HTTPException(status_code=429, detail="Too many submissions from here; please try again in an hour",
                            headers={"Retry-After": "3600"})


def _fields(body: BaseModel) -> dict:
    data = body.model_dump(exclude={"website"})
    return {k: v.strip() if isinstance(v, str) else v for k, v in data.items()}


def make_router() -> APIRouter:
    router = APIRouter(prefix="/site", tags=["website forms"])

    @router.post("/waitlist", status_code=201)
    def join_waitlist(body: Waitlist, request: Request):
        if not body.agree:
            raise HTTPException(status_code=422, detail="Please agree to be emailed about the launch")
        _check(request)
        if body.website:  # a bot filled in the trap: say yes, keep nothing
            return {"joined": True}
        entry = {**_fields(body), "email": body.email.strip().lower(), "at": _now()}
        with _lock:
            known = any(row["email"] == entry["email"] for row in read("waitlist"))
        if not known:
            _save("waitlist", entry)
        return {"joined": True, "already": known}

    @router.post("/contact", status_code=201)
    def contact(body: Contact, request: Request):
        if not body.agree:
            raise HTTPException(status_code=422, detail="Please agree to us using these details to reply")
        _check(request)
        if not body.website:
            _save("contact", {**_fields(body), "email": body.email.strip().lower(), "at": _now()})
        return {"sent": True}

    @router.post("/report", status_code=201)
    def report(body: Report, request: Request):
        if not body.truthful:
            raise HTTPException(status_code=422, detail="Please confirm the report is true to the best of your knowledge")
        _check(request)
        reference = "R-" + secrets.token_hex(4).upper()
        if not body.website:
            _save("report", {**_fields(body), "email": body.email.strip().lower(), "reference": reference,
                             "status": "new", "at": _now()})
        return {"reference": reference}

    return router


def export(kind: str, out=None) -> int:
    """Write one form's submissions as CSV (to stdout by default); returns how many."""
    rows = read(kind)
    if rows:
        writer = csv.DictWriter(out or sys.stdout, fieldnames=list(dict.fromkeys(k for row in rows for k in row)))
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "export" or sys.argv[2] not in ("waitlist", "contact", "report"):
        sys.exit("usage: python -m services.site_forms export waitlist|contact|report")
    print(f"{export(sys.argv[2])} rows", file=sys.stderr)
