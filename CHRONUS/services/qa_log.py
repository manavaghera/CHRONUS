"""
Q&A log: one JSON line per answered question (qa_log.jsonl, gitignored).

Used for analytics (the /analytics page), the knowledge-gap report (questions
a model couldn't answer) and the feedback review queue. Entries for a custom
model quote its private memories, so deleting the model purges them too
(services/personas.py delete_custom_persona -> purge()).
"""

from __future__ import annotations

import json
import logging
import secrets
import threading
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("chronus")

# Next to the CHRONUS package, not the current working directory
QA_LOG_PATH = Path(__file__).resolve().parent.parent / "qa_log.jsonl"

_lock = threading.Lock()


def log_qa(query: str, answer: str, sources: list[dict], **details) -> str:
    """Append one answered question; returns its entry id (for feedback).

    *details*: persona, mode, confidence, faithfulness, latency_ms...
    """
    from services.personas import current_user

    entry_id = secrets.token_hex(6)
    user = current_user.get()
    if user:
        details.setdefault("user", user)  # accounts: only this person sees it in Insights
    entry = {
        "id": entry_id,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "query": query,
        "answer": answer[:500],
        "sources": [s.get("source_file", "unknown") for s in sources[:3]],
        **details,
    }
    with _lock, QA_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    logger.info(f"Logged Q&A: {query[:50]}...")
    return entry_id


def read_entries(persona: str | None = None, path: Path | None = None) -> list[dict]:
    """All logged entries (oldest first), optionally for one persona.

    Entries written before the persona field existed belong to Elon, the
    only model at the time. Malformed lines are skipped.
    """
    path = path or QA_LOG_PATH
    if not path.exists():
        return []
    entries = []
    with _lock:
        lines = path.read_text(encoding="utf-8").splitlines()
    for line in lines:
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(entry, dict):
            continue
        entry.setdefault("persona", "elon_musk")
        if persona is None or entry["persona"] == persona:
            entries.append(entry)
    return entries


def purge(persona: str, path: Path | None = None) -> int:
    """Remove every entry for *persona*; returns how many were removed."""
    path = path or QA_LOG_PATH
    if not path.exists():
        return 0
    with _lock:
        kept, removed = [], 0
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                owner = json.loads(line).get("persona", "elon_musk")
            except (json.JSONDecodeError, AttributeError):
                owner = None
            if owner == persona:
                removed += 1
            else:
                kept.append(line)
        if removed:
            tmp = path.with_suffix(".tmp")
            tmp.write_text("".join(f"{line}\n" for line in kept), encoding="utf-8")
            tmp.replace(path)
    return removed
