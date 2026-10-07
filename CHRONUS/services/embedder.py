"""
The sentence embedder, loaded on first use.

Importing api_server used to load the ~90 MB SentenceTransformer (and torch)
straight away, so even `python -c "import api_server"` or a test that never
embeds anything paid for it. LazyEmbedder has the same .encode() but loads
the model the first time it is called.

Tests and CI swap in HashEmbedder (no download, deterministic) when the real
model isn't available; see tests/conftest.py.
"""

from __future__ import annotations

import hashlib
import re
import threading

import numpy as np


class LazyEmbedder:
    def __init__(self, model_name: str, device: str = "cpu"):
        self.model_name = model_name
        self.device = device
        self._model = None
        self._lock = threading.Lock()

    @property
    def model(self):
        if self._model is None:
            with self._lock:
                if self._model is None:
                    # pyarrow must be imported before sentence_transformers on
                    # Windows (native crash otherwise; see requirements.txt)
                    try:
                        import pyarrow.dataset  # noqa: F401
                    except ImportError:
                        pass
                    from sentence_transformers import SentenceTransformer
                    self._model = SentenceTransformer(self.model_name, device=self.device)
        return self._model

    def encode(self, texts, **kwargs):
        return self.model.encode(texts, **kwargs)

    @property
    def loaded(self) -> bool:
        return self._model is not None


class HashEmbedder:
    """Deterministic bag-of-words embedder for tests: texts sharing words get
    similar vectors, so retrieval behaves sensibly on a tiny corpus."""

    def __init__(self, dim: int = 384):
        self.dim = dim

    def encode(self, texts, normalize_embeddings: bool = True, **_):
        single = isinstance(texts, str)
        rows = []
        for text in [texts] if single else texts:
            vec = np.zeros(self.dim, dtype=np.float32)
            for word in re.findall(r"[a-z0-9']+", str(text).lower()):
                h = int(hashlib.md5(word.encode()).hexdigest(), 16)
                vec[h % self.dim] += 1.0 if (h >> 64) & 1 else -1.0
            if normalize_embeddings:
                norm = np.linalg.norm(vec)
                vec = vec / norm if norm else vec
            rows.append(vec)
        out = np.stack(rows)
        return out[0] if single else out
