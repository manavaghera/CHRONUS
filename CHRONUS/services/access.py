"""
Who may talk to the server, and how often.

1. Host check: only requests addressed to an allowed host name are served
   (config.ALLOWED_HOSTS). Stops DNS rebinding, where a website points its
   own domain at 127.0.0.1 and then reads this server as "same origin".
2. Cross-site writes: POST/PUT/PATCH/DELETE sent by another website are
   refused (Origin / Sec-Fetch-Site headers). JSON bodies already force a
   preflight, but bodyless posts and form uploads don't; this covers them all.
3. Access code (optional, config.ACCESS_CODE / CHRONUS_ACCESS_CODE): when set,
   every API call needs the chronus_access cookie from POST /auth/login. The
   website's files and /health stay public so the login screen can load.
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


def _token(code: str) -> str:
    """Cookie value: a hash of the code, so the code itself isn't stored in the browser."""
    return hashlib.sha256(f"chronus:{code}".encode()).hexdigest()


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

        code = config.ACCESS_CODE
        if code and request.method != "OPTIONS" and not (path in PUBLIC_PATHS or path.startswith(PUBLIC_PREFIXES)):
            cookie = request.cookies.get(COOKIE, "")
            if not hmac.compare_digest(cookie, _token(code)):
                return JSONResponse({"detail": "Access code required", "login": True}, status_code=401)

        limit = _rate_limit()
        if limit > 0 and request.method == "POST" and path.startswith(LIMITED_PREFIXES):
            client = request.client.host if request.client else "unknown"
            if not limiter.allow(client, limit):
                return JSONResponse({"detail": "Too many requests; please wait a minute"}, status_code=429,
                                    headers={"Retry-After": "60"})
        return await call_next(request)

    # Added last so it runs first: unknown Host names never reach anything
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=config.ALLOWED_HOSTS)


def make_router(config) -> APIRouter:
    router = APIRouter(prefix="/auth", tags=["auth"])

    @router.get("/status")
    def status(request: Request):
        required = bool(config.ACCESS_CODE)
        ok = not required or hmac.compare_digest(request.cookies.get(COOKIE, ""), _token(config.ACCESS_CODE))
        return {"required": required, "signed_in": ok}

    @router.post("/login")
    def login(body: LoginBody, request: Request, response: Response):
        code = config.ACCESS_CODE
        if not code:
            return {"signed_in": True}
        client = request.client.host if request.client else "unknown"
        if not limiter.allow(f"login:{client}", 10):
            raise HTTPException(status_code=429, detail="Too many attempts; please wait a minute")
        if not hmac.compare_digest(body.code, code):
            raise HTTPException(status_code=401, detail="Wrong access code")
        response.set_cookie(COOKIE, _token(code), httponly=True, samesite="strict", max_age=30 * 24 * 3600)
        return {"signed_in": True}

    @router.post("/logout")
    def logout(response: Response):
        response.delete_cookie(COOKIE)
        return {"signed_in": False}

    return router
