from __future__ import annotations

import logging

import httpx
import pytest
import respx

from app.logging_setup import configure_logging
from app.providers.baidu import OCR_URL, TOKEN_URL, BaiduAdapter
from app.providers.base import (
    AccountRuntime,
    ErrorKind,
    InputError,
    RetryableError,
)


def make_account(account_id: int = 1) -> AccountRuntime:
    return AccountRuntime(
        id=account_id,
        provider="baidu",
        name="baidu",
        credentials={"app_id": "app", "api_key": "AK", "secret_key": "SK"},
        priority=100,
        weight=1,
        enabled=True,
        timeout_ms=8000,
        max_concurrency=2,
        qps_limit=None,
        quota_daily=None,
        quota_monthly=None,
        quota_total=None,
        reset_day=1,
    )


@pytest.fixture
async def async_client():
    async with httpx.AsyncClient(trust_env=False) as client:
        yield client


def _token_response() -> httpx.Response:
    return httpx.Response(200, json={"access_token": "tok", "expires_in": 2592000})


def _words_response(*words: str) -> httpx.Response:
    return httpx.Response(
        200, json={"words_result": [{"words": word} for word in words]}
    )


async def test_token_is_cached_across_calls(async_client) -> None:
    adapter = BaiduAdapter(async_client)
    account = make_account()
    with respx.mock(assert_all_called=True) as mock:
        token_route = mock.post(TOKEN_URL).mock(return_value=_token_response())
        ocr_route = mock.post(OCR_URL).mock(return_value=_words_response("第一行"))
        first = await adapter.recognize(account, b"img", "zh", 5.0)
        second = await adapter.recognize(account, b"img", "zh", 5.0)
    assert token_route.call_count == 1
    assert ocr_route.call_count == 2
    assert first.text == "第一行"
    assert second.text == "第一行"
    assert first.lines[0].confidence is None


async def test_auth_error_110_refreshes_token_once(async_client) -> None:
    adapter = BaiduAdapter(async_client)
    account = make_account()
    with respx.mock(assert_all_called=True) as mock:
        token_route = mock.post(TOKEN_URL).mock(return_value=_token_response())
        mock.post(OCR_URL).mock(
            side_effect=[
                httpx.Response(200, json={"error_code": 110, "error_msg": "expired"}),
                _words_response("ok"),
            ]
        )
        result = await adapter.recognize(account, b"img", "zh", 5.0)
    assert result.text == "ok"
    assert token_route.call_count == 2


async def test_auth_error_after_retry_raises(async_client) -> None:
    adapter = BaiduAdapter(async_client)
    account = make_account()
    with respx.mock(assert_all_called=True) as mock:
        mock.post(TOKEN_URL).mock(return_value=_token_response())
        mock.post(OCR_URL).mock(
            return_value=httpx.Response(
                200, json={"error_code": 111, "error_msg": "invalid token"}
            )
        )
        with pytest.raises(RetryableError) as raised:
            await adapter.recognize(account, b"img", "zh", 5.0)
    assert raised.value.kind is ErrorKind.AUTH_FAILED


@pytest.mark.parametrize(
    ("code", "kind"),
    [
        (17, ErrorKind.QUOTA_EXCEEDED),
        (216604, ErrorKind.QUOTA_EXCEEDED),
        (18, ErrorKind.RATE_LIMITED),
        (4, ErrorKind.RATE_LIMITED),
        (999, ErrorKind.PROVIDER_ERROR),
    ],
)
async def test_error_codes_map_to_kinds(async_client, code: int, kind: ErrorKind) -> None:
    adapter = BaiduAdapter(async_client)
    account = make_account()
    with respx.mock(assert_all_called=True) as mock:
        mock.post(TOKEN_URL).mock(return_value=_token_response())
        mock.post(OCR_URL).mock(
            return_value=httpx.Response(200, json={"error_code": code, "error_msg": "x"})
        )
        with pytest.raises(RetryableError) as raised:
            await adapter.recognize(account, b"img", "zh", 5.0)
    assert raised.value.kind is kind


async def test_input_error_is_not_retryable(async_client) -> None:
    adapter = BaiduAdapter(async_client)
    account = make_account()
    with respx.mock(assert_all_called=True) as mock:
        mock.post(TOKEN_URL).mock(return_value=_token_response())
        mock.post(OCR_URL).mock(
            return_value=httpx.Response(
                200, json={"error_code": 100, "error_msg": "invalid image"}
            )
        )
        with pytest.raises(InputError):
            await adapter.recognize(account, b"img", "zh", 5.0)


async def test_http_429_and_5xx_mapping(async_client) -> None:
    adapter = BaiduAdapter(async_client)
    account = make_account()
    with respx.mock() as mock:
        mock.post(TOKEN_URL).mock(return_value=_token_response())
        mock.post(OCR_URL).mock(return_value=httpx.Response(429, headers={"Retry-After": "5"}))
        with pytest.raises(RetryableError) as raised:
            await adapter.recognize(account, b"img", "zh", 5.0)
        assert raised.value.kind is ErrorKind.RATE_LIMITED
        assert raised.value.cooldown_seconds == 5.0
    adapter.invalidate(account.id)
    with respx.mock() as mock:
        mock.post(TOKEN_URL).mock(return_value=_token_response())
        mock.post(OCR_URL).mock(return_value=httpx.Response(503))
        with pytest.raises(RetryableError) as raised:
            await adapter.recognize(account, b"img", "zh", 5.0)
        assert raised.value.kind is ErrorKind.PROVIDER_ERROR


async def test_language_mapping_uses_chn_eng(async_client) -> None:
    adapter = BaiduAdapter(async_client)
    account = make_account()
    with respx.mock(assert_all_called=True) as mock:
        mock.post(TOKEN_URL).mock(return_value=_token_response())
        ocr_route = mock.post(OCR_URL).mock(return_value=_words_response("x"))
        await adapter.recognize(account, b"img", "en", 5.0)
    assert ocr_route.calls.last.request.content == b"image=aW1n&language_type=ENG"


async def test_httpx_logger_is_warning() -> None:
    configure_logging("INFO")
    assert logging.getLogger("httpx").level == logging.WARNING
    assert logging.getLogger("httpcore").level == logging.WARNING
