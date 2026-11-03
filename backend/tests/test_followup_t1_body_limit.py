from __future__ import annotations

import json
from typing import Any

from conftest import create_api_key, create_user


def _scope(path: str, headers: dict[str, str]) -> dict[str, Any]:
    return {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("utf-8"),
        "query_string": b"",
        "root_path": "",
        "headers": [(key.lower().encode("latin-1"), value.encode("latin-1")) for key, value in headers.items()],
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
    }


async def _call(application, scope, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    pending = list(chunks)

    async def receive() -> dict[str, Any]:
        if pending:
            return pending.pop(0)
        return {"type": "http.disconnect"}

    async def send(message: dict[str, Any]) -> None:
        messages.append(message)

    await application(scope, receive, send)
    return messages


def _response(messages: list[dict[str, Any]]) -> tuple[int, dict[str, Any]]:
    start = next(message for message in messages if message["type"] == "http.response.start")
    body = b"".join(
        message.get("body", b"")
        for message in messages
        if message["type"] == "http.response.body"
    )
    return int(start["status"]), json.loads(body.decode("utf-8"))


async def test_chunked_body_over_limit_returns_400(app_factory, settings) -> None:
    custom = settings.test_overrides(max_upload_bytes=1024)  # limit = 2048 bytes
    application, client = await app_factory(custom)
    login = await client.post("/api/admin/login", json={"password": "password123"})
    admin_headers = {"Authorization": f"Bearer {login.json()['token']}"}
    user = await create_user(client, admin_headers, "member")
    key = await create_api_key(
        client, admin_headers, user["id"], "member-key", daily_limit=100, rpm_limit=100
    )
    scope = _scope(
        "/v1/ocr/image",
        {
            "host": "testserver",
            "authorization": f"Bearer {key['key']}",
            "content-type": "application/json",
        },
    )
    chunks = [
        {"type": "http.request", "body": b"x" * 1024, "more_body": True},
        {"type": "http.request", "body": b"x" * 1024, "more_body": True},
        {"type": "http.request", "body": b"x" * 64, "more_body": False},
    ]
    messages = await _call(application, scope, chunks)
    status, payload = _response(messages)
    assert status == 400
    assert payload["error"]["code"] == "BAD_REQUEST"
    assert "size limit" in payload["error"]["message"]


async def test_small_chunked_body_is_accepted(app_factory, settings) -> None:
    custom = settings.test_overrides(max_upload_bytes=1024)
    application, _client = await app_factory(custom)
    body = json.dumps({"password": "password123"}).encode("utf-8")
    scope = _scope(
        "/api/admin/login",
        {"host": "testserver", "content-type": "application/json"},
    )
    chunks = [
        {"type": "http.request", "body": body[:10], "more_body": True},
        {"type": "http.request", "body": body[10:], "more_body": False},
    ]
    messages = await _call(application, scope, chunks)
    status, payload = _response(messages)
    assert status == 200
    assert payload["token"]
