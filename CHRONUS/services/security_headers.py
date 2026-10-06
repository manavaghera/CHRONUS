"""
Browser security headers on every response.

The website (FRONTEND/chronus-app/dist) is served by this server, so these
headers protect it as well as the API:

* Content-Security-Policy: scripts only from this server (no inline or
  third-party scripts), styles and fonts from here and Google Fonts, audio
  and images from here or blob:/data: (spoken answers are played from
  blobs), requests only to this server, and the page can't be framed.
  The interactive API docs (/docs, /redoc) load Swagger/ReDoc from a CDN
  and get a policy that allows it.
* X-Content-Type-Options: nosniff, so an uploaded or returned file is never
  run as something else.
* X-Frame-Options: DENY (for browsers without frame-ancestors).
* Referrer-Policy: no-referrer: links out (GitHub) and Google Fonts don't
  learn which model page someone had open.
* Permissions-Policy: microphone only for this site (voice input), no
  camera, location or payment.
* Cross-Origin-Opener-Policy: same-origin.
* Strict-Transport-Security, only when the request came over HTTPS.

If the website is hosted somewhere else (VITE_API_BASE), that host sets its
own headers; these still cover the API responses.
"""

from __future__ import annotations

from starlette.datastructures import MutableHeaders

CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' https://fonts.googleapis.com",
    "font-src 'self' https://fonts.gstatic.com",
    "img-src 'self' data: blob:",
    "media-src 'self' data: blob:",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
])
DOCS_CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com",
    "font-src 'self' https://fonts.gstatic.com",
    "img-src 'self' data: https://fastapi.tiangolo.com",
    "worker-src 'self' blob:",
    "connect-src 'self'",
    "object-src 'none'",
    "frame-ancestors 'none'",
])
DOCS_PATHS = ("/docs", "/redoc")

HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "microphone=(self), camera=(), geolocation=(), payment=(), usb=()",
    "Cross-Origin-Opener-Policy": "same-origin",
}


class SecurityHeaders:
    """Plain ASGI middleware (doesn't buffer streamed answers)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        csp = DOCS_CSP if path.startswith(DOCS_PATHS) else CSP
        https = scope.get("scheme") == "https"

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.setdefault("Content-Security-Policy", csp)
                for name, value in HEADERS.items():
                    headers.setdefault(name, value)
                if https:
                    headers.setdefault("Strict-Transport-Security", "max-age=31536000")
            await send(message)

        await self.app(scope, receive, send_with_headers)


def install(app) -> None:
    """Add last, so it wraps everything (refusals from the host check and
    the access guard get the headers too)."""
    app.add_middleware(SecurityHeaders)
