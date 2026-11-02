from __future__ import annotations

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

from app.db import utcnow
from app.models import Account, QuotaCounter, UsageEvent

BAIDU_TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"
BAIDU_OCR_URL = "https://aip.baidubce.com/rest/2.0/ocr/v1/general_basic"
TENCENT_URL = "https://ocr.tencentcloudapi.com"


def baidu_token() -> httpx.Response:
    return httpx.Response(200, json={"access_token": "tok", "expires_in": 2592000})


def baidu_words(*words: str) -> httpx.Response:
    return httpx.Response(200, json={"words_result": [{"words": word} for word in words]})


def tencent_ok(*texts: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "Response": {
                "TextDetections": [
                    {"DetectedText": text, "Confidence": 90.0} for text in texts
                ],
                "RequestId": "req",
            }
        },
    )


def tencent_error(code: str, message: str = "x") -> httpx.Response:
    return httpx.Response(
        200, json={"Response": {"Error": {"Code": code, "Message": message}}}
    )


async def setup(client, admin_headers, provider: str, **account_overrides):
    user = await create_user(client, admin_headers, "member")
    key = await create_api_key(
        client, admin_headers, user["id"], "member-key", daily_limit=100, rpm_limit=100
    )
    account = await create_account(
        client, admin_headers, provider, f"{provider}-main", **account_overrides
    )
    return auth_headers(key["key"]), account


async def test_auto_falls_back_to_tencent(client, admin_headers) -> None:
    key_headers, _ = await setup(client, admin_headers, "tencent")
    with respx.mock(assert_all_called=False) as mock:
        route = mock.post(TENCENT_URL).mock(return_value=tencent_ok("腾讯结果"))
        response = await client.post(
            "/v1/ocr/image",
            headers=key_headers,
            files={"file": ("a.png", make_image_bytes(), "image/png")},
        )
    assert response.status_code == 200, response.text
    assert response.json()["provider"] == "tencent"
    assert response.json()["text"] == "腾讯结果"
    assert response.json()["lines"][0]["confidence"] == 90.0
    assert route.call_count == 1


async def test_explicit_baidu_does_not_use_tencent(client, admin_headers) -> None:
    key_headers, _ = await setup(client, admin_headers, "tencent")
    with respx.mock(assert_all_called=False) as mock:
        route = mock.post(TENCENT_URL).mock(return_value=tencent_ok("should not happen"))
        response = await client.post(
            "/v1/ocr/image",
            headers=key_headers,
            files={"file": ("a.png", make_image_bytes(), "image/png")},
            data={"provider": "baidu"},
        )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "PROVIDER_UNAVAILABLE"
    assert route.call_count == 0


async def test_explicit_tencent_does_not_use_baidu(client, admin_headers) -> None:
    key_headers, _ = await setup(client, admin_headers, "baidu")
    with respx.mock(assert_all_called=False) as mock:
        token_route = mock.post(BAIDU_TOKEN_URL).mock(return_value=baidu_token())
        ocr_route = mock.post(BAIDU_OCR_URL).mock(return_value=baidu_words("no"))
        response = await client.post(
            "/v1/ocr/image",
            headers=key_headers,
            files={"file": ("a.png", make_image_bytes(), "image/png")},
            data={"provider": "tencent"},
        )
    assert response.status_code == 503
    assert token_route.call_count == 0
    assert ocr_route.call_count == 0


async def test_signature_expire_cools_not_invalid(client, admin_headers, app) -> None:
    key_headers, account = await setup(client, admin_headers, "tencent")
    with respx.mock(assert_all_called=False) as mock:
        mock.post(TENCENT_URL).mock(
            return_value=tencent_error("AuthFailure.SignatureExpire", "expired")
        )
        response = await client.post(
            "/v1/ocr/image",
            headers=key_headers,
            files={"file": ("a.png", make_image_bytes(), "image/png")},
            data={"provider": "tencent"},
        )
    assert response.status_code == 502
    state = app.state.gw
    async with state.session_factory() as session:
        row = await session.get(Account, account["id"])
        assert row is not None
        assert row.state == "cooling"
        assert row.state != "invalid"
        assert row.last_error_code == "PROVIDER_ERROR"
        assert row.cooldown_until is not None
        remaining = row.cooldown_until - utcnow()
        assert remaining > timedelta(seconds=20)


async def test_tencent_quota_error_marks_account_quota_exhausted(
    client, admin_headers, app
) -> None:
    key_headers, account = await setup(client, admin_headers, "tencent")
    with respx.mock(assert_all_called=False) as mock:
        mock.post(TENCENT_URL).mock(
            return_value=tencent_error("ResourceUnavailable.InArrears", "arrears")
        )
        response = await client.post(
            "/v1/ocr/image",
            headers=key_headers,
            files={"file": ("a.png", make_image_bytes(), "image/png")},
            data={"provider": "tencent"},
        )
    assert response.status_code == 503
    state = app.state.gw
    async with state.session_factory() as session:
        row = await session.get(Account, account["id"])
        assert row is not None
        assert row.state == "quota_exhausted"


async def test_account_probe_success_has_no_side_effects(
    client, admin_headers, app
) -> None:
    _, account = await setup(client, admin_headers, "baidu")
    with respx.mock(assert_all_called=False) as mock:
        mock.post(BAIDU_TOKEN_URL).mock(return_value=baidu_token())
        mock.post(BAIDU_OCR_URL).mock(return_value=baidu_words("probe", "text"))
        response = await client.post(
            f"/api/admin/accounts/{account['id']}/test", headers=admin_headers
        )
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["text"] == "probe\ntext"
    assert body["provider"] == "baidu"
    assert body["latency_ms"] >= 0
    state = app.state.gw
    async with state.session_factory() as session:
        assert (await session.execute(select(UsageEvent))).scalars().all() == []
        assert (await session.execute(select(QuotaCounter))).scalars().all() == []
        row = await session.get(Account, account["id"])
        assert row is not None
        assert row.state == "active"
        assert row.ewma_latency_ms == 1000.0
        assert row.last_used_at is None


async def test_account_probe_failure_reports_classification(client, admin_headers, app) -> None:
    _, account = await setup(client, admin_headers, "baidu")
    with respx.mock(assert_all_called=False) as mock:
        mock.post(BAIDU_TOKEN_URL).mock(return_value=baidu_token())
        mock.post(BAIDU_OCR_URL).mock(return_value=httpx.Response(401))
        response = await client.post(
            f"/api/admin/accounts/{account['id']}/test", headers=admin_headers
        )
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["error_code"] == "AUTH_FAILED"
    state = app.state.gw
    async with state.session_factory() as session:
        row = await session.get(Account, account["id"])
        assert row is not None
        assert row.state == "active"


async def test_reset_state_recovers_invalid_account(client, admin_headers, app) -> None:
    key_headers, account = await setup(client, admin_headers, "baidu")
    with respx.mock(assert_all_called=False) as mock:
        mock.post(BAIDU_TOKEN_URL).mock(return_value=baidu_token())
        mock.post(BAIDU_OCR_URL).mock(return_value=httpx.Response(401))
        failed = await client.post(
            "/v1/ocr/image",
            headers=key_headers,
            files={"file": ("a.png", make_image_bytes(), "image/png")},
        )
    assert failed.status_code == 503
    state = app.state.gw
    async with state.session_factory() as session:
        row = await session.get(Account, account["id"])
        assert row is not None
        assert row.state == "invalid"
    reset = await client.post(
        f"/api/admin/accounts/{account['id']}/reset-state", headers=admin_headers
    )
    assert reset.status_code == 200
    assert reset.json() == {"state": "active"}
    with respx.mock(assert_all_called=False) as mock:
        mock.post(BAIDU_TOKEN_URL).mock(return_value=baidu_token())
        mock.post(BAIDU_OCR_URL).mock(return_value=baidu_words("recovered"))
        recovered = await client.post(
            "/v1/ocr/image",
            headers=key_headers,
            files={"file": ("b.png", make_image_bytes(text="b"), "image/png")},
        )
    assert recovered.status_code == 200
    assert recovered.json()["text"] == "recovered"


async def test_reset_state_clears_quota_counters(client, admin_headers, app) -> None:
    key_headers, account = await setup(client, admin_headers, "baidu", quota_total=1)
    with respx.mock(assert_all_called=False) as mock:
        mock.post(BAIDU_TOKEN_URL).mock(return_value=baidu_token())
        mock.post(BAIDU_OCR_URL).mock(return_value=baidu_words("one"))
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
        await state.quota.flush(session)
        counters = (await session.execute(select(QuotaCounter))).scalars().all()
        assert counters and all(row.used == 1 for row in counters)
    reset = await client.post(
        f"/api/admin/accounts/{account['id']}/reset-state", headers=admin_headers
    )
    assert reset.status_code == 200
    async with state.session_factory() as session:
        counters = (await session.execute(select(QuotaCounter))).scalars().all()
        assert counters == []
    with respx.mock(assert_all_called=False) as mock:
        mock.post(BAIDU_TOKEN_URL).mock(return_value=baidu_token())
        mock.post(BAIDU_OCR_URL).mock(return_value=baidu_words("three"))
        third = await client.post(
            "/v1/ocr/image",
            headers=key_headers,
            files={"file": ("c.png", make_image_bytes(text="three"), "image/png")},
        )
    assert third.status_code == 200
    assert third.json()["text"] == "three"
