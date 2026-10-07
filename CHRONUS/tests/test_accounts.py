"""Accounts (CHRONUS_USERS): each person sees only the custom models they made."""

import pytest
from fastapi.testclient import TestClient

from services import qa_log


@pytest.fixture
def accounts(srv, monkeypatch, tmp_path):
    monkeypatch.setattr(srv.config, "USERS", "asha:mango-tree,ravi:blue-bicycle")
    monkeypatch.setattr(srv, "log_qa", qa_log.log_qa)
    monkeypatch.setattr(qa_log, "QA_LOG_PATH", tmp_path / "qa.jsonl")

    def sign_in(name, code):
        c = TestClient(srv.app, base_url="http://localhost")
        assert c.post("/auth/login", json={"user": name, "code": code}).status_code == 200
        return c
    return sign_in


def test_sign_in(srv, accounts):
    anon = TestClient(srv.app, base_url="http://localhost")
    assert anon.get("/personas").status_code == 401
    assert anon.get("/auth/status").json() == {"required": True, "signed_in": False, "accounts": True, "user": None}
    assert anon.post("/auth/login", json={"user": "asha", "code": "blue-bicycle"}).status_code == 401  # ravi's code
    assert anon.post("/auth/login", json={"user": "nobody", "code": "x"}).status_code == 401
    asha = accounts("Asha", "mango-tree")  # names are case-insensitive
    assert asha.get("/auth/status").json()["user"] == "asha"


def test_each_account_sees_only_its_own_models(srv, accounts):
    asha, ravi = accounts("asha", "mango-tree"), accounts("ravi", "blue-bicycle")
    pid = asha.post("/personas", json={"name": "pytest Asha's Nani", "relationship": "family", "consent": True}).json()["id"]
    try:
        assert pid in [p["id"] for p in asha.get("/personas").json()]
        assert pid not in [p["id"] for p in ravi.get("/personas").json()]
        assert "elon_musk" in [p["id"] for p in ravi.get("/personas").json()]  # pretrained models are shared
        assert ravi.get(f"/personas/{pid}").status_code == 404
        assert ravi.delete(f"/personas/{pid}").status_code == 404
        assert ravi.get(f"/personas/{pid}/memories").status_code == 404
        assert ravi.post("/chat", json={"query": "hello there", "persona": pid}).status_code == 404
    finally:
        assert asha.delete(f"/personas/{pid}").status_code == 200


def test_insights_are_per_account(srv, accounts):
    asha, ravi = accounts("asha", "mango-tree"), accounts("ravi", "blue-bicycle")
    asha.post("/chat", json={"query": "How do I descale a kettle?", "mode": "mix_method"})
    assert asha.get("/insights/analytics", params={"persona": "elon_musk"}).json()["total"] == 1
    assert ravi.get("/insights/analytics", params={"persona": "elon_musk"}).json()["total"] == 0
    assert ravi.get("/insights/gaps", params={"persona": "elon_musk"}).json()["unanswered"] == 0


def test_sign_in_rate_limit_cannot_be_bypassed(srv, accounts, monkeypatch):
    """Only failed attempts count, but once a client has failed 10 times in a
    minute every attempt is refused, a right code included; and signing in
    to your own account doesn't reset the count."""
    from fastapi.testclient import TestClient

    guesser = TestClient(srv.app, base_url="http://localhost")
    seen = []
    for i in range(20):
        if i % 5 == 4:  # the attacker's own valid login in between
            guesser.post("/auth/login", json={"user": "asha", "code": "mango-tree"})
        seen.append(guesser.post("/auth/login", json={"user": "ravi", "code": f"guess-{i}"}).status_code)
    assert seen[:10] == [401] * 10 and set(seen[10:]) == {429}
    right = guesser.post("/auth/login", json={"user": "ravi", "code": "blue-bicycle"})
    assert right.status_code == 429 and "chronus_access" not in right.cookies  # the right code learns nothing
    # successful sign-ins alone never use up the limit (test clients share one address)
    from services import access

    monkeypatch.setattr(access, "limiter", access._Limiter())
    for _ in range(15):
        accounts("asha", "mango-tree")
