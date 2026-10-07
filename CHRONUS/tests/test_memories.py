"""Memory browser (services/memory_routes.py) and time travel (services/timeline.py)."""

import base64

import pytest

from services import personas as ps
from services import timeline

LETTER = """Dear Ravi,

My favourite birthday was my eighteenth. My father bought me a blue Hero bicycle, and I rode it to the market every morning for twenty years.

I became a schoolteacher because I loved watching children understand mathematics for the first time. Teaching fractions with mangoes always worked better than any textbook.

When I retired, I started a small garden with tomatoes, chillies and tulsi. Gardening taught me patience.

With love, Amma"""

DATED = [
    ("d1", "In 2012 I thought electric cars would take a decade to matter, and the bicycle shop was my whole world.", "2012-03-01"),
    ("d2", "By 2016 the bicycle shop had grown into three shops and I was teaching my nephew to repair gears.", "2016-07-11"),
    ("d3", "In 2023 I sold the bicycle shops and finally had time for the garden every single morning.", "2023-01-05"),
]


@pytest.fixture(scope="module")
def persona(client, srv):
    r = client.post("/personas", json={"name": "pytest Memories", "relationship": "self", "consent": True})
    pid = r.json()["id"]
    client.post(f"/personas/{pid}/documents", json={"filename": "letter.txt", "content_base64": base64.b64encode(LETTER.encode()).decode()})
    col = ps.get_collection(srv.client, ps.load_persona(pid))
    col.add(ids=[d[0] for d in DATED], documents=[d[1] for d in DATED],
            embeddings=srv.embedder.encode([d[1] for d in DATED], normalize_embeddings=True).tolist(),
            metadatas=[{"source_type": "personal_writing", "source_file": "diary.txt", "date": d[2]} for d in DATED])
    for qid, answer in [("Q1", "Patient, stubborn, a teacher at heart."), ("Q2", "I hum old songs while cooking."),
                        ("Q3", "I go quiet and make tea."), ("Q4", "A realist who hopes."), ("Q5", "The flood of 1987.")]:
        client.post(f"/personas/{pid}/interview", json={"question_id": qid, "answer": answer})
    assert client.post(f"/personas/{pid}/build").status_code == 200
    # The sample setup's hash embedder isn't calibrated for the 0.58 threshold
    p = ps.load_persona(pid)
    p["distance_threshold"] = 1.0
    ps.save_persona(p)
    yield pid
    client.delete(f"/personas/{pid}")


def test_list_search_and_filter(client, persona):
    everything = client.get(f"/personas/{persona}/memories").json()
    assert everything["total"] >= 10 and all(i["editable"] for i in everything["items"])
    page = client.get(f"/personas/{persona}/memories", params={"limit": 2, "offset": 1}).json()
    assert len(page["items"]) == 2
    diary = client.get(f"/personas/{persona}/memories", params={"source": "diary.txt"}).json()
    assert diary["total"] == 3 and {i["source_file"] for i in diary["items"]} == {"diary.txt"}
    found = client.get(f"/personas/{persona}/memories", params={"q": "blue bicycle birthday father"}).json()
    assert "bicycle" in found["items"][0]["text"] and found["items"][0]["distance"] is not None


def test_memory_with_context(client, persona):
    first = client.get(f"/personas/{persona}/memories", params={"source": "letter.txt"}).json()["items"][0]
    one = client.get(f"/personas/{persona}/memories/{first['id']}").json()
    assert one["text"] == first["text"] and "parent_text" not in one["metadata"]
    assert client.get(f"/personas/{persona}/memories/nope").status_code == 404


def test_edit_and_delete_custom_memories(client, persona):
    r = client.patch(f"/personas/{persona}/memories/d1", json={"text": "In 2012 the bicycle shop was my whole world."})
    assert r.status_code == 200 and r.json()["edited_at"]
    assert client.get(f"/personas/{persona}/memories/d1").json()["text"] == "In 2012 the bicycle shop was my whole world."
    before = client.get(f"/personas/{persona}").json()["memories"]
    client.post(f"/personas/{persona}/interview", json={"question_id": "Q9", "answer": "My sister, always."})
    q9 = [i for i in client.get(f"/personas/{persona}/memories", params={"limit": 100}).json()["items"]
          if i["question_id"] == "Q9"][0]
    assert client.delete(f"/personas/{persona}/memories/{q9['id']}").json()["memories"] == before


def test_pretrained_memories_are_read_only(client):
    assert client.get("/personas/elon_musk/memories", params={"limit": 1}).status_code == 200
    assert client.patch("/personas/elon_musk/memories/x", json={"text": "fake quote"}).status_code == 403
    assert client.delete("/personas/elon_musk/memories/x").status_code == 403
    assert client.delete("/personas/elon_musk/documents/x.txt").status_code == 403


def test_delete_document_removes_its_memories(client, persona):
    client.post(f"/personas/{persona}/documents", json={"filename": "extra.txt", "content_base64": base64.b64encode(
        b"I kept every letter my students ever wrote me in a tin box under the bed, and I still read them.").decode()})
    r = client.delete(f"/personas/{persona}/documents/extra.txt")
    assert r.status_code == 200 and r.json()["memories_removed"] >= 1
    assert client.get(f"/personas/{persona}/memories", params={"source": "extra.txt"}).json()["total"] == 0
    assert "extra.txt" not in [u["filename"] for u in client.get(f"/personas/{persona}").json()["uploads"]]
    assert not (ps.CUSTOM_DIR / persona / "uploads" / "extra.txt").exists()
    assert client.delete(f"/personas/{persona}/documents/extra.txt").status_code == 404


def test_timeline_counts_years(client, persona):
    t = client.get(f"/personas/{persona}/timeline").json()
    assert t["years"] == {"2012": 1, "2016": 1, "2023": 1} and t["undated"] >= 5


@pytest.mark.parametrize("years", [(2010, 2013), (2015, 2017), (2020, None)])
def test_time_travel_only_uses_that_era(client, persona, years):
    body = {"query": "Tell me about the bicycle shop", "persona": persona, "mode": "mix_method",
            "year_from": years[0], "year_to": years[1]}
    d = client.post("/chat", json=body).json()
    assert d["sources"] and all(s["source_file"] == "diary.txt" for s in d["sources"])
    assert {s["date"][:4] for s in d["sources"]} <= {str(y) for y in range(years[0], (years[1] or 2100) + 1)}
    assert "Time travel" in d["notice"]


def test_time_travel_with_nothing_in_range_says_so(client, persona):
    d = client.post("/chat", json={"query": "Tell me about the bicycle shop", "persona": persona, "mode": "mix_method",
                                   "year_from": 1990, "year_to": 1995}).json()
    assert d["fallback"] and "1990 to 1995" in d["notice"]
    assert client.post("/chat", json={"query": "x y z", "persona": persona, "year_from": 2020, "year_to": 2010}).status_code == 422


def test_year_of():
    assert timeline.year_of("2018-06-09") == 2018 and timeline.year_of("unknown") is None and timeline.year_of(None) is None
    assert timeline.year_filter(None, None) is None
    assert timeline.year_filter(2010, 2012) == {"$and": [{"year": {"$gte": 2010}}, {"year": {"$lte": 2012}}]}
