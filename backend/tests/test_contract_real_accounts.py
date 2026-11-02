from __future__ import annotations

import os
import time
from io import BytesIO

import httpx
import pytest
from PIL import Image, ImageDraw, ImageFont

from app.providers.baidu import BaiduAdapter
from app.providers.base import AccountRuntime
from app.providers.tencent import TencentAdapter
from app.utils.images import normalize_image

pytestmark = [pytest.mark.contract]

MAX_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 40_000_000


def chinese_image() -> bytes:
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 40)
        text = "你好 世界"
    except OSError:
        font = ImageFont.load_default()
        text = "OCR TEST 123"
    image = Image.new("RGB", (480, 160), "white")
    ImageDraw.Draw(image).text((20, 50), text, fill="black", font=font)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _baidu_account() -> AccountRuntime:
    return AccountRuntime(
        id=9001,
        provider="baidu",
        name="contract-baidu",
        credentials={
            "app_id": os.environ["BAIDU_APP_ID"],
            "api_key": os.environ["BAIDU_API_KEY"],
            "secret_key": os.environ["BAIDU_SECRET_KEY"],
        },
        priority=100,
        weight=1,
        enabled=True,
        timeout_ms=15000,
        max_concurrency=1,
        qps_limit=None,
        quota_daily=None,
        quota_monthly=None,
        quota_total=None,
        reset_day=1,
    )


def _tencent_account() -> AccountRuntime:
    return AccountRuntime(
        id=9002,
        provider="tencent",
        name="contract-tencent",
        credentials={
            "secret_id": os.environ["TENCENT_SECRET_ID"],
            "secret_key": os.environ["TENCENT_SECRET_KEY"],
        },
        priority=100,
        weight=1,
        enabled=True,
        timeout_ms=15000,
        max_concurrency=1,
        qps_limit=None,
        quota_daily=None,
        quota_monthly=None,
        quota_total=None,
        reset_day=1,
    )


@pytest.mark.skipif(
    not all(
        os.environ.get(name)
        for name in ("BAIDU_APP_ID", "BAIDU_API_KEY", "BAIDU_SECRET_KEY")
    ),
    reason="local Baidu credentials not configured",
)
async def test_baidu_contract_real_account() -> None:
    image = normalize_image(chinese_image(), "baidu", MAX_BYTES, MAX_PIXELS)
    async with httpx.AsyncClient(trust_env=False, timeout=20.0) as client:
        adapter = BaiduAdapter(client)
        started = time.monotonic()
        result = await adapter.recognize(_baidu_account(), image, "zh", 15.0)
        latency_ms = int((time.monotonic() - started) * 1000)
    assert result.text.strip(), "baidu returned empty text"
    print(f"baidu contract latency_ms={latency_ms} text={result.text[:80]!r}")


@pytest.mark.skipif(
    not all(
        os.environ.get(name) for name in ("TENCENT_SECRET_ID", "TENCENT_SECRET_KEY")
    ),
    reason="local Tencent credentials not configured",
)
async def test_tencent_contract_real_account() -> None:
    image = normalize_image(chinese_image(), "tencent", MAX_BYTES, MAX_PIXELS)
    async with httpx.AsyncClient(trust_env=False, timeout=20.0) as client:
        adapter = TencentAdapter(client)
        started = time.monotonic()
        result = await adapter.recognize(_tencent_account(), image, "zh", 15.0)
        latency_ms = int((time.monotonic() - started) * 1000)
    assert result.text.strip(), "tencent returned empty text"
    print(f"tencent contract latency_ms={latency_ms} text={result.text[:80]!r}")
