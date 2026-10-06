"""
Shared fixtures. Tests run against the real api_server module with every
LLM call mocked, so they cost no API quota.

Two setups, picked automatically:
* full: the real embedding model and Elon's real collection (chroma_db/)
  are available. Everything runs.
* sample: a fresh clone or CI, where chroma_db/ (gitignored) is missing or
  the model can't be downloaded. A throwaway database and a deterministic
  word-hash embedder (services/embedder.py HashEmbedder) are used, and tests
  marked `corpus` (they need real embeddings on Elon's archive) are skipped.
  Force it with CHRONUS_TEST_SAMPLE=1.

They must never change real data: `guard_real_data` fails the run if Elon's
collection size changes or a test persona is left behind (an earlier ad-hoc
check once deleted a real interview answer).
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest import mock

import httpx
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "06-Testing"))
os.chdir(ROOT)
os.environ.setdefault("CHRONUS_RATE_LIMIT", "0")  # tests send many requests a minute
os.environ.setdefault("CHRONUS_ANSWER_CACHE", "0")  # each test sees fresh answers (test_data_features.py turns it on)

TEST_PERSONA_PREFIX = "pytest "  # names of personas created by tests


def _full_setup_available() -> bool:
    if os.getenv("CHRONUS_TEST_SAMPLE") == "1":
        return False
    try:
        import chromadb
        import sentence_transformers  # noqa: F401

        from config import config
        return chromadb.PersistentClient(path=config.CHROMA_PATH).get_collection(config.COLLECTION_NAME).count() > 0
    except Exception:
        return False


FULL = _full_setup_available()
if not FULL:
    os.environ["CHRONUS_CHROMA_PATH"] = tempfile.mkdtemp(prefix="chronus_test_db_")


def pytest_configure(config):
    config.addinivalue_line("markers", "corpus: needs the real embedding model and Elon's full collection")


def pytest_collection_modifyitems(config, items):
    if FULL:
        return
    skip = pytest.mark.skip(reason="needs the real embedding model + chroma_db (sample setup; see tests/conftest.py)")
    for item in items:
        if "corpus" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def srv():
    import api_server  # connects to ChromaDB once per run; the embedder loads on first use
    if not FULL:
        from services.embedder import HashEmbedder
        api_server.embedder._model = HashEmbedder()
    return api_server


@pytest.fixture(scope="session")
def client(srv):
    from fastapi.testclient import TestClient
    return TestClient(srv.app, base_url="http://localhost")  # an allowed host (config.ALLOWED_HOSTS)


@pytest.fixture(autouse=True)
def no_qa_log(srv, monkeypatch):
    monkeypatch.setattr(srv, "log_qa", lambda *a, **k: None)


@pytest.fixture(scope="session", autouse=True)
def guard_real_data(srv):
    before = srv.collection.count()
    yield
    assert srv.collection.count() == before, "tests changed Elon's memory collection"
    leftovers = [c.name for c in srv.client.list_collections() if c.name.startswith("persona_pytest_")]
    assert not leftovers, f"test personas left behind: {leftovers}"


class FakeFish:
    """Stands in for the Fish Audio API (services/tts.py) for the whole run,
    so no test can send a recording or text to the real service."""

    def __init__(self):
        self.requests, self.fail, self.voices_made = [], {}, 0

    def reset(self):
        self.requests.clear()
        self.fail.clear()  # {"POST": 402} makes every POST fail with 402

    def handler(self, request):
        request.read()
        self.requests.append(request)
        if request.method in self.fail:
            return httpx.Response(self.fail[request.method], json={"status": self.fail[request.method], "message": "fake"})
        if request.method == "POST" and request.url.path == "/model":
            self.voices_made += 1
            return httpx.Response(201, json={"_id": f"fishvoice{self.voices_made:08d}", "state": "trained"})
        if request.method == "POST" and request.url.path == "/v1/tts":
            return httpx.Response(200, content=b"ID3 fake mp3", headers={"content-type": "audio/mpeg"})
        if request.method == "DELETE" and request.url.path.startswith("/model/"):
            return httpx.Response(200)
        return httpx.Response(404)


@pytest.fixture(scope="session", autouse=True)
def _fish_for_session():
    from services import tts
    fish = FakeFish()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(tts, "_TRANSPORT", httpx.MockTransport(fish.handler))
        mp.setenv("FISH_API_KEY", "test-key-not-real")
        yield fish


@pytest.fixture(autouse=True)
def fake_fish(_fish_for_session):
    from services import tts
    _fish_for_session.reset()
    tts.fish_speech.cache_clear()
    return _fish_for_session


@pytest.fixture
def fake_llm():
    """Patch the natural-mode LLM call. Usage: with fake_llm(content=..., finish=..., status=...) as post: ..."""
    import services.natural_mode as nm

    def make(content=None, finish="stop", status=200):
        resp = mock.Mock(status_code=status)
        if status >= 400:
            resp.raise_for_status.side_effect = nm.requests.HTTPError(f"{status} error")
        resp.json.return_value = {"choices": [{"message": {"content": content}, "finish_reason": finish}]}
        patches = [
            mock.patch.object(nm.config, "LLM_PROVIDER", "openrouter"),
            mock.patch.object(nm.config, "OPENAI_API_KEY", "test-key"),
            mock.patch.object(nm.requests, "post", return_value=resp),
        ]
        return _Stack(patches)

    return make


class _Stack:
    """Enter several patches together; yields the requests.post mock."""

    def __init__(self, patches):
        self.patches = patches

    def __enter__(self):
        return [p.__enter__() for p in self.patches][-1]

    def __exit__(self, *exc):
        for p in reversed(self.patches):
            p.__exit__(*exc)
