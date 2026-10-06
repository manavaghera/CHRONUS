"""
Access control, sessions, MFA, audit trail, notifications, search presets and
basic performance instrumentation for CHRONUS operational endpoints.
"""

from __future__ import annotations

import base64
import csv
import hashlib
import hmac
import json
import os
import secrets
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
AUDIT_LOG_PATH = ROOT / "audit_log.jsonl"
QA_LOG_PATH = ROOT / "qa_log.jsonl"

SESSION_TTL_SECONDS = 60 * 60
LOGIN_WINDOW_SECONDS = 5 * 60
LOGIN_MAX_FAILURES = 5
LOGIN_BLOCK_SECONDS = 5 * 60

_SESSION_SECRET = os.getenv("CHRONUS_SESSION_SECRET", "chronus-dev-only-secret-change-me").encode("utf-8")
ADMIN_BOOTSTRAP_PASSWORD = os.getenv("CHRONUS_ADMIN_PASSWORD", "admin123!")
ANALYST_BOOTSTRAP_PASSWORD = os.getenv("CHRONUS_ANALYST_PASSWORD", "analyst123!")


ROLE_PERMISSIONS = {
    "admin": {
        "auth.mfa.manage",
        "audit.read",
        "notifications.read",
        "notifications.write",
        "search.logs.read",
        "search.presets.read",
        "search.presets.write",
        "bulk.logs.export",
        "analytics.read",
    },
    "analyst": {
        "notifications.read",
        "notifications.write",
        "search.logs.read",
        "search.presets.read",
        "search.presets.write",
        "bulk.logs.export",
        "analytics.read",
    },
    "user": {
        "notifications.read",
        "notifications.write",
        "search.presets.read",
        "search.presets.write",
    },
}


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


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * ((4 - len(data) % 4) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("ascii"))


def _sign(blob: bytes) -> str:
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
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


_users = {
    "admin": {
        "username": "admin",
        "password_hash": _hash_password(ADMIN_BOOTSTRAP_PASSWORD),
        "role": "admin",
        "mfa_enabled": False,
        "mfa_secret": None,
        "backup_code_hashes": [],
        "disabled": False,
    },
    "analyst": {
        "username": "analyst",
        "password_hash": _hash_password(ANALYST_BOOTSTRAP_PASSWORD),
        "role": "analyst",
        "mfa_enabled": False,
        "mfa_secret": None,
        "backup_code_hashes": [],
        "disabled": False,
    },
}

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
            code_hash = _hash_backup_code(backup_code.strip().upper())
            codes = user.get("backup_code_hashes", [])
            if code_hash not in codes:
                retry_after = _register_failure(username, client_id)
                return LoginResult(ok=False, message="Invalid backup code.", retry_after=retry_after)
            user["backup_code_hashes"] = [c for c in codes if c != code_hash]
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
    with AUDIT_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def iter_audit(limit: int = 100, action: str | None = None, actor: str | None = None) -> list[dict[str, Any]]:
    if not AUDIT_LOG_PATH.exists():
        return []
    out = []
    for line in AUDIT_LOG_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
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
    if not QA_LOG_PATH.exists():
        return []
    rows = []
    for line in QA_LOG_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if _matches_qa_filters(item, filters):
            rows.append(item)
    return rows[-limit:][::-1]


def qa_logs_to_csv(rows: list[dict[str, Any]]) -> str:
    columns = ["timestamp", "persona", "mode", "confidence", "faithfulness", "query", "answer", "sources"]
    output: list[str] = []
    from io import StringIO

    io_buf = StringIO()
    writer = csv.DictWriter(io_buf, fieldnames=columns)
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row.get(k, "") for k in columns})
    output.append(io_buf.getvalue())
    return "".join(output)


def record_timing(metric: str, duration_ms: float) -> None:
    _timings_ms[metric].append(float(duration_ms))


def timing_summary() -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for metric, values in _timings_ms.items():
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
    _cache[key] = (time.time() + ttl_seconds, value)


def cache_stats() -> dict[str, int]:
    now = time.time()
    expired = [k for k, (exp, _) in _cache.items() if exp <= now]
    for key in expired:
        _cache.pop(key, None)
    return {"entries": len(_cache)}
