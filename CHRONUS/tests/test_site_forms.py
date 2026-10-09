"""The website's public forms (services/site_forms.py): waitlist, contact, report a model."""

import pytest

from services import access, site_forms


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(site_forms, "DATA_DIR", tmp_path)
    return tmp_path


WAITLIST = {"email": "Asha@Example.com", "name": "Asha", "plan": "voice", "people": 3, "country": "UK", "agree": True}
CONTACT = {"name": "Ravi", "email": "ravi@example.com", "topic": "partnership", "message": "We run a hospice in Pune.", "agree": True}
REPORT = {"name": "Meera", "email": "meera@example.com", "model": "Model of my father", "relationship": "family",
          "reason": "deceased_no_agreement", "details": "My brother made this without asking the family.", "truthful": True}


def test_waitlist_keeps_each_email_once(client):
    first = client.post("/site/waitlist", json=WAITLIST)
    assert first.status_code == 201 and first.json() == {"joined": True, "already": False}
    again = client.post("/site/waitlist", json={**WAITLIST, "email": "asha@example.com"})
    assert again.json()["already"] is True
    rows = site_forms.read("waitlist")
    assert len(rows) == 1 and rows[0]["email"] == "asha@example.com" and rows[0]["people"] == 3
    assert "website" not in rows[0] and "ip" not in rows[0]  # no spam trap, no address kept


def test_forms_validate_what_they_receive(client):
    assert client.post("/site/waitlist", json={**WAITLIST, "email": "not an email"}).status_code == 422
    assert client.post("/site/waitlist", json={**WAITLIST, "agree": False}).status_code == 422
    assert client.post("/site/waitlist", json={**WAITLIST, "people": 0}).status_code == 422
    assert client.post("/site/contact", json={**CONTACT, "message": "hi"}).status_code == 422
    assert client.post("/site/report", json={**REPORT, "truthful": False}).status_code == 422
    assert client.post("/site/report", json={**REPORT, "reason": "dislike"}).status_code == 422
    assert site_forms.read("waitlist") == site_forms.read("contact") == site_forms.read("report") == []


def test_a_bot_filling_the_hidden_field_gets_a_normal_answer_and_nothing_is_saved(client):
    assert client.post("/site/waitlist", json={**WAITLIST, "website": "http://spam"}).json() == {"joined": True}
    assert client.post("/site/contact", json={**CONTACT, "website": "x"}).status_code == 201
    assert "reference" in client.post("/site/report", json={**REPORT, "website": "x"}).json()
    assert not any(site_forms.read(kind) for kind in ("waitlist", "contact", "report"))


def test_contact_and_report_are_saved_with_a_reference(client):
    assert client.post("/site/contact", json=CONTACT).json() == {"sent": True}
    reference = client.post("/site/report", json=REPORT).json()["reference"]
    assert reference.startswith("R-") and len(reference) == 10
    report = site_forms.read("report")[0]
    assert report["reference"] == reference and report["status"] == "new" and report["reason"] == "deceased_no_agreement"
    assert site_forms.read("contact")[0]["topic"] == "partnership"


def test_forms_work_without_signing_in_but_the_archive_does_not(client, srv, monkeypatch):
    monkeypatch.setattr(srv.config, "ACCESS_CODE", "open sesame")
    client.cookies.clear()
    assert client.post("/site/waitlist", json=WAITLIST).status_code == 201
    assert client.get("/personas").status_code == 401


def test_forms_refuse_other_websites(client):
    response = client.post("/site/waitlist", json=WAITLIST, headers={"Origin": "https://evil.example"})
    assert response.status_code == 403


def test_submissions_per_address_are_limited(client, monkeypatch):
    monkeypatch.setenv("CHRONUS_RATE_LIMIT", "30")
    monkeypatch.setattr(access, "limiter", access._Limiter())
    codes = [client.post("/site/contact", json=CONTACT).status_code for _ in range(site_forms.FORMS_PER_HOUR + 1)]
    assert codes[:-1] == [201] * site_forms.FORMS_PER_HOUR and codes[-1] == 429


def test_export_writes_csv(client, capsys):
    client.post("/site/waitlist", json=WAITLIST)
    assert site_forms.export("waitlist") == 1
    out = capsys.readouterr().out
    assert out.splitlines()[0].startswith("email,") and "asha@example.com" in out
