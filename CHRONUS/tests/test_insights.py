"""Feedback + human review, knowledge gaps and analytics (services/insights.py)."""

import base64
from datetime import date

import pytest

from services import insights, qa_log
from services import personas as ps


@pytest.fixture
def logs(srv, monkeypatch, tmp_path):
    """Real logging, into throwaway files."""
    monkeypatch.setattr(qa_log, "QA_LOG_PATH", tmp_path / "qa_log.jsonl")
    monkeypatch.setattr(insights, "FEEDBACK_PATH", tmp_path / "feedback.jsonl")
    monkeypatch.setattr(srv, "log_qa", qa_log.log_qa)
    return tmp_path


@pytest.fixture(scope="module")
def custom(client):
    r = client.post("/personas", json={"name": "pytest Insights", "relationship": "self", "consent": True})
    pid = r.json()["id"]
    text = ("In the garden behind our house I grew mangoes, tomatoes and tulsi, and I watered them every evening.\n\n"
            "I taught fractions to the children of our village school for thirty years, mostly with mangoes.\n\n"
            "My younger brother Ravi moved to Pune in 1979 and wrote me a letter every single month.")
    r = client.post(f"/personas/{pid}/documents", json={"filename": "notes.txt", "content_base64": base64.b64encode(text.encode()).decode()})
    assert r.status_code == 200, r.text
    for i in range(1, 9):
        client.post(f"/personas/{pid}/interview", json={"question_id": f"Q{i}", "answer": f"Interview answer {i} about teaching."})
    assert client.post(f"/personas/{pid}/build").status_code == 200
    yield pid
    client.delete(f"/personas/{pid}")


def test_feedback_review_and_approve_into_memory(client, logs, custom):
    d = client.post("/chat", json={"query": "What did you grow in the garden?", "persona": custom, "mode": "mix_method"}).json()
    assert len(d["id"]) == 12
    assert client.post("/feedback", json={"entry_id": "0" * 12, "persona": custom, "rating": "up"}).status_code == 404
    r = client.post("/feedback", json={"entry_id": d["id"], "persona": custom, "rating": "down", "reason": "incorrect", "note": "It was mangoes"})
    assert r.status_code == 201
    # a second click on the same answer changes the vote instead of adding one
    fid = client.post("/feedback", json={"entry_id": d["id"], "persona": custom, "rating": "up"}).json()["id"]
    queue = client.get("/review", params={"persona": custom}).json()
    assert [q["id"] for q in queue] == [fid] and queue[0]["can_approve"] and queue[0]["question"] == "What did you grow in the garden?"

    before = client.get(f"/personas/{custom}").json()["memories"]
    approved = client.post(f"/review/{fid}/approve", json={"answer": "Mangoes and tulsi, mostly."}).json()
    assert approved["status"] == "approved" and approved["memory_id"].startswith("rv_")
    assert client.get(f"/personas/{custom}").json()["memories"] == before + 1
    memory = client.get(f"/personas/{custom}/memories/{approved['memory_id']}").json()
    assert memory["voice"] == "synthesized" and "Mangoes and tulsi" in memory["text"]  # never quoted as their words
    assert client.post(f"/review/{fid}/approve", json={}).status_code == 409
    assert client.get("/review", params={"persona": custom}).json() == []


def test_pretrained_answers_can_only_be_dismissed(client, logs):
    d = client.post("/chat", json={"query": "hey"}).json()
    fid = client.post("/feedback", json={"entry_id": d["id"], "persona": "elon_musk", "rating": "down", "reason": "not_their_words"}).json()["id"]
    assert client.post(f"/review/{fid}/approve", json={}).status_code == 403
    assert client.post(f"/review/{fid}/dismiss").json()["status"] == "dismissed"


def test_gaps_group_questions_and_suggest_interview_questions(client, logs, custom):
    for q in ["What is your favourite film?", "What's your favourite film ever?", "Which car did you drive?"]:
        client.post("/chat", json={"query": q, "persona": custom, "mode": "mix_method", "year_from": 1900, "year_to": 1901})
    g = client.get("/insights/gaps", params={"persona": custom}).json()
    assert g["unanswered"] == 3 and g["gaps"][0]["count"] == 2 and "film" in g["gaps"][0]["question"]
    assert g["gaps"][0]["suggestion"]["id"].startswith("Q")


def test_analytics(client, logs):
    client.post("/chat", json={"query": "How do I descale a kettle?", "mode": "mix_method"})
    client.post("/chat", json={"query": "hey"})
    a = client.get("/insights/analytics", params={"persona": "elon_musk", "days": 7}).json()
    assert a["total"] == 2 and a["refused"] == 1 and a["refusal_rate"] == 0.5
    assert len(a["per_day"]) == 7 and a["per_day"][-1]["count"] == 2 and a["latency_ms"]["samples"] == 2


def test_analytics_math():
    entries = [{"query": "Why Mars?", "mode": "natural", "confidence": "high", "faithfulness": 0.9, "latency_ms": 100, "timestamp": "2026-10-05T10:00:00"},
               {"query": "why mars", "mode": "mix_method", "confidence": "medium", "faithfulness": 0.3, "latency_ms": 300, "timestamp": "2026-10-06T10:00:00"},
               {"query": "Kettle?", "mode": "fallback", "confidence": "low", "fallback": True, "faithfulness": 0, "timestamp": "2026-10-06T11:00:00"}]
    a = insights.analytics(entries, [{"rating": "up", "status": "pending"}], days=3, today=date(2026, 10, 6))
    assert a["grounding"]["buckets"][4]["count"] == 1 and a["grounding"]["buckets"][1]["count"] == 1
    assert a["latency_ms"]["p50"] == 200.0 and a["top_questions"][0] == {"question": "Why Mars?", "count": 2}
    assert [d["count"] for d in a["per_day"]] == [0, 1, 2] and a["feedback"] == {"up": 1, "down": 0, "pending": 1}


def test_deleting_a_model_purges_its_feedback(client, logs):
    r = client.post("/personas", json={"name": "pytest Purge feedback", "relationship": "self", "consent": True})
    pid = r.json()["id"]
    insights._write_feedback([{"id": "a" * 12, "persona": pid, "answer": "private"}, {"id": "b" * 12, "persona": "elon_musk"}])
    client.delete(f"/personas/{pid}")
    assert [f["persona"] for f in insights.read_feedback()] == ["elon_musk"]
    assert ps.load_persona(pid) is None
