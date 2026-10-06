"""
Okapi BM25 keyword retrieval: the baseline the CHRONUS paper compares
semantic retrieval against (Table IV). Self-contained, no extra dependency.
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict

# Standard English stopwords; BM25 baselines conventionally drop them
_STOPWORDS = frozenset(
    "a an and are as at be been but by can could did do does for from had has have he her his i if in into is it "
    "its just me my no not of on or our she so than that the their them then there these they this to up us was "
    "we were what when where which who why will with would you your".split()
)


def tokenize(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9']+", text.lower()) if w not in _STOPWORDS and len(w) > 1]


class BM25:
    def __init__(self, documents: list[str], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.term_freqs = [Counter(tokenize(d)) for d in documents]
        self.lengths = [sum(tf.values()) for tf in self.term_freqs]
        self.avg_length = sum(self.lengths) / max(len(self.lengths), 1)
        self.postings: dict[str, list[int]] = defaultdict(list)
        for i, tf in enumerate(self.term_freqs):
            for term in tf:
                self.postings[term].append(i)
        n = len(documents)
        self.idf = {t: math.log((n - len(ids) + 0.5) / (len(ids) + 0.5) + 1) for t, ids in self.postings.items()}

    def top(self, query: str, k: int = 10) -> list[tuple[int, float]]:
        """[(document index, score)] for the k best-scoring documents."""
        scores: dict[int, float] = defaultdict(float)
        for term in set(tokenize(query)):
            idf = self.idf.get(term)
            if idf is None:
                continue
            for i in self.postings[term]:
                tf = self.term_freqs[i][term]
                norm = tf + self.k1 * (1 - self.b + self.b * self.lengths[i] / self.avg_length)
                scores[i] += idf * tf * (self.k1 + 1) / norm
        return sorted(scores.items(), key=lambda kv: -kv[1])[:k]
