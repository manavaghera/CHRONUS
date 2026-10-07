"""
Admin / operations endpoints (from PR #2): an admin and an analyst login with
roles, optional MFA (TOTP + one-time backup codes), an audit trail, in-app
notifications, Q&A log search with saved presets, CSV export, and a timing
dashboard. All routes live under /ops.

This is separate from the site's sign-in (services/access.py: access code or
accounts, cookie). Behind an access code or accounts, /ops also needs that
sign-in first.

Off unless configured. Nothing here has a default password or secret:
    CHRONUS_SESSION_SECRET    signs ops session tokens (16+ characters, random)
    CHRONUS_ADMIN_PASSWORD    the "admin" login
    CHRONUS_ANALYST_PASSWORD  optional "analyst" login (no audit log, no MFA)
Without the first two, every /ops route answers 404. (PR #2 shipped
"admin123!" and a secret written in the source, so anyone could log in, or
sign their own admin token, and export every question asked.)

    POST /ops/auth/login        {username, password, otp_code?, backup_code?} -> bearer token (1 hour)
    POST /ops/auth/logout       GET /ops/auth/me
    POST /ops/auth/mfa/enable   POST /ops/auth/mfa/disable           (admin)
    GET  /ops/notifications     POST /ops/notifications/read
    GET  /ops/audit                                                  (admin)
    GET  /ops/search/logs       GET/POST /ops/search/presets
    POST /ops/bulk/export/logs  (CSV)
    GET  /ops/analytics/dashboard  GET /ops/analytics/dashboard.csv

Users, sessions, MFA settings, notifications and presets are kept in memory
(lost on restart); the audit log is a JSON-lines file kept for
LOG_RETENTION_DAYS like the Q&A log.
"""

from __future__ import annotations

import base64
import csv
import hashlib
import hmac
import io
import json
import logging
import os
import secrets
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from services import qa_log

logger = logging.getLogger("chronus")

ROOT = Path(__file__).resolve().parent.parent
AUDIT_LOG_PATH = ROOT / "audit_log.jsonl"
QA_LOG_PATH: Path | None = None  # None = the Q&A log (services/qa_log.py); tests point it elsewhere

SESSION_TTL_SECONDS = 60 * 60
LOGIN_WINDOW_SECONDS = 5 * 60
LOGIN_MAX_FAILURES = 5
LOGIN_BLOCK_SECONDS = 5 * 60
MIN_SECRET_LENGTH = 16
# PR #2's built-in secret: public in the repository, so never accepted
_PUBLISHED_SECRETS = {"chronus-dev-only-secret-change-me"}

ROLE_PERMISSIONS = {
    "admin": {
        "auth.mfa.manage", "audit.read", "notifications.read", "notifications.write", "search.logs.read",
        "search.presets.read", "search.presets.write", "bulk.logs.export", "analytics.read",
    },
    "analyst": {
        "notifications.read", "notifications.write", "search.logs.read", "search.presets.read",
        "search.presets.write", "bulk.logs.export", "analytics.read",
    },
    "user": {"notifications.read", "notifications.write", "search.presets.read", "search.presets.write"},
}

_SESSION_SECRET = b""
ADMIN_BOOTSTRAP_PASSWORD = ""
ANALYST_BOOTSTRAP_PASSWORD = ""
_users: dict[str, dict] = {}
_audit_lock = threading.Lock()
qa_log.retain(lambda: AUDIT_LOG_PATH, _audit_lock)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 200_000)
    return f"{salt}${digest.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        salt, expected = stored.split("$", 1)
    except ValueError:
        return False
    actual = _hash_password(password, salt).split("$", 1)[1]
    return hmac.compare_digest(actual, expected)


def _new_user(username: str, password: str, role: str) -> dict:
    return {"username": username, "password_hash": _hash_password(password), "role": role, "mfa_enabled": False,
            "mfa_secret": None, "backup_code_hashes": [], "disabled": False}


def configure(secret: str | None = None, admin_password: str | None = None, analyst_password: str | None = None) -> bool:
    """(Re)load the ops settings, from the arguments or the environment.
    Returns whether /ops is on."""
    global _SESSION_SECRET, ADMIN_BOOTSTRAP_PASSWORD, ANALYST_BOOTSTRAP_PASSWORD
    secret = os.getenv("CHRONUS_SESSION_SECRET", "") if secret is None else secret
    admin_password = os.getenv("CHRONUS_ADMIN_PASSWORD", "") if admin_password is None else admin_password
    analyst_password = os.getenv("CHRONUS_ANALYST_PASSWORD", "") if analyst_password is None else analyst_password
    if secret and (secret in _PUBLISHED_SECRETS or len(secret) < MIN_SECRET_LENGTH):
        logger.warning(f"CHRONUS_SESSION_SECRET is too short or published; /ops stays off (use {MIN_SECRET_LENGTH}+ random characters)")
        secret = ""
    _SESSION_SECRET = secret.encode("utf-8")
    ADMIN_BOOTSTRAP_PASSWORD, ANALYST_BOOTSTRAP_PASSWORD = admin_password, analyst_password
    _users.clear()
    if secret and admin_password:
        _users["admin"] = _new_user("admin", admin_password, "admin")
        if analyst_password:
            _users["analyst"] = _new_user("analyst", analyst_password, "analyst")
    _revoked_jtis.clear()
    _login_failures.clear()
    _login_blocks.clear()
    return enabled()


def enabled() -> bool:
    return bool(_SESSION_SECRET) and "admin" in _users


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * ((4 - len(data) % 4) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("ascii"))


def _sign(blob: bytes) -> str:
    if not _SESSION_SECRET:
        raise ValueError("Ops sessions are off")
    return _b64url(hmac.new(_SESSION_SECRET, blob, hashlib.sha256).digest())


def _make_token(payload: dict[str, Any]) -> str:
    body = _b64url(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    return f"{body}.{_sign(body.encode('utf-8'))}"


def _decode_token(token: str) -> dict[str, Any]:
    body, sig = token.split(".", 1)
    expected = _sign(body.encode("utf-8"))
    if not hmac.compare_digest(sig, expected):
        raise ValueError("Invalid token signature")
    return json.loads(_b64url_decode(body).decode("utf-8"))


def _totp(secret_b32: str, ts: int | None = None, digits: int = 6, step: int = 30) -> str:
    ts = ts or int(time.time())
    counter = ts // step
    key = base64.b32decode(secret_b32.upper())
    msg = counter.to_bytes(8, "big")
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = ((digest[offset] & 0x7F) << 24) | ((digest[offset + 1] & 0xFF) << 16) | ((digest[offset + 2] & 0xFF) << 8) | (
        digest[offset + 3] & 0xFF
    )
    return str(code % (10**digits)).zfill(digits)


def _verify_totp(secret_b32: str, code: str, drift_steps: int = 1) -> bool:
    now = int(time.time())
    for offset in range(-drift_steps, drift_steps + 1):
        if hmac.compare_digest(_totp(secret_b32, now + (offset * 30)), code):
            return True
    return False


def _generate_backup_codes() -> list[str]:
    return [secrets.token_hex(4).upper() for _ in range(8)]


def _hash_backup_code(code: str) -> str:
    return _hash_password(code)


def _consume_backup_code(user: dict, code: str) -> bool:
    normalized = code.strip().upper()
    codes = list(user.get("backup_code_hashes", []))
    for idx, stored in enumerate(codes):
        if _verify_password(normalized, stored):
            del codes[idx]
            user["backup_code_hashes"] = codes
            return True
    return False


_revoked_jtis: set[str] = set()
_login_failures: dict[str, deque[float]] = defaultdict(deque)
_login_blocks: dict[str, float] = {}
_notifications: dict[str, list[dict[str, Any]]] = defaultdict(list)
_next_notification_id = 1
_saved_search_presets: dict[str, dict[str, dict[str, str]]] = defaultdict(dict)

_timings_ms: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=500))


@dataclass
class LoginResult:
    ok: bool
    message: str
    token: str | None = None
    expires_at: str | None = None
    retry_after: int | None = None
    user: dict | None = None


def has_permission(role: str, permission: str) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, set())


def issue_session(username: str, role: str) -> tuple[str, str]:
    exp = int(time.time()) + SESSION_TTL_SECONDS
    payload = {"sub": username, "role": role, "exp": exp, "jti": secrets.token_hex(12)}
    token = _make_token(payload)
    return token, datetime.fromtimestamp(exp, tz=timezone.utc).isoformat()


def parse_session(token: str) -> dict[str, Any]:
    payload = _decode_token(token)
    if payload.get("jti") in _revoked_jtis:
        raise ValueError("Session already logged out")
    if int(payload.get("exp", 0)) <= int(time.time()):
        raise ValueError("Session expired")
    user = _users.get(payload.get("sub", ""))
    if not user or user.get("disabled") or user["role"] != payload.get("role"):
        raise ValueError("Unknown user")
    return payload


def revoke_session(token: str) -> None:
    payload = _decode_token(token)
    if payload.get("jti"):
        _revoked_jtis.add(payload["jti"])


def _failure_key(username: str, client_id: str) -> str:
    return f"{username}|{client_id}"


def _cleanup_failures(failures: deque[float], now_ts: float) -> None:
    cutoff = now_ts - LOGIN_WINDOW_SECONDS
    while failures and failures[0] < cutoff:
        failures.popleft()


def _register_failure(username: str, client_id: str) -> int | None:
    now_ts = time.time()
    key = _failure_key(username, client_id)
    failures = _login_failures[key]
    _cleanup_failures(failures, now_ts)
    failures.append(now_ts)
    if len(failures) >= LOGIN_MAX_FAILURES:
        until = now_ts + LOGIN_BLOCK_SECONDS
        _login_blocks[key] = until
        return int(until - now_ts)
    return None


def _clear_login_failures(username: str, client_id: str) -> None:
    key = _failure_key(username, client_id)
    _login_failures.pop(key, None)
    _login_blocks.pop(key, None)


def login(username: str, password: str, client_id: str, otp_code: str | None = None, backup_code: str | None = None) -> LoginResult:
    now_ts = time.time()
    key = _failure_key(username, client_id)
    # Checked before the password, so a blocked client learns nothing from a right guess
    blocked_until = _login_blocks.get(key)
    if blocked_until and blocked_until > now_ts:
        return LoginResult(ok=False, message="Too many failed login attempts. Try again later.", retry_after=int(blocked_until - now_ts))

    user = _users.get(username)
    if not user or user.get("disabled"):
        retry_after = _register_failure(username, client_id)
        return LoginResult(ok=False, message="Invalid credentials.", retry_after=retry_after)
    if not _verify_password(password, user["password_hash"]):
        retry_after = _register_failure(username, client_id)
        return LoginResult(ok=False, message="Invalid credentials.", retry_after=retry_after)

    if user.get("mfa_enabled"):
        if otp_code:
            if not (user.get("mfa_secret") and _verify_totp(user["mfa_secret"], otp_code)):
                retry_after = _register_failure(username, client_id)
                return LoginResult(ok=False, message="Invalid one-time code.", retry_after=retry_after)
        elif backup_code:
            if not _consume_backup_code(user, backup_code):
                retry_after = _register_failure(username, client_id)
                return LoginResult(ok=False, message="Invalid backup code.", retry_after=retry_after)
        else:
            return LoginResult(ok=False, message="MFA required: provide otp_code or backup_code.")

    _clear_login_failures(username, client_id)
    token, expires = issue_session(username, user["role"])
    return LoginResult(ok=True, message="Login successful.", token=token, expires_at=expires, user={"username": username, "role": user["role"]})


def enable_mfa(username: str) -> dict[str, Any]:
    user = _users.get(username)
    if not user:
        raise ValueError("Unknown user")
    secret = base64.b32encode(secrets.token_bytes(10)).decode("ascii").rstrip("=")
    backup_codes = _generate_backup_codes()
    user["mfa_enabled"] = True
    user["mfa_secret"] = secret
    user["backup_code_hashes"] = [_hash_backup_code(code) for code in backup_codes]
    uri = f"otpauth://totp/CHRONUS:{username}?secret={secret}&issuer=CHRONUS"
    return {"secret": secret, "otpauth_uri": uri, "backup_codes": backup_codes}


def disable_mfa(username: str) -> None:
    user = _users.get(username)
    if not user:
        raise ValueError("Unknown user")
    user["mfa_enabled"] = False
    user["mfa_secret"] = None
    user["backup_code_hashes"] = []


def mfa_status(username: str) -> dict[str, Any]:
    user = _users.get(username)
    if not user:
        raise ValueError("Unknown user")
    return {"enabled": bool(user.get("mfa_enabled")), "backup_codes_remaining": len(user.get("backup_code_hashes", []))}


def record_audit(action: str, actor: str, outcome: str, details: dict[str, Any] | None = None) -> None:
    entry = {
        "timestamp": _utc_now().isoformat(),
        "action": action,
        "actor": actor,
        "outcome": outcome,
        "details": details or {},
    }
    with _audit_lock, AUDIT_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def iter_audit(limit: int = 100, action: str | None = None, actor: str | None = None) -> list[dict[str, Any]]:
    if not AUDIT_LOG_PATH.exists():
        return []
    out = []
    with _audit_lock:
        lines = AUDIT_LOG_PATH.read_text(encoding="utf-8").splitlines()
    for line in lines:
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if action and item.get("action") != action:
            continue
        if actor and item.get("actor") != actor:
            continue
        out.append(item)
    return out[-limit:][::-1]


def create_notification(username: str, title: str, body: str, level: str = "info") -> dict[str, Any]:
    global _next_notification_id
    row = {
        "id": _next_notification_id,
        "title": title,
        "body": body,
        "level": level,
        "read": False,
        "created_at": _utc_now().isoformat(),
    }
    _next_notification_id += 1
    _notifications[username].append(row)
    return row


def list_notifications(username: str, unread_only: bool = False, limit: int = 100) -> list[dict[str, Any]]:
    rows = _notifications.get(username, [])
    if unread_only:
        rows = [r for r in rows if not r["read"]]
    return rows[-limit:][::-1]


def mark_notifications_read(username: str, ids: list[int] | None = None) -> int:
    rows = _notifications.get(username, [])
    count = 0
    wanted = set(ids or [])
    for row in rows:
        if ids is None or row["id"] in wanted:
            if not row["read"]:
                row["read"] = True
                count += 1
    return count


def save_search_preset(username: str, name: str, filters: dict[str, str]) -> None:
    _saved_search_presets[username][name] = filters


def list_search_presets(username: str) -> dict[str, dict[str, str]]:
    return _saved_search_presets.get(username, {})


def _matches_qa_filters(item: dict[str, Any], filters: dict[str, str]) -> bool:
    query_text = filters.get("query")
    persona = filters.get("persona")
    mode = filters.get("mode")
    confidence = filters.get("confidence")
    if query_text and query_text.lower() not in item.get("query", "").lower():
        return False
    if persona and item.get("persona") != persona:
        return False
    if mode and item.get("mode") != mode:
        return False
    if confidence and item.get("confidence") != confidence:
        return False
    return True


def search_qa_logs(filters: dict[str, str], limit: int = 100) -> list[dict[str, Any]]:
    rows = [e for e in qa_log.read_entries(path=QA_LOG_PATH) if _matches_qa_filters(e, filters)]
    return rows[-limit:][::-1]


def qa_logs_to_csv(rows: list[dict[str, Any]]) -> str:
    columns = ["timestamp", "persona", "mode", "confidence", "faithfulness", "query", "answer", "sources"]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=columns)
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row.get(k, "") for k in columns})
    return buf.getvalue()


def record_timing(metric: str, duration_ms: float) -> None:
    _timings_ms[metric].append(float(duration_ms))


def timing_summary() -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for metric, values in list(_timings_ms.items()):
        if not values:
            continue
        ordered = sorted(values)
        p95_idx = min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))
        out[metric] = {
            "count": len(values),
            "avg_ms": round(mean(values), 2),
            "p95_ms": round(ordered[p95_idx], 2),
            "max_ms": round(max(values), 2),
        }
    return out


def route_metric(request: Request) -> str:
    """Timing name for a request: its route template (/personas/{persona_id}),
    so arbitrary URLs can't create unbounded metric names."""
    route = request.scope.get("route")
    return f"http.{request.method}:{getattr(route, 'path', 'other')}"


_cache: dict[str, tuple[float, Any]] = {}


def cache_get(key: str) -> Any | None:
    row = _cache.get(key)
    if not row:
        return None
    expires_at, value = row
    if expires_at <= time.time():
        _cache.pop(key, None)
        return None
    return value


def cache_set(key: str, value: Any, ttl_seconds: int = 30) -> None:
    cache_stats()  # drop expired entries
    _cache[key] = (time.time() + ttl_seconds, value)


def cache_stats() -> dict[str, int]:
    now = time.time()
    expired = [k for k, (exp, _) in list(_cache.items()) if exp <= now]
    for key in expired:
        _cache.pop(key, None)
    return {"entries": len(_cache)}


# ---- HTTP routes ----

class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=200)
    otp_code: str | None = Field(default=None, min_length=6, max_length=8)
    backup_code: str | None = Field(default=None, min_length=8, max_length=32)


class NotificationReadRequest(BaseModel):
    ids: list[int] = Field(default_factory=list, max_length=500)


class SearchPresetRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    filters: dict[str, str] = Field(default_factory=dict)


def _require_enabled() -> None:
    if not enabled():
        raise HTTPException(status_code=404, detail="Ops endpoints are off: set CHRONUS_SESSION_SECRET and CHRONUS_ADMIN_PASSWORD")


def _bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return token


def current_user(authorization: str | None = Header(default=None)) -> dict:
    token = _bearer_token(authorization)
    try:
        payload = parse_session(token)
    except ValueError as e:
        detail = str(e)
        if "expired" in detail.lower():
            detail = "Session expired. Please log in again."
        raise HTTPException(status_code=401, detail=detail)
    return {"username": payload["sub"], "role": payload["role"], "token": token}


def require_permission(permission: str):
    def _guard(user: dict = Depends(current_user)) -> dict:
        if not has_permission(user["role"], permission):
            raise HTTPException(status_code=403, detail=f"Missing permission: {permission}")
        return user
    return _guard


def _filters(query, persona, mode, confidence) -> dict[str, str]:
    return {"query": query or "", "persona": persona or "", "mode": mode or "", "confidence": confidence or ""}


def make_router() -> APIRouter:
    router = APIRouter(prefix="/ops", tags=["ops"], dependencies=[Depends(_require_enabled)])

    @router.post("/auth/login")
    def auth_login(req: LoginRequest, request: Request):
        client_id = request.client.host if request.client else "unknown"
        result = login(req.username, req.password, client_id, otp_code=req.otp_code, backup_code=req.backup_code)
        headers = {}
        if result.retry_after:
            headers["Retry-After"] = str(result.retry_after)
        if not result.ok:
            record_audit("auth.login", req.username, "denied", {"client_id": client_id, "message": result.message})
            raise HTTPException(status_code=429 if result.retry_after else 401, detail=result.message, headers=headers)
        record_audit("auth.login", req.username, "success", {"client_id": client_id})
        create_notification(req.username, "Login successful", "You signed in to CHRONUS.", level="success")
        return {"access_token": result.token, "token_type": "bearer", "expires_at": result.expires_at, "user": result.user}

    @router.post("/auth/logout")
    def auth_logout(user: dict = Depends(current_user)):
        revoke_session(user["token"])
        record_audit("auth.logout", user["username"], "success", {})
        create_notification(user["username"], "Logged out", "Your session was invalidated.", level="info")
        return {"success": True}

    @router.get("/auth/me")
    def auth_me(user: dict = Depends(current_user)):
        return {"username": user["username"], "role": user["role"], "mfa": mfa_status(user["username"])}

    @router.post("/auth/mfa/enable")
    def auth_enable_mfa(user: dict = Depends(require_permission("auth.mfa.manage"))):
        setup = enable_mfa(user["username"])
        record_audit("auth.mfa.enable", user["username"], "success", {})
        create_notification(user["username"], "MFA enabled", "Two-factor authentication is now active.", level="warning")
        return setup

    @router.post("/auth/mfa/disable")
    def auth_disable_mfa(user: dict = Depends(require_permission("auth.mfa.manage"))):
        disable_mfa(user["username"])
        record_audit("auth.mfa.disable", user["username"], "success", {})
        create_notification(user["username"], "MFA disabled", "Two-factor authentication was turned off.", level="warning")
        return {"success": True}

    @router.get("/notifications")
    def notifications(unread_only: bool = False, limit: int = Query(default=100, ge=1, le=500),
                      user: dict = Depends(require_permission("notifications.read"))):
        rows = list_notifications(user["username"], unread_only=unread_only, limit=limit)
        return {"items": rows, "count": len(rows)}

    @router.post("/notifications/read")
    def notifications_read(req: NotificationReadRequest, user: dict = Depends(require_permission("notifications.write"))):
        ids = req.ids or None
        count = mark_notifications_read(user["username"], ids=ids)
        record_audit("notifications.read", user["username"], "success", {"count": count, "bulk": ids is None})
        return {"updated": count}

    @router.get("/audit")
    def get_audit(limit: int = Query(default=100, ge=1, le=500), action: str | None = None, actor: str | None = None,
                  user: dict = Depends(require_permission("audit.read"))):
        rows = iter_audit(limit=limit, action=action, actor=actor)
        record_audit("audit.read", user["username"], "success", {"limit": limit})
        return {"items": rows, "count": len(rows)}

    @router.get("/search/logs")
    def search_logs(query: str | None = None, persona: str | None = None, mode: str | None = None,
                    confidence: str | None = None, preset: str | None = None,
                    limit: int = Query(default=100, ge=1, le=1000),
                    user: dict = Depends(require_permission("search.logs.read"))):
        filters = _filters(query, persona, mode, confidence)
        if preset:
            preset_filters = list_search_presets(user["username"]).get(preset)
            if not preset_filters:
                raise HTTPException(status_code=404, detail=f"Unknown preset '{preset}'")
            filters = preset_filters
        cache_key = f"search:{user['username']}:{json.dumps(filters, sort_keys=True)}:{limit}"
        rows = cache_get(cache_key)
        if rows is None:
            t0 = time.perf_counter()
            rows = search_qa_logs(filters=filters, limit=limit)
            record_timing("search.logs", (time.perf_counter() - t0) * 1000)
            cache_set(cache_key, rows, ttl_seconds=20)
        record_audit("search.logs", user["username"], "success", {"filters": filters, "limit": limit})
        return {"items": rows, "count": len(rows), "filters": filters}

    @router.post("/search/presets")
    def save_preset(req: SearchPresetRequest, user: dict = Depends(require_permission("search.presets.write"))):
        save_search_preset(user["username"], req.name, req.filters)
        record_audit("search.presets.write", user["username"], "success", {"name": req.name})
        return {"success": True}

    @router.get("/search/presets")
    def search_presets(user: dict = Depends(require_permission("search.presets.read"))):
        return {"presets": list_search_presets(user["username"])}

    @router.post("/bulk/export/logs")
    def bulk_export_logs(query: str | None = None, persona: str | None = None, mode: str | None = None,
                         confidence: str | None = None, limit: int = Query(default=200, ge=1, le=5000),
                         user: dict = Depends(require_permission("bulk.logs.export"))):
        filters = _filters(query, persona, mode, confidence)
        rows = search_qa_logs(filters=filters, limit=limit)
        record_audit("bulk.logs.export", user["username"], "success", {"rows": len(rows), "filters": filters})
        return Response(content=qa_logs_to_csv(rows), media_type="text/csv",
                        headers={"Content-Disposition": "attachment; filename=qa_logs.csv"})

    def dashboard() -> dict:
        recent = search_qa_logs(filters={}, limit=200)
        by_mode: dict[str, int] = {}
        by_confidence: dict[str, int] = {}
        for row in recent:
            by_mode[row.get("mode", "unknown")] = by_mode.get(row.get("mode", "unknown"), 0) + 1
            by_confidence[row.get("confidence", "unknown")] = by_confidence.get(row.get("confidence", "unknown"), 0) + 1
        return {"qa_total": len(recent), "qa_by_mode": by_mode, "qa_by_confidence": by_confidence,
                "performance": timing_summary(), "cache": cache_stats(), "generated_at": datetime.now().isoformat()}

    @router.get("/analytics/dashboard")
    def analytics_dashboard(user: dict = Depends(require_permission("analytics.read"))):
        return dashboard()

    @router.get("/analytics/dashboard.csv")
    def analytics_dashboard_csv(user: dict = Depends(require_permission("analytics.read"))):
        data = dashboard()
        rows = [{"metric": "qa_total", "value": str(data["qa_total"])},
                {"metric": "cache_entries", "value": str(data["cache"]["entries"])}]
        rows += [{"metric": f"qa_mode_{k}", "value": str(v)} for k, v in data["qa_by_mode"].items()]
        rows += [{"metric": f"qa_confidence_{k}", "value": str(v)} for k, v in data["qa_by_confidence"].items()]
        for metric, detail in data["performance"].items():
            rows.append({"metric": f"{metric}_avg_ms", "value": str(detail["avg_ms"])})
            rows.append({"metric": f"{metric}_p95_ms", "value": str(detail["p95_ms"])})
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=["metric", "value"])
        writer.writeheader()
        writer.writerows(rows)
        record_audit("analytics.download", user["username"], "success", {"rows": len(rows)})
        return Response(content=buf.getvalue(), media_type="text/csv",
                        headers={"Content-Disposition": "attachment; filename=dashboard.csv"})

    return router


configure()
