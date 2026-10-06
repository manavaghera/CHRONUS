"""
Q&A log: one JSON line per answered question (qa_log.jsonl, gitignored).

Used for analytics (the /analytics page), the knowledge-gap report (questions
a model couldn't answer) and the feedback review queue. Entries for a custom
model quote its private memories, so deleting the model purges them too
(services/personas.py delete_custom_persona -> purge()).

Retention: entries older than config.LOG_RETENTION_DAYS (default 90) are
deleted, checked at most once an hour (prune_if_due). Logs registered with
retain() (the feedback log) are pruned the same way. People can delete
their own history at any time (forget(), DELETE /history).
"""

from __future__ import annotations

import json
import logging
import secrets
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

logger = logging.getLogger("chronus")

# Next to the CHRONUS package, not the current working directory
QA_LOG_PATH = Path(__file__).resolve().parent.parent / "qa_log.jsonl"

_lock = threading.Lock()
_PRUNE_EVERY = 3600  # seconds
_last_prune = 0.0
# Other logs kept for the same time: (path getter, the lock their writers hold)
_retained: list[tuple[Callable[[], Path], threading.Lock]] = []


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
    prune_if_due()
    with _lock, QA_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    logger.info(f"Logged Q&A: {query[:50]}...")
    return entry_id


def read_entries(persona: str | None = None, path: Path | None = None) -> list[dict]:
    """All logged entries (oldest first), optionally for one persona.

    Entries written before the persona field existed belong to Elon, the
    only model at the time. Malformed lines are skipped.
    """
    if path is None:
        prune_if_due()
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


def rewrite(path: Path, drop: Callable[[dict], bool], lock: threading.Lock | None = None) -> int:
    """Remove the JSON lines of *path* for which drop(entry) is true; returns
    how many were removed. Unreadable lines are kept (nothing to judge them by)."""
    if not path.exists():
        return 0
    with lock or _lock:
        kept, removed = [], 0
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                entry = None
            if isinstance(entry, dict) and drop(entry):
                removed += 1
            else:
                kept.append(line)
        if removed:
            tmp = path.with_suffix(".tmp")
            tmp.write_text("".join(f"{line}\n" for line in kept), encoding="utf-8")
            tmp.replace(path)
    return removed


def purge(persona: str, path: Path | None = None) -> int:
    """Remove every entry for *persona*; returns how many were removed."""
    return rewrite(path or QA_LOG_PATH, lambda e: e.get("persona", "elon_musk") == persona)


def forget(user: str | None, persona: str | None = None, path: Path | None = None,
           lock: threading.Lock | None = None) -> int:
    """Delete one person's entries (all of them, or for one model).

    *user* None means no accounts: everything on this server is the one
    person's. With accounts, only entries they made; ones logged before
    accounts were turned on belong to no one and stay until they expire.
    """
    def mine(e: dict) -> bool:
        return (user is None or e.get("user") == user) and (persona is None or e.get("persona", "elon_musk") == persona)
    return rewrite(path or QA_LOG_PATH, mine, lock)


def _older_than(days: int, now: datetime | None = None) -> Callable[[dict], bool]:
    cutoff = (now or datetime.now()) - timedelta(days=days)

    def old(e: dict) -> bool:
        try:
            return datetime.fromisoformat(str(e.get("timestamp", ""))) < cutoff
        except ValueError:
            return False  # no readable date: keep
    return old


def prune(days: int, path: Path | None = None, lock: threading.Lock | None = None,
          now: datetime | None = None) -> int:
    """Delete entries older than *days* (0 or less keeps everything)."""
    if days <= 0:
        return 0
    return rewrite(path or QA_LOG_PATH, _older_than(days, now), lock)


def retain(path: Callable[[], Path], lock: threading.Lock) -> None:
    """Prune another log (e.g. feedback) on the same schedule."""
    _retained.append((path, lock))


def prune_if_due() -> int:
    """Apply LOG_RETENTION_DAYS to every log, at most once an hour.

    Takes each log's lock, so never call it while holding one of them."""
    global _last_prune
    if _last_prune and time.monotonic() - _last_prune < _PRUNE_EVERY:
        return 0
    _last_prune = time.monotonic()
    from config import config

    days = config.LOG_RETENTION_DAYS
    removed = prune(days)
    for path, lock in _retained:
        removed += prune(days, path(), lock)
    if removed:
        logger.info(f"Deleted {removed} log entries older than {days} days")
    return removed
