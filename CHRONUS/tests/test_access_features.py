import time

from services import access


def _login(client, username="admin", pw=None, **extra):
    body = {
        "username": username,
        "password": pw or access.ADMIN_BOOTSTRAP_PASSWORD,
        **extra,
    }
    return client.post("/auth/login", json=body)


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": "Bearer " + token}


def test_auth_session_lifecycle(client):
    r = _login(client)
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]

    me = client.get("/auth/me", headers=_auth_header(token))
    assert me.status_code == 200 and me.json()["username"] == "admin"

    out = client.post("/auth/logout", headers=_auth_header(token))
    assert out.status_code == 200

    me_after = client.get("/auth/me", headers=_auth_header(token))
    assert me_after.status_code == 401


def test_login_rate_limit_returns_retry_after(client):
    for _ in range(4):
        bad = _login(client, pw="wrong-pw")
        assert bad.status_code == 401
    blocked = _login(client, pw="wrong-pw")
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers


def test_mfa_enable_and_login_with_totp(client):
    access.disable_mfa("admin")
    ok = _login(client)
    token = ok.json()["access_token"]

    setup = client.post("/auth/mfa/enable", headers=_auth_header(token))
    assert setup.status_code == 200, setup.text
    secret = setup.json()["secret"]
    code = access._totp(secret, int(time.time()))

    client.post("/auth/logout", headers=_auth_header(token))

    needs_mfa = _login(client)
    assert needs_mfa.status_code == 401
    assert "MFA required" in needs_mfa.json()["detail"]

    mfa_login = _login(client, otp_code=code)
    assert mfa_login.status_code == 200, mfa_login.text

    access.disable_mfa("admin")


def test_notifications_presets_export_and_analytics(client):
    r = _login(client)
    token = r.json()["access_token"]
    headers = _auth_header(token)

    preset = client.post("/search/presets", json={"name": "default", "filters": {"mode": "mix_method"}}, headers=headers)
    assert preset.status_code == 200

    listed = client.get("/search/presets", headers=headers)
    assert listed.status_code == 200 and "default" in listed.json()["presets"]

    notes = client.get("/notifications", headers=headers)
    assert notes.status_code == 200

    exported = client.post("/bulk/export/logs", headers=headers)
    assert exported.status_code == 200 and exported.headers["content-type"].startswith("text/csv")

    dashboard = client.get("/analytics/dashboard", headers=headers)
    assert dashboard.status_code == 200

    audit = client.get("/audit", headers=headers)
    assert audit.status_code == 200
