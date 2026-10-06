"""Q&A log retention and "delete my history" (services/qa_log.py, DELETE /history)."""

import json
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from services import insights, qa_log


@pytest.fixture
def logs(srv, monkeypatch, tmp_path):
    monkeypatch.setattr(qa_log, "QA_LOG_PATH", tmp_path / "qa_log.jsonl")
    monkeypatch.setattr(insights, "FEEDBACK_PATH", tmp_path / "feedback.jsonl")
    monkeypatch.setattr(srv, "log_qa", qa_log.log_qa)
    return tmp_path


def _write(path, entries):
    path.write_text("".join(json.dumps(e) + "\n" for e in entries) + "not json\n", encoding="utf-8")


def _ids(path):
    return [json.loads(line)["id"] for line in path.read_text(encoding="utf-8").splitlines() if line.startswith("{")]


def test_old_entries_expire_from_both_logs(srv, logs, monkeypatch):
    now = datetime.now()
    old, recent = (now - timedelta(days=100)).isoformat(timespec="seconds"), (now - timedelta(days=3)).isoformat(timespec="seconds")
    _write(logs / "qa_log.jsonl", [{"id": "a", "timestamp": old}, {"id": "b", "timestamp": recent}, {"id": "c", "timestamp": "?"}])
    _write(logs / "feedback.jsonl", [{"id": "f1", "timestamp": old}, {"id": "f2", "timestamp": recent}])
    monkeypatch.setattr(srv.config, "LOG_RETENTION_DAYS", 90)
    monkeypatch.setattr(qa_log, "_last_prune", 0.0)

    assert qa_log.prune_if_due() == 2
    assert _ids(logs / "qa_log.jsonl") == ["b", "c"]  # no readable date: kept
    assert _ids(logs / "feedback.jsonl") == ["f2"]
    assert "not json" in (logs / "qa_log.jsonl").read_text()  # unreadable lines aren't judged
    assert qa_log.prune_if_due() == 0  # at most once an hour

    assert qa_log.prune(0, logs / "qa_log.jsonl") == 0  # 0 = keep forever


def test_delete_my_history(client, logs):
    first = client.post("/chat", json={"query": "What is your view on AI safety?"}).json()
    client.post("/chat", json={"query": "Why Mars?"})
    client.post("/feedback", json={"entry_id": first["id"], "persona": "elon_musk", "rating": "up"})
    assert client.get("/insights/analytics", params={"persona": "elon_musk"}).json()["total"] == 2

    assert client.delete("/history", params={"persona": "no_such_model"}).status_code == 404
    r = client.delete("/history", params={"persona": "elon_musk"})
    assert r.json() == {"questions_deleted": 2, "feedback_deleted": 1}
    assert client.get("/insights/analytics", params={"persona": "elon_musk"}).json()["total"] == 0
    assert client.get("/review").json() == []


def test_with_accounts_only_your_own_history_is_deleted(srv, logs, monkeypatch):
    monkeypatch.setattr(srv.config, "USERS", "asha:mango-tree,ravi:blue-bicycle")

    def sign_in(name, code):
        c = TestClient(srv.app, base_url="http://localhost")
        assert c.post("/auth/login", json={"user": name, "code": code}).status_code == 200
        return c
    asha, ravi = sign_in("asha", "mango-tree"), sign_in("ravi", "blue-bicycle")
    asha.post("/chat", json={"query": "Why Mars?"})
    ravi.post("/chat", json={"query": "Why Mars?"})
    ravi.post("/chat", json={"query": "What about Tesla?"})

    assert asha.delete("/history").json()["questions_deleted"] == 1
    assert [e["user"] for e in qa_log.read_entries()] == ["ravi", "ravi"]
    assert ravi.get("/insights/analytics").json()["total"] == 2


def test_pruning_never_deadlocks_with_log_writers(client, logs, monkeypatch, srv):
    """Pruning takes each log's lock; no code path may call it while holding one."""
    import threading

    monkeypatch.setattr(srv.config, "LOG_RETENTION_DAYS", 90)
    monkeypatch.setattr(qa_log, "_PRUNE_EVERY", 0)  # prune on every call
    failures = []

    def flow():
        try:
            pid = client.post("/personas", json={"name": "pytest Retention", "relationship": "self", "consent": True}).json()["id"]
            d = client.post("/chat", json={"query": "Why Mars?"}).json()
            fid = client.post("/feedback", json={"entry_id": d["id"], "persona": "elon_musk", "rating": "up"}).json()["id"]
            client.get("/review")
            client.post(f"/review/{fid}/dismiss")
            client.get("/insights/analytics")
            client.delete(f"/personas/{pid}")  # purges its log entries and feedback
            client.delete("/history")
        except Exception as e:  # pragma: no cover - reported below
            failures.append(e)

    t = threading.Thread(target=flow, daemon=True)
    t.start()
    t.join(timeout=60)
    assert not t.is_alive(), "a log lock was taken twice"
    assert not failures
