from __future__ import annotations

import asyncio

import httpx

from app.providers.baidu import TOKEN_URL, BaiduAdapter
from app.providers.base import AccountRuntime


class FakeClient:
    def __init__(self) -> None:
        self.token_calls = 0
        self.ocr_calls = 0

    async def post(self, url: str, **kwargs: object) -> httpx.Response:
        if url == TOKEN_URL:
            self.token_calls += 1
            await asyncio.sleep(0.05)
            return httpx.Response(
                200, json={"access_token": "tok", "expires_in": 2592000}
            )
        self.ocr_calls += 1
        return httpx.Response(200, json={"words_result": [{"words": "ok"}]})


def make_account() -> AccountRuntime:
    return AccountRuntime(
        id=1,
        provider="baidu",
        name="baidu",
        credentials={"app_id": "app", "api_key": "AK", "secret_key": "SK"},
        priority=100,
        weight=1,
        enabled=True,
        timeout_ms=8000,
        max_concurrency=10,
        qps_limit=None,
        quota_daily=None,
        quota_monthly=None,
        quota_total=None,
        reset_day=1,
    )


async def test_concurrent_token_refresh_is_coalesced() -> None:
    client = FakeClient()
    adapter = BaiduAdapter(client)  # type: ignore[arg-type]
    account = make_account()
    results = await asyncio.gather(
        *(adapter.recognize(account, b"img", "zh", 5.0) for _ in range(5))
    )
    assert client.token_calls == 1
    assert client.ocr_calls == 5
    assert all(result.text == "ok" for result in results)


async def test_invalidate_forces_new_token_fetch() -> None:
    client = FakeClient()
    adapter = BaiduAdapter(client)  # type: ignore[arg-type]
    account = make_account()
    await adapter.recognize(account, b"img", "zh", 5.0)
    adapter.invalidate(account.id)
    await adapter.recognize(account, b"img", "zh", 5.0)
    assert client.token_calls == 2
    assert client.ocr_calls == 2
