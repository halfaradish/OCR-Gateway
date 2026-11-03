from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from starlette.datastructures import MutableHeaders
from starlette.staticfiles import StaticFiles
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.api.deps import ApiError

logger = logging.getLogger(__name__)

PANEL_MISSING_CODE = "FRONTEND_NOT_BUILT"
PANEL_MISSING_MESSAGE = "panel assets are not built; run pnpm build or use an image with the panel"

# D-A4: these prefixes always answer with JSON 404 instead of the SPA entry point, so an unknown
# API route never turns into an HTML page.
NON_PANEL_PREFIXES = ("api", "v1", "healthz")

ASSET_CACHE = "public, max-age=31536000, immutable"
ROOT_FILE_CACHE = "public, max-age=3600"


def _looks_like_api(path: str) -> bool:
    stripped = path.lstrip("/")
    return any(
        stripped == prefix or stripped.startswith(prefix + "/")
        for prefix in NON_PANEL_PREFIXES
    )


class ImmutableStatic:
    """Serve hashed build assets with a long-lived immutable cache header."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        async def send_with_cache(message: Message) -> None:
            if message["type"] == "http.response.start" and message["status"] == 200:
                MutableHeaders(scope=message)["Cache-Control"] = ASSET_CACHE
            await send(message)

        await self.app(scope, receive, send_with_cache)


def _resolve_within(root: Path, relative: str) -> Path | None:
    """Resolve a request path inside `root`; return None on traversal or missing files."""
    if not relative or "\x00" in relative:
        return None
    try:
        candidate = (root / relative).resolve()
    except OSError:  # pragma: no cover - defensive: unreadable path
        return None
    if candidate != root and root not in candidate.parents:
        return None
    return candidate if candidate.is_file() else None


def _panel_missing(request: Request) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={
            "request_id": getattr(request.state, "request_id", ""),
            "error": {"code": PANEL_MISSING_CODE, "message": PANEL_MISSING_MESSAGE},
        },
    )


def _index_response(index_path: Path, fallback: bytes) -> Response:
    # Read per request: a rebuild must not leave the process serving an HTML shell that
    # references hashed assets this build already deleted.
    try:
        content = index_path.read_bytes()
    except OSError:
        content = fallback
    return Response(
        content=content,
        media_type="text/html; charset=utf-8",
        headers={"Cache-Control": "no-store"},
    )


def register_panel(app: FastAPI, dist_dir: Path) -> bool:
    """Serve the built single-page panel from `dist_dir`; return whether assets were found.

    The catch-all route is registered after every API router so that it only sees leftovers.
    """
    dist = dist_dir.resolve()
    index_path = dist / "index.html"
    index_bytes = b""
    failure = ""
    try:
        if index_path.is_file():
            index_bytes = index_path.read_bytes()
    except OSError as exc:
        # A broken panel must never take the API down; behave like "not built".
        failure = str(exc)
    if not index_bytes:
        fields = {"frontend_dist": str(dist)}
        if failure:
            fields["reason"] = failure
        logger.warning("admin.panel.static_missing", extra={"extra_fields": fields})

        @app.api_route("/{path:path}", methods=["GET", "HEAD"], include_in_schema=False)
        async def panel_unavailable(path: str, request: Request) -> Response:
            if _looks_like_api(path):
                raise ApiError(404, "NOT_FOUND", "not found")
            return _panel_missing(request)

        return False

    assets_dir = dist / "assets"
    if assets_dir.is_dir():
        app.mount(
            "/assets",
            ImmutableStatic(StaticFiles(directory=str(assets_dir))),
            name="assets",
        )

    @app.api_route("/{path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    async def panel_fallback(path: str, request: Request) -> Response:
        if _looks_like_api(path):
            raise ApiError(404, "NOT_FOUND", "not found")
        if Path(path).name == "index.html":
            return _index_response(index_path, index_bytes)
        candidate = _resolve_within(dist, path)
        if candidate is not None:
            return FileResponse(candidate, headers={"Cache-Control": ROOT_FILE_CACHE})
        # A missing asset must not be answered with the HTML shell.
        if Path(path).suffix:
            raise ApiError(404, "NOT_FOUND", "not found")
        return _index_response(index_path, index_bytes)

    return True
