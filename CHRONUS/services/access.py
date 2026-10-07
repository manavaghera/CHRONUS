"""
Who may talk to the server, and how often.

1. Host check: only requests addressed to an allowed host name are served
   (config.ALLOWED_HOSTS). Stops DNS rebinding, where a website points its
   own domain at 127.0.0.1 and then reads this server as "same origin".
2. Cross-site writes: POST/PUT/PATCH/DELETE sent by another website are
   refused (Origin / Sec-Fetch-Site headers). JSON bodies already force a
   preflight, but bodyless posts and form uploads don't; this covers them all.
3. Sign-in (optional):
   * one shared access code (CHRONUS_ACCESS_CODE), or
   * accounts (CHRONUS_USERS="asha:code1,ravi:code2"): each person signs in
     with a name and code, and sees only the custom models they made
     (services/personas.py current_user). Pretrained models are shared.
   Every API call then needs the chronus_access cookie from POST
   /auth/login: a random session id kept on the server (it used to be a
   plain hash of the code, so a 4-digit code came back from a copied cookie
   in milliseconds, it never expired, and logging out didn't stop a copy).
   Sessions last SESSION_DAYS, end at logout or when that code changes, and
   the cookie is Secure over HTTPS. A restart signs everyone out. The
   website's files and /health stay public so the sign-in screen can load.
4. Rate limit: expensive endpoints (chat, voice) allow RATE_LIMIT_PER_MIN
   requests per client per minute (CHRONUS_RATE_LIMIT, 0 = all limits off).
   Heavy ones (uploads, builds, cloud voice, bundle import/export,
   transcription, follow-ups) also have a tighter limit
   (CHRONUS_HEAVY_RATE_LIMIT) and at most CHRONUS_MAX_HEAVY run at once.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import threading
import time
from collections import defaultdict, deque
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from services import personas as ps

COOKIE = "chronus_access"
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
# Paths that work without the access code: the website itself and login
PUBLIC_PREFIXES = ("/health", "/ready", "/auth/", "/assets/", "/favicon")
PUBLIC_PATHS = {"/", "/index.html"}
# Endpoints that cost real compute or API credit
LIMITED_PREFIXES = ("/chat", "/speak", "/voice", "/roundtable")
# Each call embeds documents, derives a key (bundles: memory-heavy scrypt),
# transcribes audio, or calls a cloud service
HEAVY_PATHS = re.compile(
    r"^/(?:transcribe|personas/import|personas/[^/]+/(?:documents(?:/async)?|build|voice|export|followup))$"
)
LOGIN_FAILURES_PER_MIN = 10  # per client address
SESSION_DAYS = 30
MAX_SESSIONS = 10_000


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _rate_limit() -> int:
    return _env_int("CHRONUS_RATE_LIMIT", 30)


def _heavy_rate_limit() -> int:
    return 0 if _rate_limit() <= 0 else _env_int("CHRONUS_HEAVY_RATE_LIMIT", 10)


class LoginBody(BaseModel):
    code: str = Field(min_length=1, max_length=200)
    user: str | None = Field(default=None, max_length=40)


# Only on this server, never sent to a browser: lets a session notice that its
# code was changed (which signs that account out)
_FINGERPRINT_KEY = secrets.token_bytes(32)


def _fingerprint(code: str, user: str | None) -> str:
    return hmac.new(_FINGERPRINT_KEY, f"{user or ''}:{code}".encode(), hashlib.sha256).hexdigest()


class _Sessions:
    """Signed-in browsers: random ids, so the cookie reveals nothing about the code."""

    def __init__(self):
        self.items: dict[str, dict] = {}
        self.lock = threading.Lock()

    def create(self, user: str | None, code: str) -> str:
        token = secrets.token_urlsafe(32)
        now = time.time()
        with self.lock:
            if len(self.items) >= MAX_SESSIONS:
                for old in [t for t, s in self.items.items() if s["expires"] < now] or sorted(
                        self.items, key=lambda t: self.items[t]["expires"])[:len(self.items) // 10]:
                    del self.items[old]
            self.items[token] = {"user": user, "fp": _fingerprint(code, user), "expires": now + SESSION_DAYS * 86400}
        return token

    def get(self, token: str) -> dict | None:
        with self.lock:
            session = self.items.get(token or "")
            if session and session["expires"] < time.time():
                del self.items[token]
                return None
            return session

    def revoke(self, token: str) -> None:
        with self.lock:
            self.items.pop(token or "", None)


sessions = _Sessions()


def users(config) -> dict[str, str]:
    """{name: code} from config.USERS ("asha:code1,ravi:code2")."""
    out = {}
    for item in (config.USERS or "").split(","):
        name, _, code = item.strip().partition(":")
        if name.strip() and code.strip():
            out[name.strip().lower()] = code.strip()
    return out


def signed_in_as(request: Request, config) -> tuple[bool, str | None]:
    """(allowed, account name) for this request's session cookie."""
    accounts = users(config)
    if not accounts and not config.ACCESS_CODE:
        return True, None
    session = sessions.get(request.cookies.get(COOKIE, ""))
    if session is None:
        return False, None
    name = session["user"]
    code = accounts.get(name) if accounts else (config.ACCESS_CODE if name is None else None)
    # A changed code (or a removed account) ends its sessions
    if not code or not hmac.compare_digest(session["fp"], _fingerprint(code, name)):
        return False, None
    return True, name


def _secure_cookie(request: Request) -> bool:
    return request.url.scheme == "https" or os.getenv("CHRONUS_COOKIE_SECURE") == "1"


class _Limiter:
    def __init__(self):
        self.hits: dict[str, deque] = defaultdict(deque)
        self.lock = threading.Lock()

    def _recent(self, key: str, window: float, now: float) -> deque:
        q = self.hits[key]
        while q and now - q[0] > window:
            q.popleft()
        return q

    def allow(self, key: str, limit: int, window: float = 60.0) -> bool:
        """Count one request; False once *limit* were counted in *window*."""
        now = time.monotonic()
        with self.lock:
            q = self._recent(key, window, now)
            if len(q) >= limit:
                return False
            q.append(now)
            return True

    def full(self, key: str, limit: int, window: float = 60.0) -> bool:
        """Has *key* used up its limit? (Doesn't count anything.)"""
        with self.lock:
            return len(self._recent(key, window, time.monotonic())) >= limit

    def hit(self, key: str) -> None:
        with self.lock:
            self.hits[key].append(time.monotonic())


limiter = _Limiter()


class _Slots:
    """At most *n* heavy requests at once; the rest are told to retry."""

    def __init__(self, n: int):
        self.sem = threading.BoundedSemaphore(max(1, n))

    def try_acquire(self) -> bool:
        return self.sem.acquire(blocking=False)

    def release(self) -> None:
        self.sem.release()


heavy_slots = _Slots(_env_int("CHRONUS_MAX_HEAVY", 2))


def _is_cross_site(request: Request, allowed_hosts: list[str]) -> bool:
    if request.headers.get("sec-fetch-site") == "cross-site":
        return True
    origin = request.headers.get("origin")
    if origin is None:
        return False  # not a browser cross-site request (curl, scripts, same-origin GET)
    host = urlsplit(origin).hostname
    return host is None or host not in allowed_hosts


def install(app, config) -> None:
    """Add the host check, cross-site guard, access code and rate limit to *app*."""

    @app.middleware("http")
    async def guard(request: Request, call_next):
        path = request.url.path
        if request.method in UNSAFE_METHODS and _is_cross_site(request, config.ALLOWED_HOSTS):
            return JSONResponse({"detail": "Cross-site requests are not allowed"}, status_code=403)

        allowed, user = signed_in_as(request, config)
        if not allowed and request.method != "OPTIONS" and not (path in PUBLIC_PATHS or path.startswith(PUBLIC_PREFIXES)):
            return JSONResponse({"detail": "Access code required", "login": True}, status_code=401)

        client = request.client.host if request.client else "unknown"
        limit = _rate_limit()
        if limit > 0 and request.method == "POST" and path.startswith(LIMITED_PREFIXES):
            if not limiter.allow(client, limit):
                return JSONResponse({"detail": "Too many requests; please wait a minute"}, status_code=429,
                                    headers={"Retry-After": "60"})
        heavy = request.method == "POST" and bool(HEAVY_PATHS.match(path))
        if heavy:
            heavy_limit = _heavy_rate_limit()
            if heavy_limit > 0 and not limiter.allow(f"heavy:{client}", heavy_limit):
                return JSONResponse({"detail": "Too many uploads or builds; please wait a minute"}, status_code=429,
                                    headers={"Retry-After": "60"})
            if not heavy_slots.try_acquire():
                return JSONResponse({"detail": "The server is busy with other uploads or builds; try again in a moment"},
                                    status_code=503, headers={"Retry-After": "5"})
        # Which account's models this request may see (services/personas.py)
        token = ps.current_user.set(user if allowed else None)
        try:
            return await call_next(request)
        finally:
            ps.current_user.reset(token)
            if heavy:
                heavy_slots.release()

    # Added last so it runs first: unknown Host names never reach anything
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=config.ALLOWED_HOSTS)


def make_router(config) -> APIRouter:
    router = APIRouter(prefix="/auth", tags=["auth"])

    @router.get("/status")
    def status(request: Request):
        accounts = bool(users(config))
        ok, user = signed_in_as(request, config)
        return {"required": accounts or bool(config.ACCESS_CODE), "signed_in": ok, "accounts": accounts,
                "user": user if ok else None}

    @router.post("/login")
    def login(body: LoginBody, request: Request, response: Response):
        accounts = users(config)
        if not accounts and not config.ACCESS_CODE:
            return {"signed_in": True, "user": None}
        client = request.client.host if request.client else "unknown"
        key = f"login:{client}"
        # Only failed attempts count, so signing in often is fine. Checked before
        # the code: a client that has failed too often gets nothing from a right
        # guess. A success doesn't reset the count (that let someone with an
        # account reset it between guesses at another account's code).
        if limiter.full(key, LOGIN_FAILURES_PER_MIN):
            raise HTTPException(status_code=429, detail="Too many attempts; please wait a minute",
                                headers={"Retry-After": "60"})
        if accounts:
            name = (body.user or "").strip().lower()
            expected = accounts.get(name)
            # compare even for unknown names, so timing doesn't reveal which names exist
            ok = hmac.compare_digest(body.code, expected or "\0" * len(body.code)) and bool(expected)
            if not ok:
                limiter.hit(key)
                raise HTTPException(status_code=401, detail="Wrong name or access code")
            token = sessions.create(name, expected)
        else:
            name = None
            if not hmac.compare_digest(body.code, config.ACCESS_CODE):
                limiter.hit(key)
                raise HTTPException(status_code=401, detail="Wrong access code")
            token = sessions.create(None, config.ACCESS_CODE)
        response.set_cookie(COOKIE, token, httponly=True, samesite="strict", max_age=SESSION_DAYS * 86400,
                            secure=_secure_cookie(request))
        return {"signed_in": True, "user": name}

    @router.post("/logout")
    def logout(request: Request, response: Response):
        sessions.revoke(request.cookies.get(COOKIE, ""))  # a copied cookie stops working too
        response.delete_cookie(COOKIE)
        return {"signed_in": False}

    return router
