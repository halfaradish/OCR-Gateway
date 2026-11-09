"""P1 加固回归：docs 开关、缓存前置（跳过二次解码）、logout 撤销、admin 审计日志。"""

from __future__ import annotations

import logging

import httpx
import respx
from conftest import (
    ADMIN_PASSWORD,
    auth_headers,
    create_account,
    create_api_key,
    create_user,
    make_image_bytes,
)

import app.api.public as public_module
from app.config import Settings
from app.runtime_settings import bump_session_version, load_session_version

TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"
OCR_URL = "https://aip.baidubce.com/rest/2.0/ocr/v1/general_basic"


def token_response() -> httpx.Response:
    return httpx.Response(200, json={"access_token": "tok", "expires_in": 2592000})


def words_response(*words: str) -> httpx.Response:
    return httpx.Response(200, json={"words_result": [{"words": word} for word in words]})


# ── 6. DOCS_ENABLED：生产默认关闭 ─────────────────────────────────


def test_docs_defaults_off(monkeypatch) -> None:
    # alembic 测试会 load_dotenv 仓库根 .env，把 DOCS_ENABLED=true 注入进程环境；显式剔除。
    monkeypatch.delenv("DOCS_ENABLED", raising=False)
    settings = Settings(_env_file=None, master_key="k" * 32, admin_password="password123")
    assert settings.docs_enabled is False


async def test_docs_disabled_hides_swagger_and_openapi(app_factory, settings) -> None:
    _app, client = await app_factory(settings.test_overrides(docs_enabled=False))
    assert (await client.get("/docs")).status_code == 404
    assert (await client.get("/redoc")).status_code == 404
    assert (await client.get("/openapi.json")).status_code == 404


async def test_docs_enabled_exposes_swagger(client) -> None:
    # conftest 的 settings fixture 已 docs_enabled=True，保证既有 /docs 契约测试继续成立。
    assert (await client.get("/docs")).status_code == 200
    assert (await client.get("/openapi.json")).status_code == 200


# ── 7+8. 缓存前置：命中缓存不再走 Pillow 解码 ──────────────────────


async def test_cache_hit_skips_normalize(client, admin_headers, monkeypatch) -> None:
    user = await create_user(client, admin_headers, "cache-user")
    key = await create_api_key(
        client, admin_headers, user["id"], "cache-key", daily_limit=100, rpm_limit=100
    )
    await create_account(client, admin_headers, "baidu", "baidu-cache")
    headers = auth_headers(key["key"])
    image = make_image_bytes(text="CACHED")

    with respx.mock(assert_all_called=False) as mock:
        mock.post(TOKEN_URL).mock(return_value=token_response())
        mock.post(OCR_URL).mock(return_value=words_response("第一行"))
        first = await client.post(
            "/v1/ocr/image",
            headers=headers,
            files={"file": ("a.png", image, "image/png")},
        )
    assert first.status_code == 200, first.text
    assert first.json()["cached"] is False

    def boom(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("normalize_image must not run on cache hits")

    monkeypatch.setattr(public_module, "normalize_image", boom)
    second = await client.post(
        "/v1/ocr/image",
        headers=headers,
        files={"file": ("a.png", image, "image/png")},
    )
    assert second.status_code == 200, second.text
    assert second.json()["cached"] is True
    assert second.json()["provider"] == "baidu"


# ── 11a. logout 撤销所有已签发 token（session_version） ───────────


async def test_logout_revokes_all_admin_tokens(client) -> None:
    login = await client.post("/api/admin/login", json={"password": ADMIN_PASSWORD})
    assert login.status_code == 200
    old_headers = {"Authorization": f"Bearer {login.json()['token']}"}

    assert (await client.get("/api/admin/me", headers=old_headers)).status_code == 200
    assert (
        await client.post("/api/admin/logout", headers=old_headers)
    ).status_code == 204
    revoked = await client.get("/api/admin/me", headers=old_headers)
    assert revoked.status_code == 401

    relogin = await client.post("/api/admin/login", json={"password": ADMIN_PASSWORD})
    assert relogin.status_code == 200
    fresh = {"Authorization": f"Bearer {relogin.json()['token']}"}
    assert (await client.get("/api/admin/me", headers=fresh)).status_code == 200


async def test_session_version_persists_and_bumps(app) -> None:
    state = app.state.gw
    async with state.session_factory() as session:
        before = await load_session_version(session)
        bumped = await bump_session_version(session)
        await session.commit()
        after = await load_session_version(session)
    assert before == 1
    assert bumped == before + 1
    assert after == bumped


# ── 11b. admin 变更的结构化审计日志 ───────────────────────────────


async def test_admin_mutations_emit_audit_log(client, admin_headers, caplog) -> None:
    # alembic fileConfig 会把 root logger 提到 WARN，这里把 root 也压回 INFO 以便捕获传播记录。
    with caplog.at_level(logging.INFO, logger="app.api.admin"), caplog.at_level(logging.INFO):
        await create_user(client, admin_headers, "audit-user")
    records = [r for r in caplog.records if r.getMessage() == "admin.audit"]
    assert records, "没有 admin.audit 记录"
    audit = records[-1]
    assert audit.extra_fields["action"] == "user.create"
    assert audit.extra_fields["target"] == "user"
    assert audit.extra_fields["target_id"] is not None
    assert audit.extra_fields["detail"]["name"] == "audit-user"
