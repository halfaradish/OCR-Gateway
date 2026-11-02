from __future__ import annotations

import asyncio
import base64
from datetime import timedelta

import httpx
import respx
from conftest import (
    auth_headers,
    create_account,
    create_api_key,
    create_user,
    make_image_bytes,
)
from sqlalchemy import select

from app.core.scheduler import ScheduleResult
from app.db import utcnow
from app.models import Account, ApiKey, QuotaCounter, UsageEvent

TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"
OCR_URL = "https://aip.baidubce.com/rest/2.0/ocr/v1/general_basic"


def token_response() -> httpx.Response:
    return httpx.Response(200, json={"access_token": "tok", "expires_in": 2592000})


def words_response(*words: str) -> httpx.Response:
    return httpx.Response(200, json={"words_result": [{"words": word} for word in words]})


async def setup_access(client, admin_headers, **account_overrides):
    user = await create_user(client, admin_headers, "member")
    key = await create_api_key(
        client, admin_headers, user["id"], "member-key", daily_limit=100, rpm_limit=100
    )
    account = await create_account(
        client, admin_headers, "baidu", "baidu-main", **account_overrides
    )
    return auth_headers(key["key"]), key, account


async def test_multipart_success_and_accounting(client, admin_headers, app) -> None:
    key_headers, key, account = await setup_access(client, admin_headers)
    image = make_image_bytes()
    with respx.mock(assert_all_called=False) as mock:
        mock.post(TOKEN_URL).mock(return_value=token_response())
        ocr_route = mock.post(OCR_URL).mock(return_value=words_response("第一行", "第二行"))
        response = await client.post(
            "/v1/ocr/image",
            headers=key_headers,
            files={"file": ("a.png", image, "image/png")},
        )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["provider"] == "baidu"
    assert body["text"] == "第一行\n第二行"
    assert [line["text"] for line in body["lines"]] == ["第一行", "第二行"]
    assert body["lines"][0]["confidence"] is None
    assert body["quota"] == {"unit": "image", "used": 1}
    assert body["cached"] is False
    assert body["warnings"] == []
    assert body["request_id"]
    assert ocr_route.call_count == 1

    state = app.state.gw
    async with state.session_factory() as session:
        events = (await session.execute(select(UsageEvent))).scalars().all()
        assert len(events) == 1
        event = events[0]
        assert event.success is True
        assert event.quota_used == 1
        assert event.api_key_id == key["id"]
        assert event.account_id == account["id"]
        assert event.image_hash and len(event.image_hash) == 16
        assert not hasattr(event, "text")
        await state.quota.flush(session)
        counters = (await session.execute(select(QuotaCounter))).scalars().all()
        daily = [row for row in counters if row.period_type == "daily"]
        assert daily and daily[0].used == 1
        account_row = await session.get(Account, account["id"])
        assert account_row is not None
        assert account_row.ewma_latency_ms != 1000.0
        key_row = await session.get(ApiKey, key["id"])
        assert key_row is not None
        assert key_row.last_used_at is not None


async def test_base64_success(client, admin_headers) -> None:
    key_headers, _, _ = await setup_access(client, admin_headers)
    encoded = base64.b64encode(make_image_bytes()).decode("ascii")
    with respx.mock(assert_all_called=False) as mock:
        mock.post(TOKEN_URL).mock(return_value=token_response())
        mock.post(OCR_URL).mock(return_value=words_response("ok"))
        response = await client.post(
            "/v1/ocr/image", headers=key_headers, json={"image_base64": encoded}
        )
    assert response.status_code == 200, response.text
    assert response.json()["text"] == "ok"
    assert response.json()["quota"]["used"] == 1


async def test_both_inputs_rejected(client, admin_headers) -> None:
    key_headers, _, _ = await setup_access(client, admin_headers)
    encoded = base64.b64encode(make_image_bytes()).decode("ascii")
    multipart = await client.post(
        "/v1/ocr/image",
        headers=key_headers,
        files={"file": ("a.png", make_image_bytes(), "image/png")},
        data={"image_base64": encoded},
    )
    assert multipart.status_code == 400
    json_both = await client.post(
        "/v1/ocr/image",
        headers=key_headers,
        json={"image_base64": encoded, "image_url": "https://example.com/a.png"},
    )
    assert json_both.status_code == 400


async def test_invalid_provider_and_language_rejected(client, admin_headers) -> None:
    key_headers, _, _ = await setup_access(client, admin_headers)
    encoded = base64.b64encode(make_image_bytes()).decode("ascii")
    provider = await client.post(
        "/v1/ocr/image",
        headers=key_headers,
        json={"image_base64": encoded, "provider": "local"},
    )
    assert provider.status_code == 400
    language = await client.post(
        "/v1/ocr/image",
        headers=key_headers,
        json={"image_base64": encoded, "language": "fr"},
    )
    assert language.status_code == 400


async def test_empty_text_returns_warning(client, admin_headers) -> None:
    key_headers, _, _ = await setup_access(client, admin_headers)
    with respx.mock(assert_all_called=False) as mock:
        mock.post(TOKEN_URL).mock(return_value=token_response())
        mock.post(OCR_URL).mock(return_value=httpx.Response(200, json={"words_result": []}))
        response = await client.post(
            "/v1/ocr/image",
            headers=key_headers,
            files={"file": ("a.png", make_image_bytes(), "image/png")},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["text"] == ""
    assert body["warnings"] == ["EMPTY_TEXT"]


async def test_provider_5xx_returns_502_and_does_not_charge(client, admin_headers, app) -> None:
    key_headers, _, account = await setup_access(client, admin_headers)
    with respx.mock(assert_all_called=False) as mock:
        mock.post(TOKEN_URL).mock(return_value=token_response())
        mock.post(OCR_URL).mock(return_value=httpx.Response(503))
        response = await client.post(
            "/v1/ocr/image",
            headers=key_headers,
            files={"file": ("a.png", make_image_bytes(), "image/png")},
        )
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "PROVIDER_ERROR"
    state = app.state.gw
    async with state.session_factory() as session:
        event = (await session.execute(select(UsageEvent))).scalars().one()
        assert event.success is False
        assert event.quota_used == 0
        row = await session.get(Account, account["id"])
        assert row is not None
        assert row.state == "cooling"
        assert row.last_error_code == "PROVIDER_ERROR"


async def test_auth_failure_marks_account_invalid(client, admin_headers, app) -> None:
    key_headers, _, account = await setup_access(client, admin_headers)
    with respx.mock(assert_all_called=False) as mock:
        mock.post(TOKEN_URL).mock(return_value=token_response())
        mock.post(OCR_URL).mock(return_value=httpx.Response(401))
        response = await client.post(
            "/v1/ocr/image",
            headers=key_headers,
            files={"file": ("a.png", make_image_bytes(), "image/png")},
        )
    assert response.status_code == 503
    state = app.state.gw
    async with state.session_factory() as session:
        row = await session.get(Account, account["id"])
        assert row is not None
        assert row.state == "invalid"


async def test_cooling_account_recovers_after_cooldown(client, admin_headers, app) -> None:
    key_headers, _, account = await setup_access(client, admin_headers)
    with respx.mock(assert_all_called=False) as mock:
        mock.post(TOKEN_URL).mock(return_value=token_response())
        mock.post(OCR_URL).mock(return_value=httpx.Response(503))
        first = await client.post(
            "/v1/ocr/image",
            headers=key_headers,
            files={"file": ("a.png", make_image_bytes(), "image/png")},
        )
    assert first.status_code == 502
    state = app.state.gw
    runtime = state.registry.get(account["id"])
    assert runtime is not None
    runtime.cooldown_until = utcnow() - timedelta(seconds=1)
    async with state.session_factory() as session:
        row = await session.get(Account, account["id"])
        assert row is not None
        row.cooldown_until = runtime.cooldown_until
        await session.commit()
    with respx.mock(assert_all_called=False) as mock:
        mock.post(TOKEN_URL).mock(return_value=token_response())
        mock.post(OCR_URL).mock(return_value=words_response("recovered"))
        second = await client.post(
            "/v1/ocr/image",
            headers=key_headers,
            files={"file": ("b.png", make_image_bytes(text="second"), "image/png")},
        )
    assert second.status_code == 200
    assert second.json()["text"] == "recovered"


async def test_daily_account_quota_excludes_account(client, admin_headers, app) -> None:
    key_headers, _, account = await setup_access(client, admin_headers, quota_daily=1)
    with respx.mock(assert_all_called=False) as mock:
        mock.post(TOKEN_URL).mock(return_value=token_response())
        mock.post(OCR_URL).mock(return_value=words_response("first"))
        first = await client.post(
            "/v1/ocr/image",
            headers=key_headers,
            files={"file": ("a.png", make_image_bytes(text="one"), "image/png")},
        )
        assert first.status_code == 200
        second = await client.post(
            "/v1/ocr/image",
            headers=key_headers,
            files={"file": ("b.png", make_image_bytes(text="two"), "image/png")},
        )
    assert second.status_code == 503
    state = app.state.gw
    async with state.session_factory() as session:
        row = await session.get(Account, account["id"])
        assert row is not None
        assert row.state == "quota_exhausted"


async def test_providers_and_me(client, admin_headers, app) -> None:
    user = await create_user(client, admin_headers, "member")
    key = await create_api_key(
        client, admin_headers, user["id"], "member-key", daily_limit=100, rpm_limit=100
    )
    await create_account(client, admin_headers, "baidu", "baidu-1")
    await create_account(client, admin_headers, "baidu", "baidu-2")
    await create_account(client, admin_headers, "tencent", "tencent-1")
    key_headers = auth_headers(key["key"])
    providers = await client.get("/v1/providers", headers=key_headers)
    assert providers.status_code == 200
    body = providers.json()
    by_code = {item["code"]: item for item in body["providers"]}
    assert by_code["baidu"]["available_accounts"] == 2
    assert by_code["tencent"]["available_accounts"] == 1
    assert "credential_fields" not in str(body)
    assert "AK-test" not in str(body)

    with respx.mock(assert_all_called=False) as mock:
        mock.post(TOKEN_URL).mock(return_value=token_response())
        mock.post(OCR_URL).mock(return_value=words_response("hello"))
        response = await client.post(
            "/v1/ocr/image",
            headers=key_headers,
            files={"file": ("a.png", make_image_bytes(), "image/png")},
        )
        assert response.status_code == 200
    me = await client.get("/v1/me", headers=key_headers)
    assert me.status_code == 200
    payload = me.json()
    assert payload["user"] == "member"
    assert payload["today"]["requests"] == 1
    assert payload["today"]["quota_used"] == 1
    assert payload["limits"]["daily_limit"] == 100
    assert payload["limits"]["rpm_limit"] == 100


async def test_global_concurrency_returns_503(app_factory, settings) -> None:
    custom = settings.test_overrides(
        max_concurrent_requests=1, request_deadline_ms=200, cache_enabled=False
    )
    application, client = await app_factory(custom)
    login = await client.post(
        "/api/admin/login", json={"password": "password123"}
    )
    admin_headers = {"Authorization": f"Bearer {login.json()['token']}"}
    user = await create_user(client, admin_headers, "member")
    key = await create_api_key(
        client, admin_headers, user["id"], "member-key", daily_limit=100, rpm_limit=100
    )
    await create_account(client, admin_headers, "baidu", "baidu-1")
    key_headers = auth_headers(key["key"])

    account = application.state.gw.registry.all()[0]

    async def slow_recognize(provider, image, language):
        await asyncio.sleep(0.4)
        return ScheduleResult(
            account_id=account.id,
            provider="baidu",
            text="slow",
            lines=[],
            vendor_latency_ms=1,
        )

    application.state.gw.scheduler.recognize = slow_recognize  # type: ignore[method-assign]

    async def call(index: int) -> httpx.Response:
        return await client.post(
            "/v1/ocr/image",
            headers=key_headers,
            files={
                "file": (
                    f"{index}.png",
                    make_image_bytes(text=f"img-{index}"),
                    "image/png",
                )
            },
        )

    responses = await asyncio.gather(call(1), call(2))
    statuses = sorted(response.status_code for response in responses)
    assert statuses == [200, 503]
    limited = [response for response in responses if response.status_code == 503][0]
    assert limited.json()["error"]["code"] == "PROVIDER_UNAVAILABLE"
    assert "gateway at capacity" in limited.json()["error"]["message"]


async def test_background_quota_flush_reaches_database(client, admin_headers, app) -> None:
    key_headers, _, account = await setup_access(client, admin_headers)
    with respx.mock(assert_all_called=False) as mock:
        mock.post(TOKEN_URL).mock(return_value=token_response())
        mock.post(OCR_URL).mock(return_value=words_response("flush"))
        response = await client.post(
            "/v1/ocr/image",
            headers=key_headers,
            files={"file": ("a.png", make_image_bytes(), "image/png")},
        )
    assert response.status_code == 200
    await asyncio.sleep(2.3)
    state = app.state.gw
    async with state.session_factory() as session:
        counters = (
            await session.execute(
                select(QuotaCounter).where(QuotaCounter.account_id == account["id"])
            )
        ).scalars().all()
        assert counters
        assert all(row.used == 1 for row in counters)


async def test_gateway_overhead_p99_under_20ms(app_factory, settings) -> None:
    custom = settings.test_overrides(cache_enabled=False)
    application, client = await app_factory(custom)
    login = await client.post("/api/admin/login", json={"password": "password123"})
    admin_headers = {"Authorization": f"Bearer {login.json()['token']}"}
    user = await create_user(client, admin_headers, "member")
    key = await create_api_key(
        client, admin_headers, user["id"], "member-key", daily_limit=1000, rpm_limit=1000
    )
    await create_account(
        client, admin_headers, "baidu", "baidu-1", qps_limit=None
    )
    key_headers = auth_headers(key["key"])
    image = make_image_bytes(text="benchmark")
    samples: list[int] = []
    with respx.mock(assert_all_called=False) as mock:
        mock.post(TOKEN_URL).mock(return_value=token_response())
        mock.post(OCR_URL).mock(return_value=words_response("ok"))
        for _ in range(30):
            response = await client.post(
                "/v1/ocr/image",
                headers=key_headers,
                files={"file": ("a.png", image, "image/png")},
            )
            assert response.status_code == 200, response.text
            samples.append(int(response.json()["latency_ms"]))
    samples.sort()
    p99 = samples[max(0, int(len(samples) * 0.99) - 1)]
    assert p99 < 20, f"p99={p99}ms samples={samples}"


async def test_disabled_primary_uses_backup_account(client, admin_headers, app) -> None:
    user = await create_user(client, admin_headers, "member")
    key = await create_api_key(
        client, admin_headers, user["id"], "member-key", daily_limit=100, rpm_limit=100
    )
    primary = await create_account(
        client, admin_headers, "baidu", "primary", priority=10
    )
    backup = await create_account(
        client, admin_headers, "baidu", "backup", priority=100
    )
    await client.patch(
        f"/api/admin/accounts/{primary['id']}",
        json={"enabled": False},
        headers=admin_headers,
    )
    key_headers = auth_headers(key["key"])
    with respx.mock(assert_all_called=False) as mock:
        mock.post(TOKEN_URL).mock(return_value=token_response())
        ocr_route = mock.post(OCR_URL).mock(return_value=words_response("backup"))
        response = await client.post(
            "/v1/ocr/image",
            headers=key_headers,
            files={"file": ("a.png", make_image_bytes(), "image/png")},
        )
    assert response.status_code == 200
    assert response.json()["text"] == "backup"
    assert ocr_route.call_count == 1
    state = app.state.gw
    async with state.session_factory() as session:
        event = (await session.execute(select(UsageEvent))).scalars().one()
        assert event.account_id == backup["id"]
        assert event.provider == "baidu"
        assert event.quota_used == 1
        await state.quota.flush(session)
        counters = (
            await session.execute(
                select(QuotaCounter).where(QuotaCounter.account_id == backup["id"])
            )
        ).scalars().all()
        assert counters and all(row.used == 1 for row in counters)
        primary_counters = (
            await session.execute(
                select(QuotaCounter).where(QuotaCounter.account_id == primary["id"])
            )
        ).scalars().all()
        assert primary_counters == []


async def test_vendor_input_error_returns_400_without_switch(client, admin_headers) -> None:
    user = await create_user(client, admin_headers, "member")
    key = await create_api_key(
        client, admin_headers, user["id"], "member-key", daily_limit=100, rpm_limit=100
    )
    await create_account(client, admin_headers, "baidu", "primary", priority=10)
    await create_account(client, admin_headers, "baidu", "backup", priority=100)
    key_headers = auth_headers(key["key"])
    with respx.mock(assert_all_called=False) as mock:
        mock.post(TOKEN_URL).mock(return_value=token_response())
        ocr_route = mock.post(OCR_URL).mock(
            return_value=httpx.Response(
                200, json={"error_code": 100, "error_msg": "bad image"}
            )
        )
        response = await client.post(
            "/v1/ocr/image",
            headers=key_headers,
            files={"file": ("a.png", make_image_bytes(), "image/png")},
        )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "BAD_REQUEST"
    assert ocr_route.call_count == 1
