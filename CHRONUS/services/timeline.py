"""
Time travel: answer as the persona was in a range of years.

Memories carry a "date" string ("2018-06-09" or "unknown"). ChromaDB can't
range-filter strings, so a numeric "year" field is added to dated memories
the first time a collection is used with a year range (additive and
idempotent: only metadata changes, never the text or embeddings). New
uploads get it straight away (services/personas.py).
"""

from __future__ import annotations

import re
import threading
from collections import Counter

_YEAR = re.compile(r"^\s*(1[0-9]{3}|20[0-9]{2})")
_lock = threading.Lock()
_ready: dict[str, int] = {}       # collection name -> count when year-tagged
_histograms: dict[str, tuple[int, dict]] = {}

BATCH = 500


def year_of(date) -> int | None:
    match = _YEAR.match(str(date or ""))
    return int(match.group(1)) if match else None


def ensure_year_metadata(collection) -> None:
    """Give every dated memory a numeric "year" field (once per collection size)."""
    count = collection.count()
    if _ready.get(collection.name) == count:
        return
    with _lock:
        if _ready.get(collection.name) == count:
            return
        offset = 0
        while True:
            page = collection.get(include=["metadatas"], limit=BATCH, offset=offset)
            if not page["ids"]:
                break
            ids, metas = [], []
            for mid, meta in zip(page["ids"], page["metadatas"]):
                meta = dict(meta or {})
                year = year_of(meta.get("date"))
                if year is not None and meta.get("year") != year:
                    meta["year"] = year
                    ids.append(mid)
                    metas.append(meta)
            if ids:
                collection.update(ids=ids, metadatas=metas)
            offset += BATCH
        _ready[collection.name] = count


def year_filter(year_from: int | None, year_to: int | None) -> dict | None:
    """ChromaDB where-clause for a year range (None when no range is set)."""
    parts = []
    if year_from is not None:
        parts.append({"year": {"$gte": year_from}})
    if year_to is not None:
        parts.append({"year": {"$lte": year_to}})
    if not parts:
        return None
    return parts[0] if len(parts) == 1 else {"$and": parts}


def combine(*clauses: dict | None) -> dict | None:
    parts = [c for c in clauses if c]
    if not parts:
        return None
    return parts[0] if len(parts) == 1 else {"$and": parts}


def histogram(collection) -> dict:
    """{"years": {year: count}, "dated": n, "undated": n} (cached by size)."""
    count = collection.count()
    cached = _histograms.get(collection.name)
    if cached and cached[0] == count:
        return cached[1]
    years: Counter = Counter()
    undated = 0
    offset = 0
    while True:
        page = collection.get(include=["metadatas"], limit=2000, offset=offset)
        if not page["ids"]:
            break
        for meta in page["metadatas"]:
            year = year_of((meta or {}).get("date"))
            if year is None:
                undated += 1
            else:
                years[year] += 1
        offset += 2000
    result = {"years": dict(sorted(years.items())), "dated": sum(years.values()), "undated": undated}
    _histograms[collection.name] = (count, result)
    return result
