from __future__ import annotations

import json
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send


class BodyTooLarge(Exception):
    """Raised when a request body exceeds the configured byte cap."""


def _contains_body_too_large(exc: BaseException) -> bool:
    if isinstance(exc, BodyTooLarge):
        return True
    if isinstance(exc, BaseExceptionGroup):
        return any(_contains_body_too_large(item) for item in exc.exceptions)
    return False


class BodyLimitMiddleware:
    """Count request bytes as they stream in, covering chunked bodies without Content-Length."""

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        received = 0
        response_started = False

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise BodyTooLarge()
            return message

        async def wrapped_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, wrapped_send)
        except BaseExceptionGroup as group:
            # Starlette's BaseHTTPMiddleware wraps receive-task failures in an ExceptionGroup.
            if not _contains_body_too_large(group):
                raise
            await _send_too_large(scope, send, response_started)
        except BodyTooLarge:
            await _send_too_large(scope, send, response_started)


async def _send_too_large(scope: Scope, send: Send, response_started: bool) -> None:
    # The FastAPI exception handler normally turns this into the standard envelope.
    # This branch is a backstop for reads that happen outside the app's handler stack.
    if response_started:
        raise RuntimeError("response already started before body limit error")
    state: Any = scope.get("state")
    request_id = ""
    if isinstance(state, dict):
        request_id = str(state.get("request_id", ""))
    body = json.dumps(
        {
            "request_id": request_id,
            "error": {
                "code": "BAD_REQUEST",
                "message": "request body exceeds the size limit",
            },
        },
        ensure_ascii=False,
    ).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": 400,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send({"type": "http.response.body", "body": body})
