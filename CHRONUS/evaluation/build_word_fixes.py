"""
Build services/data/word_fixes.json: words glued together in the cleaned
transcripts ("pointat", "availableto", "capableof", where a line break was
dropped), mapped to their split form. Mix Method applies it when quoting
(services/mix_method.py clean_for_display), so quotes read normally without
re-embedding anything.

It also restores ligatures lost when the biographies' PDFs were extracted
("dierent" -> "different", "condent" -> "confident": the ff/fi glyph vanished).

A token is fixed only when it is not an English word itself (wordfreq
frequency 0). A lost ligature is tried first; otherwise it is split into two
common words, where any two-letter part must be a real two-letter word
("de", "re", "st" never count) and the two words must also appear side by
side somewhere else in the corpus ("difficult to" does; "die rent" doesn't).
Names and @handles/#tags are left alone.

    pip install wordfreq      # only needed to rebuild the list
    python -m evaluation.build_word_fixes
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UNITS = ROOT / "04-Memory-Units" / "elon_musk_memory_units.jsonl"
OUT = ROOT / "services" / "data" / "word_fixes.json"
TWO_LETTER = set("to of in is it at as an be by do go he if me my no on or so up us we am".split())
MIN_PART = 3.2  # wordfreq Zipf frequency: about 1.5 uses per million words


LIGATURES = ("ffi", "ffl", "ff", "fi", "fl")


def fix_for(word: str, zipf, bigrams: Counter) -> str | None:
    if zipf(word, "en") > 0:
        return None  # a real word ("notebook", "takeoff")
    for i in range(1, len(word)):
        for lig in LIGATURES:
            candidate = word[:i] + lig + word[i:]
            if zipf(candidate, "en") >= MIN_PART:
                return candidate
    split = split_for(word, zipf)
    return split if split and bigrams[split] > 0 else None


def split_for(word: str, zipf) -> str | None:
    best = None
    for k in range(2, len(word) - 1):
        a, b = word[:k], word[k:]
        if any(len(p) == 2 and p not in TWO_LETTER for p in (a, b)):
            continue
        score = min(zipf(a, "en"), zipf(b, "en"))
        if score >= MIN_PART and (best is None or score > best[0]):
            best = (score, f"{a} {b}")
    return best[1] if best else None


def main() -> None:
    try:
        from wordfreq import zipf_frequency
    except ImportError:
        sys.exit("pip install wordfreq first (only needed to rebuild this list)")
    counts: Counter = Counter()
    bigrams: Counter = Counter()
    with UNITS.open(encoding="utf-8") as f:
        for line in f:
            text = json.loads(line)["text"]
            # lowercase tokens only, not preceded by @ or # (handles, hashtags)
            counts.update(m.group(1) for m in re.finditer(r"(?<![@#\w])([a-z]{5,24})(?![\w@])", text))
            words = re.findall(r"[a-z']+", text.lower())
            bigrams.update(f"{a} {b}" for a, b in zip(words, words[1:]))
    fixes = {}
    for word in sorted(counts):
        fixed = fix_for(word, zipf_frequency, bigrams)
        if fixed:
            fixes[word] = fixed
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(fixes, indent=0, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{len(fixes)} glued words -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
