from __future__ import annotations

import ipaddress
from datetime import timedelta
from pathlib import Path

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
from app.models import UsageEvent
from app.utils import ssrf

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


async def setup_access(client, admin_headers, provider: str = "baidu", **overrides):
    user = await create_user(client, admin_headers, "member")
    key = await create_api_key(
        client, admin_headers, user["id"], "member-key", daily_limit=100, rpm_limit=100
    )
    account = await create_account(
        client, admin_headers, provider, f"{provider}-main", **overrides
    )
    return auth_headers(key["key"]), key, account


async def test_repeated_request_hits_cache(client, admin_headers, app) -> None:
    key_headers, key, _ = await setup_access(client, admin_headers)
    image = make_image_bytes()
    with respx.mock(assert_all_called=False) as mock:
        mock.post(BAIDU_TOKEN_URL).mock(return_value=baidu_token())
        ocr_route = mock.post(BAIDU_OCR_URL).mock(return_value=baidu_words("缓存"))
        first = await client.post(
            "/v1/ocr/image",
            headers=key_headers,
            files={"file": ("a.png", image, "image/png")},
        )
        second = await client.post(
            "/v1/ocr/image",
            headers=key_headers,
            files={"file": ("a.png", image, "image/png")},
        )
    assert first.status_code == 200
    assert first.json()["cached"] is False
    assert first.json()["quota"]["used"] == 1
    assert second.status_code == 200
    assert second.json()["cached"] is True
    assert second.json()["quota"]["used"] == 0
    assert second.json()["text"] == "缓存"
    assert ocr_route.call_count == 1
    state = app.state.gw
    async with state.session_factory() as session:
        events = (
            await session.execute(
                select(UsageEvent).where(UsageEvent.api_key_id == key["id"])
            )
        ).scalars().all()
    assert len(events) == 2
    assert events[0].quota_used == 1
    assert events[1].quota_used == 0
    assert events[1].cached is True


async def test_cache_is_isolated_by_provider(client, admin_headers) -> None:
    await setup_access(client, admin_headers, "baidu")
    await create_account(client, admin_headers, "tencent", "tencent-main")
    user = await create_user(client, admin_headers, "other")
    key = await create_api_key(
        client, admin_headers, user["id"], "other-key", daily_limit=100, rpm_limit=100
    )
    key_headers = auth_headers(key["key"])
    image = make_image_bytes()
    with respx.mock(assert_all_called=False) as mock:
        mock.post(BAIDU_TOKEN_URL).mock(return_value=baidu_token())
        baidu_route = mock.post(BAIDU_OCR_URL).mock(return_value=baidu_words("baidu"))
        tencent_route = mock.post(TENCENT_URL).mock(return_value=tencent_ok("tencent"))
        first = await client.post(
            "/v1/ocr/image",
            headers=key_headers,
            files={"file": ("a.png", image, "image/png")},
            data={"provider": "baidu"},
        )
        second = await client.post(
            "/v1/ocr/image",
            headers=key_headers,
            files={"file": ("a.png", image, "image/png")},
            data={"provider": "tencent"},
        )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["provider"] == "baidu"
    assert second.json()["provider"] == "tencent"
    assert second.json()["cached"] is False
    assert baidu_route.call_count == 1
    assert tencent_route.call_count == 1


async def test_cache_clear_forces_vendor_call(client, admin_headers) -> None:
    key_headers, _, _ = await setup_access(client, admin_headers)
    image = make_image_bytes()
    with respx.mock(assert_all_called=False) as mock:
        mock.post(BAIDU_TOKEN_URL).mock(return_value=baidu_token())
        ocr_route = mock.post(BAIDU_OCR_URL).mock(return_value=baidu_words("x"))
        await client.post(
            "/v1/ocr/image",
            headers=key_headers,
            files={"file": ("a.png", image, "image/png")},
        )
        cleared = await client.post("/api/admin/cache/clear", headers=admin_headers)
        assert cleared.status_code == 200
        assert cleared.json()["cleared"] == 1
        third = await client.post(
            "/v1/ocr/image",
            headers=key_headers,
            files={"file": ("a.png", image, "image/png")},
        )
    assert third.status_code == 200
    assert third.json()["cached"] is False
    assert ocr_route.call_count == 2


async def test_empty_text_is_not_cached(client, admin_headers) -> None:
    key_headers, _, _ = await setup_access(client, admin_headers)
    image = make_image_bytes()
    with respx.mock(assert_all_called=False) as mock:
        mock.post(BAIDU_TOKEN_URL).mock(return_value=baidu_token())
        ocr_route = mock.post(BAIDU_OCR_URL).mock(return_value=baidu_words())
        first = await client.post(
            "/v1/ocr/image",
            headers=key_headers,
            files={"file": ("a.png", image, "image/png")},
        )
        second = await client.post(
            "/v1/ocr/image",
            headers=key_headers,
            files={"file": ("a.png", image, "image/png")},
        )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["cached"] is False
    assert second.json()["cached"] is False
    assert ocr_route.call_count == 2


async def test_url_input_success_and_private_rejection(
    client, admin_headers, monkeypatch
) -> None:
    key_headers, _, _ = await setup_access(client, admin_headers)

    def fake_resolve(host: str, port: int):
        if host == "private.example":
            return [ipaddress.ip_address("127.0.0.1")]
        return [ipaddress.ip_address("93.184.216.34")]

    monkeypatch.setattr(ssrf, "_resolve", fake_resolve)
    image = make_image_bytes()
    with respx.mock(assert_all_called=False) as mock:
        mock.get("https://public.example/a.png").mock(
            return_value=httpx.Response(200, content=image)
        )
        mock.post(BAIDU_TOKEN_URL).mock(return_value=baidu_token())
        mock.post(BAIDU_OCR_URL).mock(return_value=baidu_words("url"))
        success = await client.post(
            "/v1/ocr/image",
            headers=key_headers,
            json={"image_url": "https://public.example/a.png"},
        )
    assert success.status_code == 200, success.text
    assert success.json()["text"] == "url"
    private = await client.post(
        "/v1/ocr/image",
        headers=key_headers,
        json={"image_url": "https://private.example/a.png"},
    )
    assert private.status_code == 400


async def test_usage_summary_and_logs(client, admin_headers, app) -> None:
    user = await create_user(client, admin_headers, "member")
    key = await create_api_key(
        client, admin_headers, user["id"], "member-key", daily_limit=100, rpm_limit=100
    )
    state = app.state.gw
    now = utcnow()
    async with state.session_factory() as session:
        session.add_all(
            [
                UsageEvent(
                    request_id="u1",
                    user_id=user["id"],
                    api_key_id=key["id"],
                    provider="baidu",
                    success=True,
                    latency_ms=10,
                    quota_used=1,
                    cached=False,
                    created_at=now,
                ),
                UsageEvent(
                    request_id="u2",
                    user_id=user["id"],
                    api_key_id=key["id"],
                    provider="baidu",
                    success=True,
                    latency_ms=5,
                    quota_used=0,
                    cached=True,
                    created_at=now,
                ),
                UsageEvent(
                    request_id="u3",
                    user_id=user["id"],
                    api_key_id=key["id"],
                    provider="tencent",
                    success=False,
                    error_code="PROVIDER_ERROR",
                    latency_ms=20,
                    quota_used=0,
                    cached=False,
                    created_at=now - timedelta(days=30),
                ),
            ]
        )
        await session.commit()

    summary = await client.get(
        "/api/admin/usage/summary?group_by=provider", headers=admin_headers
    )
    assert summary.status_code == 200
    rows = {row["key"]: row for row in summary.json()["rows"]}
    assert rows["baidu"]["requests"] == 2
    assert rows["baidu"]["success"] == 2
    assert rows["baidu"]["cached"] == 1
    assert rows["baidu"]["quota_used"] == 1
    assert "tencent" not in rows  # 30 days ago is outside the default 7-day window

    logs = await client.get("/api/admin/logs?limit=2&offset=0", headers=admin_headers)
    assert logs.status_code == 200
    assert len(logs.json()["rows"]) == 2
    assert "text" not in logs.json()["rows"][0]
    second_page = await client.get(
        "/api/admin/logs?limit=2&offset=2", headers=admin_headers
    )
    assert len(second_page.json()["rows"]) == 1
    failures = await client.get(
        "/api/admin/logs?success=false", headers=admin_headers
    )
    assert failures.json()["rows"][0]["error_code"] == "PROVIDER_ERROR"


def test_run_docs_cover_quickstart_and_operations() -> None:
    root = Path(__file__).resolve().parents[2]
    readme = (root / "README.md").read_text(encoding="utf-8")
    for needle in (
        "uv sync",
        "alembic upgrade head",
        "MASTER_KEY",
        "ADMIN_PASSWORD",
        "--workers 1",
        "sqlite3",
        ".backup",
        "以官网为准",
        "HTTPS",
        "RPO",
        "RTO",
    ):
        assert needle in readme
    example = (root / ".env.example").read_text(encoding="utf-8")
    assert "change-me-please" in example
    assert "AKID" not in example
