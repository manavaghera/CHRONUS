"""
Memory history with undo, for custom models.

Editing a memory used to destroy the original words for good. Every change
to a custom model's memories (edit, delete, restore, never-quote) is now
appended to personas/<id>/history.jsonl with the memory as it was before and
after. Each entry carries the hash of the one before it, so changing or
removing a past entry breaks the chain and verify() reports where (a
tamper-evident log: it shows that history was altered, it can't stop
someone with access to the files from rewriting all of it).

The log holds private words like the memories themselves: it lives in the
model's folder and is deleted with the model.
"""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime
from pathlib import Path

from services import personas as ps

_lock = threading.Lock()
GENESIS = "0" * 64


def _path(persona: dict) -> Path:
    return ps.CUSTOM_DIR / persona["id"] / "history.jsonl"


def _digest(entry: dict) -> str:
    body = {k: v for k, v in entry.items() if k != "hash"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def entries(persona: dict) -> list[dict]:
    path = _path(persona)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def record(persona: dict, memory_id: str, action: str, before: dict | None, after: dict | None) -> dict:
    """Append one change. *before*/*after*: {"text", "metadata"} or None."""
    with _lock:
        log = entries(persona)
        entry = {"seq": len(log) + 1, "at": datetime.now().isoformat(timespec="seconds"), "memory_id": memory_id,
                 "action": action, "before": before, "after": after, "prev": log[-1]["hash"] if log else GENESIS}
        entry["hash"] = _digest(entry)
        path = _path(persona)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def verify(persona: dict) -> dict:
    """{"ok", "entries", "broken_at"}: is every entry unchanged and in its place?"""
    prev = GENESIS
    log = entries(persona)
    for entry in log:
        if entry.get("prev") != prev or entry.get("hash") != _digest(entry):
            return {"ok": False, "entries": len(log), "broken_at": entry.get("seq")}
        prev = entry["hash"]
    return {"ok": True, "entries": len(log), "broken_at": None}


def versions(persona: dict, memory_id: str, current: dict | None) -> list[dict]:
    """Every version of one memory, oldest (the original) first.

    [{"version", "text", "metadata", "at", "action", "seq", "current"}]; *seq* is
    the change that replaced it (restore uses it). *current*: the memory now,
    or None if it is deleted.
    """
    changes = [e for e in entries(persona) if e["memory_id"] == memory_id]
    out = []
    for change in changes:
        if change["before"] is not None:
            out.append({"text": change["before"]["text"], "metadata": change["before"].get("metadata", {}),
                        "replaced_at": change["at"], "replaced_by": change["action"], "seq": change["seq"]})
    if current is not None:
        out.append({"text": current["text"], "metadata": current.get("metadata", {}), "replaced_at": None,
                    "replaced_by": None, "seq": None})
    for i, version in enumerate(out, start=1):
        version.update(version=i, current=version["seq"] is None)
    return out


def deleted(persona: dict, existing_ids: set[str]) -> list[dict]:
    """Memories deleted and not restored since: [{"memory_id", "text", "deleted_at", "seq"}]."""
    last: dict[str, dict] = {}
    for entry in entries(persona):
        last[entry["memory_id"]] = entry
    return [{"memory_id": mid, "text": e["before"]["text"], "deleted_at": e["at"], "seq": e["seq"]}
            for mid, e in last.items() if e["action"] == "delete" and mid not in existing_ids and e["before"]]


def find(persona: dict, seq: int) -> dict | None:
    return next((e for e in entries(persona) if e["seq"] == seq), None)
