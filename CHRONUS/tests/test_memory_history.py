"""Memory history with undo (services/memory_history.py): an edit never
destroys the original words, deletes can be undone, and tampering shows."""

import base64
import json

import pytest

from services import memory_history
from services import personas as ps

LETTER = ("My favourite birthday was my eighteenth, when my father gave me a blue bicycle.\n\n"
          "I taught mathematics at the village school for thirty years and loved every morning of it.\n\n"
          "Every Diwali I made besan laddoos for the whole street and the children queued at our gate.")


@pytest.fixture
def model(client):
    pid = client.post("/personas", json={"name": "pytest History", "description": "x", "relationship": "family",
                                         "consent": True}).json()["id"]
    client.post(f"/personas/{pid}/documents", json={"filename": "letter.txt",
                                                    "content_base64": base64.b64encode(LETTER.encode()).decode()})
    yield pid
    client.delete(f"/personas/{pid}")
    assert not (ps.CUSTOM_DIR / pid).exists()  # the history goes with the model


def _bicycle(client, pid):
    return next(m for m in client.get(f"/personas/{pid}/memories").json()["items"] if "bicycle" in m["text"])


def test_an_edit_keeps_the_original_and_can_be_undone(client, model):
    memory = _bicycle(client, model)
    original = memory["text"]
    client.patch(f"/personas/{model}/memories/{memory['id']}", json={"text": "My favourite birthday was my twentieth."})
    versions = client.get(f"/personas/{model}/memories/{memory['id']}/history").json()["versions"]
    assert [v["text"] for v in versions] == [original, "My favourite birthday was my twentieth."]
    assert versions[0]["replaced_by"] == "edit" and versions[-1]["current"] is True
    restored = client.post(f"/personas/{model}/memories/{memory['id']}/restore", json={"seq": versions[0]["seq"]}).json()
    assert restored["text"] == original
    assert len(client.get(f"/personas/{model}/memories/{memory['id']}/history").json()["versions"]) == 3


def test_a_deleted_memory_can_be_restored(client, model):
    memory = _bicycle(client, model)
    client.delete(f"/personas/{model}/memories/{memory['id']}")
    gone = client.get(f"/personas/{model}/history").json()["deleted"]
    assert [d["memory_id"] for d in gone] == [memory["id"]]
    client.post(f"/personas/{model}/memories/{memory['id']}/restore", json={"seq": gone[0]["seq"]})
    assert _bicycle(client, model)["id"] == memory["id"]
    found = client.get(f"/personas/{model}/memories", params={"q": "blue bicycle"}).json()["items"]
    assert found[0]["id"] == memory["id"]  # re-embedded: searchable again
    assert client.get(f"/personas/{model}/history").json()["deleted"] == []


def test_tampering_with_the_log_shows(client, model):
    memory = _bicycle(client, model)
    client.patch(f"/personas/{model}/memories/{memory['id']}", json={"text": "An edited memory about a bicycle."})
    client.patch(f"/personas/{model}/memories/{memory['id']}", json={"text": "Edited again, about a bicycle."})
    assert client.get(f"/personas/{model}/history").json()["log"] == {"ok": True, "entries": 2, "broken_at": None}
    path = ps.CUSTOM_DIR / model / "history.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    first["before"]["text"] = "Something she never wrote."
    path.write_text("\n".join([json.dumps(first)] + lines[1:]) + "\n", encoding="utf-8")
    assert memory_history.verify(ps.load_persona(model)) == {"ok": False, "entries": 2, "broken_at": 1}


def test_pretrained_models_have_no_editable_history(client):
    assert client.get("/personas/elon_musk/history").status_code == 403
    assert client.post("/personas/elon_musk/memories/x/restore", json={"seq": 1}).status_code == 403
