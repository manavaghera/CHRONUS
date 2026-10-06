"""Request guards (services/access.py), the Q&A log (services/qa_log.py) and
the bug fixes around them."""

import json

import pytest
from fastapi.testclient import TestClient

from services import access, qa_log


def test_unknown_host_names_are_refused(srv):
    # DNS rebinding: evil.example resolving to 127.0.0.1 must not be served
    rebound = TestClient(srv.app, base_url="http://evil.example")
    assert rebound.get("/health").status_code == 400
    assert rebound.get("/personas").status_code == 400


@pytest.mark.parametrize("headers", [
    {"origin": "https://evil.example"}, {"origin": "null"}, {"sec-fetch-site": "cross-site"},
])
def test_cross_site_writes_are_refused(client, headers):
    # /build has no body, so a plain cross-site form post used to reach it
    assert client.post("/personas/elon_musk/build", headers=headers).status_code == 403
    assert client.post("/chat", json={"query": "Why Mars?"}, headers=headers).status_code == 403


def test_same_site_and_dev_proxy_writes_are_allowed(client):
    r = client.post("/chat", json={"query": "hey"}, headers={"origin": "http://localhost:3000", "sec-fetch-site": "same-origin"})
    assert r.status_code == 200


def test_access_code(srv, client, monkeypatch):
    monkeypatch.setattr(srv.config, "ACCESS_CODE", "open sesame")
    assert client.get("/health").status_code == 200  # public, so the site can tell it's online
    r = client.get("/personas")
    assert r.status_code == 401 and r.json()["login"] is True
    assert client.get("/auth/status").json() == {"required": True, "signed_in": False, "accounts": False, "user": None}
    assert client.post("/auth/login", json={"code": "wrong"}).status_code == 401
    fresh = TestClient(srv.app, base_url="http://localhost")
    assert fresh.post("/auth/login", json={"code": "open sesame"}).status_code == 200
    assert "open sesame" not in fresh.cookies.get(access.COOKIE)  # only a hash is stored
    assert fresh.get("/personas").status_code == 200
    fresh.post("/auth/logout")
    assert fresh.get("/personas").status_code == 401


def test_rate_limit(client, monkeypatch):
    monkeypatch.setenv("CHRONUS_RATE_LIMIT", "2")
    monkeypatch.setattr(access, "limiter", access._Limiter())
    codes = [client.post("/chat", json={"query": "hey"}).status_code for _ in range(3)]
    assert codes == [200, 200, 429]
    assert client.get("/personas").status_code == 200  # cheap reads aren't limited


def test_fallbacks_are_logged(srv, client, monkeypatch):
    logged = []
    monkeypatch.setattr(srv, "log_qa", lambda *a, **k: logged.append((a, k)) or "abc123")
    d = client.post("/chat", json={"query": "How do I descale a kettle?", "mode": "mix_method"}).json()
    assert d["fallback"] is True and d["id"] == "abc123"
    [(args, details)] = logged
    assert args[0] == "How do I descale a kettle?" and details["mode"] == "fallback" and details["persona"] == "elon_musk"


def test_mixed_question_answers_both_parts(srv, client):
    basic = srv.check_basic_info("When were you born and why did you start SpaceX?", "elon_musk")
    assert basic["remainder"] == "why did you start spacex"
    assert srv.check_basic_info("Which year were you born, and where?", "elon_musk")["remainder"] == ""
    assert srv.check_basic_info("Where did you go to college and what did you study there?", "elon_musk")["remainder"] == ""
    d = client.post("/chat", json={"query": "When were you born and why did you start SpaceX?", "mode": "mix_method"}).json()
    first, _, rest = d["answer"].partition("\n\n")
    assert "1971" in first and rest  # the SpaceX half is answered (or honestly refused), not dropped


def test_persona_threshold_of_zero_is_respected(srv):
    memory = srv.client.get_or_create_collection("pytest_threshold", metadata={"hnsw:space": "cosine"})
    try:
        text = "My father bought me a blue bicycle for my eighteenth birthday and I rode it every morning."
        memory.add(ids=["t1"], documents=[text], embeddings=srv.embedder.encode([text], normalize_embeddings=True).tolist(),
                   metadatas=[{"source_type": "personal_writing"}])
        question = "Tell me about the bicycle your father bought you for your birthday"
        assert srv.retrieve(question, memory=memory, threshold=1.5) is not None
        assert srv.retrieve(question, memory=memory, threshold=0.0) is None  # used to fall back to the global 0.58
    finally:
        srv.client.delete_collection("pytest_threshold")


def test_qa_log_purge(tmp_path):
    path = tmp_path / "qa_log.jsonl"
    path.write_text("\n".join([
        json.dumps({"query": "old entry, before personas", "answer": "x"}),
        json.dumps({"query": "private", "answer": "Amma's letter", "persona": "amma_123abc"}),
        "not json",
        json.dumps({"query": "keep", "answer": "y", "persona": "albert_einstein"}),
    ]) + "\n", encoding="utf-8")
    assert qa_log.purge("amma_123abc", path) == 1
    assert "Amma" not in path.read_text(encoding="utf-8")
    assert [e["query"] for e in qa_log.read_entries(path=path)] == ["old entry, before personas", "keep"]
    assert [e["persona"] for e in qa_log.read_entries(path=path)] == ["elon_musk", "albert_einstein"]


def test_deleting_a_model_purges_its_log_entries(client, monkeypatch, tmp_path):
    monkeypatch.setattr(qa_log, "QA_LOG_PATH", tmp_path / "qa_log.jsonl")
    r = client.post("/personas", json={"name": "pytest Log purge", "relationship": "self", "consent": True})
    pid = r.json()["id"]
    qa_log.log_qa("What did you cook?", "Dal for twelve people.", [], persona=pid)
    qa_log.log_qa("Why Mars?", "Because.", [], persona="elon_musk")
    assert client.delete(f"/personas/{pid}").status_code == 200
    assert [e["persona"] for e in qa_log.read_entries()] == ["elon_musk"]
