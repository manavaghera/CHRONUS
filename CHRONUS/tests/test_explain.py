"""The About panel (/personas/{id}/about) and the "why this confidence" explanation."""

import base64


def test_about_custom_model(client):
    pid = client.post("/personas", json={"name": "pytest About", "relationship": "self", "consent": True, "memorial": True}).json()["id"]
    try:
        text = "\n\n".join(f"Memory {i}: I walked along the river every evening and counted the boats until sunset." for i in range(3))
        client.post(f"/personas/{pid}/documents", json={"filename": "walks.txt", "content_base64": base64.b64encode(text.encode()).decode()})
        client.post(f"/personas/{pid}/interview", json={"question_id": "Q1", "answer": "Quiet and patient.", "origin": "family"})
        a = client.get(f"/personas/{pid}/about").json()
        assert a["memories"] == sum(a["by_voice"].values()) and a["by_voice"]["first_person"] >= 1
        assert a["by_voice"]["third_party"] == 1  # the family's interview answer
        assert a["consent_given_at"] and a["memorial"] is True and a["top_sources"][0]["source_file"] in ("walks.txt", "interview_protocol")
    finally:
        client.delete(f"/personas/{pid}")


def test_pretrained_about_has_no_consent_record(client):
    a = client.get("/personas/elon_musk/about").json()
    assert a["kind"] == "pretrained" and "consent_given_at" not in a and 0 < a["threshold"] < 1


def test_refusals_explain_themselves(client):
    d = client.post("/chat", json={"query": "How do I descale a kettle?", "mode": "mix_method"}).json()
    assert d["fallback"] and d["why"]["threshold_match"] == 42 and d["why"]["sources"] == 0
    assert "best_match" in d["why"]
