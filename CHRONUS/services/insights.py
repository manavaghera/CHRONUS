"""
Insights: feedback with human review, knowledge gaps, and usage analytics,
all built on the Q&A log (services/qa_log.py).

Feedback (thumbs up/down, "not their words"...) lands in a review queue.
A reviewer can approve an answer for a custom model, which stores it as a
memory labelled "reviewed past answer" (synthesized, never quoted as their
own words). This is the safe form of the auto-training that BUG 1 had to
switch off: nothing enters memory without a person approving it.

    POST /feedback                      {entry_id, persona, rating, reason?, note?}
    GET  /review?persona=&status=       the queue
    POST /review/{id}/approve           {answer?}  (custom models; may edit the answer first)
    POST /review/{id}/dismiss
    GET  /insights/gaps?persona=        what people asked that the archive couldn't answer
    GET  /insights/analytics?persona=&days=
    DELETE /history?persona=            delete my questions and feedback

Both logs are kept for config.LOG_RETENTION_DAYS (services/qa_log.py).
"""

from __future__ import annotations

import hashlib
import json
import secrets
import statistics
import threading
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi import Path as PathParam
from pydantic import BaseModel, Field

from services import personas as ps
from services import qa_log
from services.provenance import content_words

FEEDBACK_PATH = Path(__file__).resolve().parent.parent / "feedback.jsonl"
FEEDBACK_ID = PathParam(pattern=r"^[0-9a-f]{12}$")
REASONS = ("wrong_attribution", "not_their_words", "incorrect", "unhelpful", "other")

_lock = threading.Lock()
qa_log.retain(lambda: FEEDBACK_PATH, _lock)


class FeedbackIn(BaseModel):
    entry_id: str = Field(pattern=r"^[0-9a-f]{12}$")
    persona: str = Field(pattern=ps.PERSONA_ID_PATTERN)
    rating: Literal["up", "down"]
    reason: Literal["wrong_attribution", "not_their_words", "incorrect", "unhelpful", "other"] | None = None
    note: str = Field(default="", max_length=1000)


class ApproveIn(BaseModel):
    answer: str | None = Field(default=None, min_length=3, max_length=4000)


# ---- feedback store (JSON lines, rewritten on review) ----

def read_feedback(path: Path | None = None) -> list[dict]:
    path = path or FEEDBACK_PATH
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            out.append(item)
    return out


def _write_feedback(items: list[dict], path: Path | None = None) -> None:
    path = path or FEEDBACK_PATH
    tmp = path.with_suffix(".tmp")
    tmp.write_text("".join(json.dumps(i, ensure_ascii=False) + "\n" for i in items), encoding="utf-8")
    tmp.replace(path)


def purge_feedback(persona: str, path: Path | None = None) -> int:
    """Remove a deleted model's feedback (it quotes its answers)."""
    with _lock:
        items = read_feedback(path)
        kept = [i for i in items if i.get("persona") != persona]
        if len(kept) != len(items):
            _write_feedback(kept, path)
    return len(items) - len(kept)


# ---- knowledge gaps ----

def _normalize(question: str) -> frozenset:
    return frozenset(content_words(question))


def cluster_questions(entries: list[dict], min_overlap: float = 0.5) -> list[dict]:
    """Group near-identical questions ("why did you leave?" / "why did you
    leave your job?") by content-word overlap (Jaccard)."""
    clusters: list[dict] = []
    for e in entries:
        words = _normalize(e["query"])
        home = None
        for c in clusters:
            union = words | c["words"]
            if union and len(words & c["words"]) / len(union) >= min_overlap:
                home = c
                break
        if home is None:
            home = {"words": words, "questions": [], "count": 0, "last_asked": ""}
            clusters.append(home)
        home["count"] += 1
        home["questions"].append(e["query"])
        home["last_asked"] = max(home["last_asked"], e.get("timestamp", ""))
    for c in clusters:
        counts = Counter(c["questions"])
        c["question"] = counts.most_common(1)[0][0]
        c["examples"] = [q for q, _ in counts.most_common(4)][1:]
        del c["words"], c["questions"]
    clusters.sort(key=lambda c: c["last_asked"], reverse=True)  # most recent first among ties
    return sorted(clusters, key=lambda c: -c["count"])


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    values = sorted(values)
    k = (len(values) - 1) * pct
    lo, hi = int(k), min(int(k) + 1, len(values) - 1)
    return round(values[lo] + (values[hi] - values[lo]) * (k - lo), 1)


def analytics(entries: list[dict], feedback: list[dict], days: int = 30, today: date | None = None) -> dict:
    """Numbers for the Insights page, from Q&A log entries."""
    today = today or date.today()
    total = len(entries)
    refused = sum(1 for e in entries if e.get("fallback") or e.get("mode") == "fallback")
    grounding = [float(e["faithfulness"]) for e in entries
                 if isinstance(e.get("faithfulness"), (int, float)) and e.get("mode") not in ("fallback", "basic_info")]
    buckets = [0] * 5
    for g in grounding:
        buckets[min(int(g * 5), 4)] += 1
    latency = [float(e["latency_ms"]) for e in entries if isinstance(e.get("latency_ms"), (int, float))]
    start = today - timedelta(days=days - 1)
    per_day = Counter()
    for e in entries:
        try:
            d = datetime.fromisoformat(e.get("timestamp", "")).date()
        except ValueError:
            continue
        if d >= start:
            per_day[d.isoformat()] += 1
    top = Counter(" ".join(sorted(_normalize(e["query"]))) or e["query"].lower() for e in entries)
    examples = {}
    for e in entries:
        examples.setdefault(" ".join(sorted(_normalize(e["query"]))) or e["query"].lower(), e["query"])
    ratings = Counter(f.get("rating") for f in feedback)
    return {
        "total": total,
        "refused": refused,
        "refusal_rate": round(refused / total, 3) if total else 0.0,
        "by_mode": dict(Counter(e.get("mode", "unknown") for e in entries).most_common()),
        "by_confidence": dict(Counter(e.get("confidence", "unknown") for e in entries).most_common()),
        "by_persona": dict(Counter(e.get("persona", "elon_musk") for e in entries).most_common()),
        "grounding": {
            "buckets": [{"from": i / 5, "to": (i + 1) / 5, "count": n} for i, n in enumerate(buckets)],
            "median": round(statistics.median(grounding), 2) if grounding else None,
        },
        "latency_ms": {"p50": _percentile(latency, 0.5), "p95": _percentile(latency, 0.95), "samples": len(latency)},
        "per_day": [{"date": (start + timedelta(days=i)).isoformat(), "count": per_day.get((start + timedelta(days=i)).isoformat(), 0)}
                    for i in range(days)],
        "top_questions": [{"question": examples[k], "count": n} for k, n in top.most_common(8)],
        "feedback": {"up": ratings.get("up", 0), "down": ratings.get("down", 0),
                     "pending": sum(1 for f in feedback if f.get("status") == "pending")},
    }


def _mine(item: dict) -> bool:
    """Accounts: questions asked from other accounts (even to shared
    pretrained models) are theirs, not this person's."""
    user = ps.current_user.get()
    return user is None or item.get("user") in (None, user)


def make_router(client, embedder) -> APIRouter:
    router = APIRouter(tags=["insights"])

    def _visible_persona(persona_id: str) -> dict:
        persona = ps.load_persona(persona_id)
        if persona is None:
            raise HTTPException(status_code=404, detail=f"No model called '{persona_id}'")
        return persona

    def _scope(persona: str | None) -> set[str]:
        """Personas whose data this request may see (all visible ones, or one)."""
        if persona:
            return {_visible_persona(persona)["id"]}
        return {p["id"] for p in ps.list_personas()}

    @router.post("/feedback", status_code=201)
    def give_feedback(body: FeedbackIn):
        _visible_persona(body.persona)
        entry = next((e for e in qa_log.read_entries(body.persona) if e.get("id") == body.entry_id and _mine(e)), None)
        if entry is None:
            raise HTTPException(status_code=404, detail="That answer isn't in the log (it may have been deleted)")
        item = {
            "id": secrets.token_hex(6), "entry_id": body.entry_id, "persona": body.persona,
            "rating": body.rating, "reason": body.reason, "note": body.note.strip(),
            "question": entry["query"], "answer": entry.get("answer", ""), "mode": entry.get("mode"),
            "sources": entry.get("sources", []), "timestamp": datetime.now().isoformat(timespec="seconds"),
            "status": "pending", "user": ps.current_user.get(),
        }
        with _lock:
            # One vote per answer: a second click changes it
            items = [i for i in read_feedback() if i.get("entry_id") != body.entry_id]
            _write_feedback([*items, item])
        return {"id": item["id"], "status": "pending"}

    @router.get("/review")
    def review_queue(persona: str | None = Query(None, pattern=ps.PERSONA_ID_PATTERN),
                     status: Literal["pending", "approved", "dismissed", "all"] = "pending"):
        qa_log.prune_if_due()
        allowed = _scope(persona)
        items = [i for i in read_feedback() if i.get("persona") in allowed and _mine(i)
                 and (status == "all" or i.get("status") == status)]
        kinds = {p["id"]: p["kind"] for p in ps.list_personas()}
        for i in items:
            i["can_approve"] = kinds.get(i["persona"]) == "custom"
        return sorted(items, key=lambda i: i.get("timestamp", ""), reverse=True)

    def _review(feedback_id: str, update) -> dict:
        with _lock:
            items = read_feedback()
            item = next((i for i in items if i.get("id") == feedback_id), None)
            if item is None or item.get("persona") not in _scope(None) or not _mine(item):
                raise HTTPException(status_code=404, detail="No such feedback")
            update(item)
            item["reviewed_at"] = datetime.now().isoformat(timespec="seconds")
            _write_feedback(items)
        return item

    @router.post("/review/{feedback_id}/approve")
    def approve(body: ApproveIn, feedback_id: str = FEEDBACK_ID):
        def do(item):
            persona = _visible_persona(item["persona"])
            if persona["kind"] != "custom":
                raise HTTPException(status_code=403, detail="Pretrained models only learn from published sources; dismiss instead")
            if item.get("status") == "approved":
                raise HTTPException(status_code=409, detail="Already approved")
            answer = (body.answer or item["answer"]).strip()
            text = f"Q: {item['question']}\nA: {answer}"
            memory_id = "rv_" + hashlib.md5(text.encode("utf-8")).hexdigest()[:16]
            ps.get_collection(client, persona).upsert(
                ids=[memory_id], documents=[text],
                embeddings=embedder.encode([text], normalize_embeddings=True).tolist(),
                metadatas=[{"source_type": "reviewed_answer", "source_file": "reviewed_answers",
                            "source_name": "Reviewed past answer", "memory_id": memory_id, "person": persona["id"],
                            "question": item["question"][:300], "date": "unknown", "importance_score": 2,
                            "reviewed_at": datetime.now().isoformat(timespec="seconds")}])
            item.update(status="approved", approved_answer=answer, memory_id=memory_id)
        return _review(feedback_id, do)

    @router.post("/review/{feedback_id}/dismiss")
    def dismiss(feedback_id: str = FEEDBACK_ID):
        return _review(feedback_id, lambda item: item.update(status="dismissed"))

    @router.get("/insights/gaps")
    def gaps(persona: str = Query(..., pattern=ps.PERSONA_ID_PATTERN), limit: int = Query(20, ge=1, le=100)):
        p = _visible_persona(persona)
        entries = [e for e in qa_log.read_entries(persona) if _mine(e)]
        unanswered = [e for e in entries if e.get("fallback") or e.get("mode") == "fallback" or e.get("confidence") == "low"]
        clusters = cluster_questions(unanswered)[:limit]
        # Custom models: the interview question that would most likely fill the gap
        if p["kind"] == "custom" and clusters:
            from data.interview_protocol import get_all_questions
            questions = [q for q in get_all_questions() if q["id"] not in set(p.get("interview_answered", []))]
            if questions:
                qv = embedder.encode([q["question"] for q in questions], normalize_embeddings=True)
                cv = embedder.encode([c["question"] for c in clusters], normalize_embeddings=True)
                best = (cv @ qv.T).argmax(axis=1)
                for c, i in zip(clusters, best):
                    c["suggestion"] = {"id": questions[i]["id"], "question": questions[i]["question"]}
        return {"persona": persona, "total_questions": len(entries), "unanswered": len(unanswered), "gaps": clusters}

    @router.get("/insights/analytics")
    def get_analytics(persona: str | None = Query(None, pattern=ps.PERSONA_ID_PATTERN), days: int = Query(30, ge=1, le=365)):
        allowed = _scope(persona)
        entries = [e for e in qa_log.read_entries() if e["persona"] in allowed and _mine(e)]
        feedback = [f for f in read_feedback() if f.get("persona") in allowed and _mine(f)]
        return analytics(entries, feedback, days)

    @router.delete("/history")
    def delete_history(persona: str | None = Query(None, pattern=ps.PERSONA_ID_PATTERN)):
        """Delete the questions this person asked (and their feedback), for
        one model or all. Answers a reviewer already approved into a custom
        model stay in its memories (delete them in its memory browser)."""
        if persona:
            _visible_persona(persona)
        user = ps.current_user.get()
        questions = qa_log.forget(user, persona)
        feedback = qa_log.forget(user, persona, FEEDBACK_PATH, _lock)
        return {"questions_deleted": questions, "feedback_deleted": feedback}

    return router
