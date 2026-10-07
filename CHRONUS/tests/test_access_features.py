"""Admin/ops endpoints from PR #2 (services/ops.py): roles, MFA, sessions,
audit, notifications, log search, timings; and that they're off unless
configured, with no default password or secret."""

import base64
import hashlib
import hmac
import json
import time

import pytest

from services import ops as access

SECRET, ADMIN_PW, ANALYST_PW = "pytest-ops-secret-0123456789", "pytest-admin-pw", "pytest-analyst-pw"


@pytest.fixture(autouse=True)
def ops_on(tmp_path, monkeypatch):
    monkeypatch.setattr(access, "AUDIT_LOG_PATH", tmp_path / "audit.jsonl")
    monkeypatch.setattr(access, "QA_LOG_PATH", tmp_path / "qa.jsonl")
    assert access.configure(secret=SECRET, admin_password=ADMIN_PW, analyst_password=ANALYST_PW)
    yield
    access.configure(secret="", admin_password="", analyst_password="")


def test_rbac_permissions():
    assert access.has_permission("admin", "audit.read")
    assert not access.has_permission("analyst", "audit.read")


def test_login_rate_limit_and_reset_with_success():
    user = "admin"
    client = "pytest-client"
    for _ in range(4):
        r = access.login(user, "wrong-pw", client)
        assert not r.ok and r.retry_after is None

    blocked = access.login(user, "wrong-pw", client)
    assert not blocked.ok and blocked.retry_after is not None

    # Different client id is independent and should still allow successful login.
    ok = access.login(user, access.ADMIN_BOOTSTRAP_PASSWORD, "pytest-client-2")
    assert ok.ok and ok.token


def test_session_logout_invalidation_and_expired_handling():
    token, _ = access.issue_session("admin", "admin")
    payload = access.parse_session(token)
    assert payload["sub"] == "admin"

    access.revoke_session(token)
    try:
        access.parse_session(token)
        assert False, "expected revoked session to fail"
    except ValueError as e:
        assert "logged out" in str(e)


def test_mfa_totp_and_backup_codes():
    access.disable_mfa("admin")
    setup = access.enable_mfa("admin")
    secret = setup["secret"]
    code = access._totp(secret, int(time.time()))

    needs_mfa = access.login("admin", access.ADMIN_BOOTSTRAP_PASSWORD, "mfa-client")
    assert not needs_mfa.ok and "MFA required" in needs_mfa.message

    with_totp = access.login("admin", access.ADMIN_BOOTSTRAP_PASSWORD, "mfa-client", otp_code=code)
    assert with_totp.ok and with_totp.token

    backup_code = setup["backup_codes"][0]
    with_backup = access.login("admin", access.ADMIN_BOOTSTRAP_PASSWORD, "mfa-client", backup_code=backup_code)
    assert with_backup.ok

    reused = access.login("admin", access.ADMIN_BOOTSTRAP_PASSWORD, "mfa-client", backup_code=backup_code)
    assert not reused.ok and "Invalid backup code" in reused.message

    access.disable_mfa("admin")


def test_audit_notifications_search_presets_cache_and_timing(tmp_path, monkeypatch):
    monkeypatch.setattr(access, "AUDIT_LOG_PATH", tmp_path / "audit.jsonl")
    monkeypatch.setattr(access, "QA_LOG_PATH", tmp_path / "qa.jsonl")

    access.record_audit("auth.login", "admin", "success", {"ip": "127.0.0.1"})
    rows = access.iter_audit(limit=10, action="auth.login")
    assert rows and rows[0]["actor"] == "admin"

    note = access.create_notification("admin", "hi", "welcome")
    assert note["id"] > 0
    unread = access.list_notifications("admin", unread_only=True)
    assert unread
    updated = access.mark_notifications_read("admin", [note["id"]])
    assert updated == 1

    access.save_search_preset("admin", "strict", {"confidence": "high"})
    assert "strict" in access.list_search_presets("admin")

    with access.QA_LOG_PATH.open("w", encoding="utf-8") as f:
        f.write(json.dumps({"query": "mars", "mode": "mix_method", "confidence": "high", "persona": "elon_musk"}) + "\n")
    found = access.search_qa_logs({"query": "mars"}, limit=10)
    assert len(found) == 1

    access.cache_set("k", {"x": 1}, ttl_seconds=5)
    assert access.cache_get("k") == {"x": 1}

    access.record_timing("endpoint", 10)
    access.record_timing("endpoint", 30)
    summary = access.timing_summary()
    assert summary["endpoint"]["count"] >= 2


# ---- Off unless configured; no published password or secret ----

def _forge(secret: str, role: str = "admin") -> str:
    b64 = lambda b: base64.urlsafe_b64encode(b).rstrip(b"=").decode()  # noqa: E731
    body = b64(json.dumps({"exp": int(time.time()) + 3600, "jti": "x", "role": role, "sub": role},
                          separators=(",", ":"), sort_keys=True).encode())
    return body + "." + b64(hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest())


def test_off_without_settings(client):
    access.configure(secret="", admin_password="", analyst_password="")
    r = client.post("/ops/auth/login", json={"username": "admin", "password": "admin123!"})
    assert r.status_code == 404 and "CHRONUS_SESSION_SECRET" in r.json()["detail"]
    assert client.get("/ops/search/logs", headers={"authorization": "Bearer " + _forge("x" * 20)}).status_code == 404
    # PR #2's built-in secret, or a weak one, never switches it on
    assert not access.configure(secret="chronus-dev-only-secret-change-me", admin_password="a-long-password")
    assert not access.configure(secret="short", admin_password="a-long-password")
    assert not access.configure(secret=SECRET, admin_password="")


def test_tokens_signed_with_another_secret_are_refused(client):
    for secret in ("chronus-dev-only-secret-change-me", "some-other-secret-0123456789"):
        r = client.get("/ops/audit", headers={"authorization": "Bearer " + _forge(secret)})
        assert r.status_code == 401
    assert client.get("/ops/audit", headers={"authorization": "Bearer " + _forge(SECRET)}).status_code == 200


def test_old_default_passwords_dont_work():
    assert not access.login("admin", "admin123!", "c1").ok
    assert not access.login("analyst", "analyst123!", "c2").ok


def test_http_flow_roles_and_audit(client):
    def login(user, pw):
        r = client.post("/ops/auth/login", json={"username": user, "password": pw})
        assert r.status_code == 200, r.text
        return {"authorization": f"Bearer {r.json()['access_token']}"}

    admin, analyst = login("admin", ADMIN_PW), login("analyst", ANALYST_PW)
    access.QA_LOG_PATH.write_text(json.dumps({"query": "Why Mars?", "mode": "mix_method", "confidence": "high",
                                              "persona": "elon_musk", "timestamp": "2026-10-07T00:00:00"}) + "\n")
    assert client.get("/ops/search/logs", params={"query": "mars"}, headers=analyst).json()["count"] == 1
    export = client.post("/ops/bulk/export/logs", headers=admin)
    assert export.status_code == 200 and "Why Mars?" in export.text
    assert client.get("/ops/audit", headers=analyst).status_code == 403  # analysts can't read the audit log
    actions = [row["action"] for row in client.get("/ops/audit", headers=admin).json()["items"]]
    assert "bulk.logs.export" in actions and "search.logs" in actions
    assert client.get("/ops/auth/me", headers=admin).json()["role"] == "admin"
    assert client.post("/ops/auth/logout", headers=admin).json() == {"success": True}
    assert client.get("/ops/auth/me", headers=admin).status_code == 401
    # The site's own sign-in is unchanged
    assert client.post("/auth/login", json={"code": "anything"}).json() == {"signed_in": True, "user": None}


def test_timings_use_route_names(client):
    client.get("/personas/elon_musk")
    client.get("/no/such/page/12345")
    names = access.timing_summary()
    assert "http.GET:/personas/{persona_id}" in names
    assert not any("12345" in n for n in names)
