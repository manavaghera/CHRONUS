import json
import time

from services import access


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
