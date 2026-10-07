"""Inline citations (natural_mode.clean_citations) and /chat/stream."""

import base64
import json
from unittest import mock

import pytest

import services.natural_mode as nm
from services import personas as ps

LETTER = ("My favourite birthday was my eighteenth. My father bought me a blue Hero bicycle, and I rode it "
          "to the market every morning for twenty years.\n\nTeaching fractions with mangoes always worked "
          "better than any textbook.\n\nGardening taught me patience, with tomatoes, chillies and tulsi.")


def _events(text: str) -> list[tuple[str, dict]]:
    out = []
    for block in text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        out.append((lines["event"], json.loads(lines["data"])))
    return out


@pytest.mark.parametrize("raw,clean", [
    ("Mars matters. [1] [9] Next thing [2].", "Mars matters [1]. Next thing [2]."),
    ("We need rockets [1][1]. And Mars [3].", "We need rockets [1]. And Mars."),
    ("No markers here.", "No markers here."),
])
def test_clean_citations(raw, clean):
    assert nm.clean_citations(raw, 2) == clean
    assert "[" not in nm.strip_citations(clean)


def test_prompt_asks_for_markers():
    assert "[1] or [2]" in nm.build_system_prompt("Amma", "[1] YOUR OWN WORDS: x")


def test_stream_errors_before_streaming(client):
    assert client.post("/chat/stream", json={"query": "hello there", "persona": "nobody_here"}).status_code == 404


def test_stream_sends_a_final_answer(client):
    r = client.post("/chat/stream", json={"query": "How do I descale a kettle?", "mode": "mix_method"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    [(event, data)] = _events(r.text)
    assert event == "final" and data["fallback"] is True and "answer" in data


@pytest.fixture(scope="module")
def cloud_persona(client):
    r = client.post("/personas", json={"name": "pytest Stream", "relationship": "self", "consent": True, "allow_cloud_llm": True})
    pid = r.json()["id"]
    client.post(f"/personas/{pid}/documents", json={"filename": "letter.txt", "content_base64": base64.b64encode(LETTER.encode()).decode()})
    for i in range(1, 9):
        client.post(f"/personas/{pid}/interview", json={"question_id": f"Q{i}", "answer": f"Answer number {i} about my life and garden."})
    assert client.post(f"/personas/{pid}/build").status_code == 200
    p = ps.load_persona(pid)
    p["distance_threshold"] = 1.0  # hash embedder in the sample setup
    ps.save_persona(p)
    yield pid
    client.delete(f"/personas/{pid}")


def test_natural_answer_streams_tokens_then_cited_final(srv, client, cloud_persona, monkeypatch):
    monkeypatch.setattr(srv, "IMPORTANCE_WEIGHT", 0.0)  # rank by match only: this tests streaming, not ranking
    chunks = ["My favourite birthday was my eighteenth", ", when my father bought me a blue Hero bicycle. [1]"]
    lines = [f"data: {json.dumps({'choices': [{'delta': {'content': c}, 'finish_reason': None}]})}" for c in chunks]
    lines += [": OPENROUTER PROCESSING", f"data: {json.dumps({'choices': [{'delta': {}, 'finish_reason': 'stop'}]})}", "data: [DONE]"]
    response = mock.MagicMock()
    response.__enter__.return_value = response
    response.iter_lines.return_value = iter(lines)
    with mock.patch.object(nm.config, "LLM_PROVIDER", "openrouter"), mock.patch.object(nm.config, "OPENAI_API_KEY", "k"), \
            mock.patch.object(nm.requests, "post", return_value=response) as post:
        r = client.post("/chat/stream", json={"query": "What was your favourite birthday?", "persona": cloud_persona, "mode": "natural"})
    events = _events(r.text)
    assert [e for e, _ in events[:-1]] == ["token", "token"] and "".join(d["text"] for _, d in events[:-1]) == "".join(chunks)
    event, final = events[-1]
    assert event == "final" and final["mode"] == "natural", final
    assert final["answer"].endswith("bicycle [1].") and final["sources"]
    assert post.call_args.kwargs["stream"] is True and post.call_args.kwargs["json"]["stream"] is True
