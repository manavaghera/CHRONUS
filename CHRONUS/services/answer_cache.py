"""
Answers to repeated questions, served from memory.

The quick-question buttons and the landing-page demo ask the same questions
over and over; retrieval and an LLM call each time is wasted. Answers are
kept for an hour, keyed on everything that shapes them (model, question,
mode, years, language, length). Follow-ups aren't cached: their answer
depends on the conversation. Any change to a model's memories or settings
(any write other than chatting) clears the whole cache, so a corrected
memory is never answered from a stale copy.

CHRONUS_ANSWER_CACHE=0 turns it off (the tests do).
"""

from __future__ import annotations

import os
import threading
import time
from collections import OrderedDict

MAX_ENTRIES = 256
TTL_SECONDS = 3600
# Writes that don't change what a model knows
_READ_LIKE = ("/chat", "/roundtable", "/feedback", "/speak", "/voice", "/transcribe", "/auth", "/jobs")

_lock = threading.Lock()
_entries: OrderedDict = OrderedDict()


def enabled() -> bool:
    return os.getenv("CHRONUS_ANSWER_CACHE", "1") != "0"


def key(*parts) -> tuple:
    return tuple(" ".join(str(p).lower().split()) if isinstance(p, str) else p for p in parts)


def get(k: tuple):
    if not enabled():
        return None
    with _lock:
        item = _entries.get(k)
        if item is None:
            return None
        stored, value = item
        if time.time() - stored > TTL_SECONDS:
            del _entries[k]
            return None
        _entries.move_to_end(k)
        return value


def put(k: tuple, value) -> None:
    if not enabled():
        return
    with _lock:
        _entries[k] = (time.time(), value)
        _entries.move_to_end(k)
        while len(_entries) > MAX_ENTRIES:
            _entries.popitem(last=False)


def clear() -> None:
    with _lock:
        _entries.clear()


def invalidates(method: str, path: str) -> bool:
    """Does this request change what some model knows?"""
    return method in ("POST", "PUT", "PATCH", "DELETE") and not path.startswith(_READ_LIKE)
