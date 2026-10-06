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
   /auth/login. The website's files and /health stay public so the sign-in
   screen can load.
4. Rate limit: expensive endpoints (chat, voice) allow RATE_LIMIT_PER_MIN
   requests per client per minute (CHRONUS_RATE_LIMIT, 0 = off).
"""

from __future__ import annotations

import hashlib
import hmac
import os
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
PUBLIC_PREFIXES = ("/health", "/auth/", "/assets/", "/favicon")
PUBLIC_PATHS = {"/", "/index.html"}
# Endpoints that cost real compute or API credit
LIMITED_PREFIXES = ("/chat", "/speak", "/voice", "/roundtable")


def _rate_limit() -> int:
    try:
        return int(os.getenv("CHRONUS_RATE_LIMIT", "30"))
    except ValueError:
        return 30


class LoginBody(BaseModel):
    code: str = Field(min_length=1, max_length=200)
    user: str | None = Field(default=None, max_length=40)


def _token(code: str, user: str | None = None) -> str:
    """Cookie value: a hash of the code (and account), so the code itself
    isn't stored in the browser. Changing a code signs that account out."""
    digest = hashlib.sha256(f"chronus:{user or ''}:{code}".encode()).hexdigest()
    return f"{user}.{digest}" if user else digest


def users(config) -> dict[str, str]:
    """{name: code} from config.USERS ("asha:code1,ravi:code2")."""
    out = {}
    for item in (config.USERS or "").split(","):
        name, _, code = item.strip().partition(":")
        if name.strip() and code.strip():
            out[name.strip().lower()] = code.strip()
    return out


def signed_in_as(request: Request, config) -> tuple[bool, str | None]:
    """(allowed, account name) for this request's cookie."""
    cookie = request.cookies.get(COOKIE, "")
    accounts = users(config)
    if accounts:
        name = cookie.split(".", 1)[0] if "." in cookie else ""
        code = accounts.get(name)
        return (bool(code) and hmac.compare_digest(cookie, _token(code, name)), name or None)
    if config.ACCESS_CODE:
        return hmac.compare_digest(cookie, _token(config.ACCESS_CODE)), None
    return True, None


class _Limiter:
    def __init__(self):
        self.hits: dict[str, deque] = defaultdict(deque)
        self.lock = threading.Lock()

    def allow(self, key: str, limit: int, window: float = 60.0) -> bool:
        now = time.monotonic()
        with self.lock:
            q = self.hits[key]
            while q and now - q[0] > window:
                q.popleft()
            if len(q) >= limit:
                return False
            q.append(now)
            return True

    def clear(self, key: str) -> None:
        with self.lock:
            self.hits.pop(key, None)


limiter = _Limiter()


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

        limit = _rate_limit()
        if limit > 0 and request.method == "POST" and path.startswith(LIMITED_PREFIXES):
            client = request.client.host if request.client else "unknown"
            if not limiter.allow(client, limit):
                return JSONResponse({"detail": "Too many requests; please wait a minute"}, status_code=429,
                                    headers={"Retry-After": "60"})
        # Which account's models this request may see (services/personas.py)
        token = ps.current_user.set(user if allowed else None)
        try:
            return await call_next(request)
        finally:
            ps.current_user.reset(token)

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
        if accounts:
            name = (body.user or "").strip().lower()
            expected = accounts.get(name)
            # compare even for unknown names, so timing doesn't reveal which names exist
            ok = hmac.compare_digest(body.code, expected or "\0" * len(body.code)) and bool(expected)
            if not ok:
                if not limiter.allow(key, 10):
                    raise HTTPException(status_code=429, detail="Too many attempts; please wait a minute")
                raise HTTPException(status_code=401, detail="Wrong name or access code")
            token = _token(expected, name)
        else:
            name = None
            if not hmac.compare_digest(body.code, config.ACCESS_CODE):
                if not limiter.allow(key, 10):
                    raise HTTPException(status_code=429, detail="Too many attempts; please wait a minute")
                raise HTTPException(status_code=401, detail="Wrong access code")
            token = _token(config.ACCESS_CODE)
        limiter.clear(key)
        response.set_cookie(COOKIE, token, httponly=True, samesite="strict", max_age=30 * 24 * 3600)
        return {"signed_in": True, "user": name}

    @router.post("/logout")
    def logout(response: Response):
        response.delete_cookie(COOKIE)
        return {"signed_in": False}

    return router
