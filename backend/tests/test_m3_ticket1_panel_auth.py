from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
from conftest import ADMIN_PASSWORD

from app.panel import PANEL_MISSING_CODE, PANEL_MISSING_MESSAGE, _resolve_within

SECURITY_HEADERS = (
    "x-content-type-options",
    "referrer-policy",
    "x-frame-options",
    "permissions-policy",
)


def _set_cookie_headers(response: httpx.Response) -> dict[str, str]:
    """name -> raw Set-Cookie header (first occurrence)."""
    out: dict[str, str] = {}
    for header in response.headers.get_list("set-cookie"):
        name = header.split(";", 1)[0].split("=", 1)[0]
        out.setdefault(name, header)
    return out


def _assert_security_headers(response: httpx.Response) -> None:
    for name in SECURITY_HEADERS:
        assert response.headers.get(name), f"missing {name} on {response.request.url}"


async def test_login_sets_session_and_csrf_cookies(client) -> None:
    response = await client.post("/api/admin/login", json={"password": ADMIN_PASSWORD})
    assert response.status_code == 200
    body = response.json()
    assert body["token"] and body["csrf_token"]
    assert body["expires_in"] == 43200

    cookies = _set_cookie_headers(response)
    session = cookies["ocr_admin_session"]
    csrf = cookies["ocr_csrf"]

    assert "httponly" in session.lower()
    assert "samesite=lax" in session.lower()
    assert "path=/" in session.lower()
    assert "max-age=43200" in session.lower()
    assert "secure" not in session.lower()
    assert body["csrf_token"] in csrf

    assert "httponly" not in csrf.lower()
    assert "samesite=lax" in csrf.lower()


async def test_cookie_session_can_read_admin_api(client) -> None:
    await client.post("/api/admin/login", json={"password": ADMIN_PASSWORD})
    response = await client.get("/api/admin/users")
    assert response.status_code == 200
    me = await client.get("/api/admin/me")
    assert me.status_code == 200
    assert me.json()["username"] == "admin"
    assert me.json()["csrf_token"]


async def test_cookie_write_requires_matching_csrf(client) -> None:
    login = await client.post("/api/admin/login", json={"password": ADMIN_PASSWORD})
    csrf_token = login.json()["csrf_token"]

    missing = await client.post("/api/admin/users", json={"name": "no-csrf"})
    assert missing.status_code == 403
    assert missing.json()["error"]["code"] == "FORBIDDEN"

    wrong = await client.post(
        "/api/admin/users", json={"name": "wrong-csrf"}, headers={"X-CSRF-Token": "nope"}
    )
    assert wrong.status_code == 403

    ok = await client.post(
        "/api/admin/users",
        json={"name": "right-csrf"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert ok.status_code == 200, ok.text


async def test_bearer_write_exempt_from_csrf(client) -> None:
    login = await client.post("/api/admin/login", json={"password": ADMIN_PASSWORD})
    token = login.json()["token"]
    response = await client.post(
        "/api/admin/users",
        json={"name": "bearer-writer"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text


async def test_invalid_bearer_does_not_fall_back_to_cookie(client) -> None:
    await client.post("/api/admin/login", json={"password": ADMIN_PASSWORD})
    response = await client.get(
        "/api/admin/users", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


async def test_me_reissues_missing_csrf_cookie(client) -> None:
    login = await client.post("/api/admin/login", json={"password": ADMIN_PASSWORD})
    assert login.status_code == 200
    client.cookies.delete("ocr_csrf")

    response = await client.get("/api/admin/me")
    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "admin"
    assert body["csrf_token"]
    cookies = _set_cookie_headers(response)
    assert "ocr_csrf" in cookies
    assert body["csrf_token"] in cookies["ocr_csrf"]
    # The session cookie must not be reissued by a plain GET.
    assert "ocr_admin_session" not in cookies


async def test_logout_clears_cookies_and_revokes_browser_session(client) -> None:
    login = await client.post("/api/admin/login", json={"password": ADMIN_PASSWORD})
    csrf_token = login.json()["csrf_token"]

    response = await client.post(
        "/api/admin/logout", headers={"X-CSRF-Token": csrf_token}
    )
    assert response.status_code == 204
    cookies = _set_cookie_headers(response)
    assert "ocr_admin_session" in cookies and "ocr_csrf" in cookies
    assert "max-age=0" in cookies["ocr_admin_session"].lower()

    after = await client.get("/api/admin/users")
    assert after.status_code == 401


async def test_secure_cookie_behind_trusted_proxy(app_factory, settings) -> None:
    proxied = settings.test_overrides(trust_proxy_headers=True)
    _app, client = await app_factory(proxied)
    response = await client.post(
        "/api/admin/login",
        json={"password": ADMIN_PASSWORD},
        headers={"X-Forwarded-Proto": "https"},
    )
    assert response.status_code == 200
    cookies = _set_cookie_headers(response)
    assert "secure" in cookies["ocr_admin_session"].lower()
    assert "secure" in cookies["ocr_csrf"].lower()


async def test_secure_cookie_ignored_when_proxy_headers_untrusted(client) -> None:
    response = await client.post(
        "/api/admin/login",
        json={"password": ADMIN_PASSWORD},
        headers={"X-Forwarded-Proto": "https"},
    )
    cookies = _set_cookie_headers(response)
    assert "secure" not in cookies["ocr_admin_session"].lower()


async def test_openapi_exposes_bearer_scheme(client) -> None:
    spec = (await client.get("/openapi.json")).json()
    schemes = spec.get("components", {}).get("securitySchemes", {})
    assert any(
        scheme.get("type") == "http" and scheme.get("scheme") == "bearer"
        for scheme in schemes.values()
    )


async def test_security_headers_on_health_and_api(client) -> None:
    health = await client.get("/healthz")
    assert health.status_code == 200
    _assert_security_headers(health)
    assert "content-security-policy" not in health.headers

    unauthorized = await client.get("/api/admin/users")
    assert unauthorized.status_code == 401
    _assert_security_headers(unauthorized)
    assert unauthorized.headers["cache-control"] == "no-store"
    assert "content-security-policy" not in unauthorized.headers

    docs = await client.get("/docs")
    assert docs.status_code == 200
    _assert_security_headers(docs)
    assert "content-security-policy" not in docs.headers


async def test_panel_missing_returns_fixed_404(client) -> None:
    response = await client.get("/")
    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == PANEL_MISSING_CODE
    assert error["message"] == PANEL_MISSING_MESSAGE

    api_missing = await client.get("/api/nope")
    assert api_missing.status_code == 404
    assert api_missing.json()["error"]["code"] == "NOT_FOUND"
    assert (await client.get("/healthz")).status_code == 200


def _build_dist(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(
        '<!doctype html><html><body><div id="root"></div>'
        '<script src="/assets/app.js"></script></body></html>',
        encoding="utf-8",
    )
    (dist / "assets" / "app.js").write_text("console.log('panel')\n", encoding="utf-8")
    (dist / "favicon.svg").write_text("<svg></svg>\n", encoding="utf-8")
    return dist


async def test_panel_serves_entry_assets_and_fallbacks(app_factory, settings, tmp_path) -> None:
    dist = _build_dist(tmp_path)
    configured = settings.test_overrides(frontend_dist=str(dist))
    _app, client = await app_factory(configured)

    root = await client.get("/")
    assert root.status_code == 200
    assert root.headers["content-type"].startswith("text/html")
    assert root.headers["cache-control"] == "no-store"
    assert "content-security-policy" in root.headers
    assert "script-src 'self'" in root.headers["content-security-policy"]
    assert "unsafe-inline" not in root.headers["content-security-policy"].split("style-src")[0]

    deep = await client.get("/accounts")
    assert deep.status_code == 200
    assert deep.headers["content-type"].startswith("text/html")
    assert deep.headers["cache-control"] == "no-store"

    asset = await client.get("/assets/app.js")
    assert asset.status_code == 200
    assert "immutable" in asset.headers["cache-control"]

    favicon = await client.get("/favicon.svg")
    assert favicon.status_code == 200
    assert "max-age=3600" in favicon.headers["cache-control"]

    missing_asset = await client.get("/assets/missing.js")
    assert missing_asset.status_code == 404
    assert missing_asset.headers["content-type"].startswith("application/json")

    for path in ("/api/nope", "/v1/nope", "/healthz/nope"):
        response = await client.get(path)
        assert response.status_code == 404
        assert response.headers["content-type"].startswith("application/json")

    assert (await client.get("/healthz")).status_code == 200


def test_resolve_within_rejects_traversal(tmp_path: Path) -> None:
    dist = _build_dist(tmp_path)
    secret = tmp_path / "secret.txt"
    secret.write_text("top secret", encoding="utf-8")

    assert _resolve_within(dist, "favicon.svg") == (dist / "favicon.svg").resolve()
    assert _resolve_within(dist, "../secret.txt") is None
    assert _resolve_within(dist, "..\\secret.txt") is None
    assert _resolve_within(dist, "assets/../../secret.txt") is None
    assert _resolve_within(dist, "") is None
    assert _resolve_within(dist, "missing.js") is None


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
        "headers": [
            (key.lower().encode("latin-1"), value.encode("latin-1"))
            for key, value in headers.items()
        ],
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
    }


async def test_body_limit_rejection_carries_security_headers(app_factory, settings) -> None:
    custom = settings.test_overrides(max_upload_bytes=64)
    application, _client = await app_factory(custom)

    messages: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"x" * 4096, "more_body": False}

    async def send(message: dict[str, Any]) -> None:
        messages.append(message)

    await application(_scope("/api/admin/login", {"content-type": "application/json"}), receive, send)

    start = next(item for item in messages if item["type"] == "http.response.start")
    assert start["status"] == 400
    header_names = {name.decode("latin-1").lower() for name, _ in start["headers"]}
    for name in SECURITY_HEADERS:
        assert name in header_names
    body = b"".join(
        item.get("body", b"") for item in messages if item["type"] == "http.response.body"
    )
    assert json.loads(body.decode("utf-8"))["error"]["code"] == "BAD_REQUEST"
