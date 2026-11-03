from __future__ import annotations

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

# D-A4: the panel is a same-origin SPA; scripts are built assets only, fonts are self-hosted.
# `style-src 'unsafe-inline'` is required by React/Recharts inline style attributes.
PANEL_CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)

COMMON_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}

# Swagger UI loads its JS/CSS from a public CDN; `default-src 'self'` would break `/docs`.
NO_CSP_PATHS = frozenset({"/docs", "/openapi.json", "/redoc", "/docs/oauth2-redirect"})


def _is_api_path(path: str) -> bool:
    return path == "/api" or path.startswith("/api/")


class SecurityHeadersMiddleware:
    """Outermost middleware: decorate every response, including error and limit responses.

    It must be added *after* `BodyLimitMiddleware` so that body-too-large responses (written by
    that middleware's own ASGI backstop) also carry the security headers.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        api_request = _is_api_path(path)
        panel_scope = not api_request and path not in NO_CSP_PATHS
        is_asset = path == "/assets" or path.startswith("/assets/")
        admin_api = path == "/api/admin" or path.startswith("/api/admin/")

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in COMMON_HEADERS.items():
                    headers[name] = value
                # CSP belongs to the panel document and its assets only (D-A4); API and
                # health responses stay untouched.
                content_type = headers.get("content-type", "")
                if panel_scope and (is_asset or content_type.startswith("text/html")):
                    headers["Content-Security-Policy"] = PANEL_CSP
                if admin_api and not headers.get("cache-control"):
                    headers["Cache-Control"] = "no-store"
            await send(message)

        await self.app(scope, receive, send_with_headers)
