from __future__ import annotations

import base64
import hashlib
import json

import httpx
import pytest
import respx

from app.providers.base import AccountRuntime, ErrorKind, InputError, RetryableError
from app.providers.tencent import (
    TENCENT_HOST,
    TencentAdapter,
    build_tc3_headers,
    canonical_request,
    tc3_signature,
)

TENCENT_URL = f"https://{TENCENT_HOST}"

GOLDEN_SECRET_ID = "AKID" + "*" * 32
GOLDEN_SECRET_KEY = "*" * 32
GOLDEN_PAYLOAD = (
    br'{"Limit": 1, "Filters": [{"Values": ["\u672a\u547d\u540d"], "Name": "instance-name"}]}'
)
GOLDEN_SIGNATURE = "10b1a37a7301a02ca19a647ad722d5e43b4b3cff309d421d85b46093f6ab6c4f"
GOLDEN_CANONICAL_HASH = "7019a55be8395899b900fb5564e4200d984910f34794a27cb3fb7d10ff6a1e84"


def make_account() -> AccountRuntime:
    return AccountRuntime(
        id=1,
        provider="tencent",
        name="tencent",
        credentials={"secret_id": "AKID-test", "secret_key": "SK-test"},
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


def test_tc3_golden_signature_matches_official_example() -> None:
    signature, request = tc3_signature(
        GOLDEN_SECRET_KEY,
        1551113065,
        "cvm",
        "cvm.tencentcloudapi.com",
        "DescribeInstances",
        GOLDEN_PAYLOAD,
    )
    assert signature == GOLDEN_SIGNATURE
    assert hashlib.sha256(request.encode("utf-8")).hexdigest() == GOLDEN_CANONICAL_HASH
    headers = build_tc3_headers(
        GOLDEN_SECRET_ID,
        GOLDEN_SECRET_KEY,
        "DescribeInstances",
        GOLDEN_PAYLOAD,
        1551113065,
        service="cvm",
        host="cvm.tencentcloudapi.com",
    )
    assert headers["Authorization"] == (
        "TC3-HMAC-SHA256 "
        f"Credential={GOLDEN_SECRET_ID}/2019-02-25/cvm/tc3_request, "
        "SignedHeaders=content-type;host;x-tc-action, "
        f"Signature={GOLDEN_SIGNATURE}"
    )
    assert headers["X-TC-Version"] == "2018-11-19"


def test_canonical_request_includes_x_tc_action_lowercase() -> None:
    request, signed_headers = canonical_request("GeneralBasicOCR", b"{}")
    assert signed_headers == "content-type;host;x-tc-action"
    assert "x-tc-action:generalbasicocr" in request


async def test_tencent_success_maps_confidence_and_order(async_client) -> None:
    adapter = TencentAdapter(async_client)
    account = make_account()
    with respx.mock(assert_all_called=True) as mock:
        route = mock.post(TENCENT_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "Response": {
                        "TextDetections": [
                            {"DetectedText": "第一行", "Confidence": 95.5},
                            {"DetectedText": "第二行", "Confidence": 88.0},
                        ],
                        "RequestId": "req",
                    }
                },
            )
        )
        result = await adapter.recognize(account, b"img", "zh", 5.0)
    assert result.provider == "tencent"
    assert result.text == "第一行\n第二行"
    assert [line.text for line in result.lines] == ["第一行", "第二行"]
    assert result.lines[0].confidence == 95.5
    request = route.calls.last.request
    assert request.headers["X-TC-Action"] == "GeneralBasicOCR"
    assert request.headers["X-TC-Version"] == "2018-11-19"
    body = json.loads(request.content)
    assert body["ImageBase64"] == base64.b64encode(b"img").decode("ascii")
    assert body["LanguageType"] == "zh"


@pytest.mark.parametrize(
    ("code", "kind"),
    [
        ("AuthFailure.SignatureFailure", ErrorKind.AUTH_FAILED),
        ("AuthFailure.SecretIdNotFound", ErrorKind.AUTH_FAILED),
        ("ResourceUnavailable.InArrears", ErrorKind.QUOTA_EXCEEDED),
        ("RequestLimitExceeded", ErrorKind.RATE_LIMITED),
        ("InternalError", ErrorKind.PROVIDER_ERROR),
        ("SomethingNew", ErrorKind.PROVIDER_ERROR),
    ],
)
async def test_tencent_error_codes_map_to_kinds(
    async_client, code: str, kind: ErrorKind
) -> None:
    adapter = TencentAdapter(async_client)
    account = make_account()
    with respx.mock(assert_all_called=True) as mock:
        mock.post(TENCENT_URL).mock(
            return_value=httpx.Response(
                200, json={"Response": {"Error": {"Code": code, "Message": "x"}}}
            )
        )
        with pytest.raises(RetryableError) as raised:
            await adapter.recognize(account, b"img", "zh", 5.0)
    assert raised.value.kind is kind


async def test_signature_expire_is_provider_error_with_30s(async_client) -> None:
    adapter = TencentAdapter(async_client)
    account = make_account()
    with respx.mock(assert_all_called=True) as mock:
        mock.post(TENCENT_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "Response": {
                        "Error": {
                            "Code": "AuthFailure.SignatureExpire",
                            "Message": "expired",
                        }
                    }
                },
            )
        )
        with pytest.raises(RetryableError) as raised:
            await adapter.recognize(account, b"img", "zh", 5.0)
    assert raised.value.kind is ErrorKind.PROVIDER_ERROR
    assert raised.value.cooldown_seconds == 30.0


async def test_tencent_input_error_is_not_retryable(async_client) -> None:
    adapter = TencentAdapter(async_client)
    account = make_account()
    with respx.mock(assert_all_called=True) as mock:
        mock.post(TENCENT_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "Response": {
                        "Error": {
                            "Code": "FailedOperation.ImageDecodeFailed",
                            "Message": "bad image",
                        }
                    }
                },
            )
        )
        with pytest.raises(InputError):
            await adapter.recognize(account, b"img", "zh", 5.0)


async def test_tencent_http_status_mapping(async_client) -> None:
    adapter = TencentAdapter(async_client)
    account = make_account()
    for status_code, kind in (
        (401, ErrorKind.AUTH_FAILED),
        (429, ErrorKind.RATE_LIMITED),
        (503, ErrorKind.PROVIDER_ERROR),
    ):
        with respx.mock(assert_all_called=True) as mock:
            mock.post(TENCENT_URL).mock(return_value=httpx.Response(status_code))
            with pytest.raises(RetryableError) as raised:
                await adapter.recognize(account, b"img", "zh", 5.0)
        assert raised.value.kind is kind


async def test_tencent_timeout_maps_to_timeout(async_client) -> None:
    adapter = TencentAdapter(async_client)
    account = make_account()
    with respx.mock(assert_all_called=True) as mock:
        mock.post(TENCENT_URL).mock(side_effect=httpx.ConnectTimeout("boom"))
        with pytest.raises(RetryableError) as raised:
            await adapter.recognize(account, b"img", "zh", 5.0)
    assert raised.value.kind is ErrorKind.TIMEOUT
