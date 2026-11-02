from __future__ import annotations

import asyncio
import ipaddress

import httpx
import pytest
import respx

from app.core.cache import MAX_RESULT_BYTES, ResultCache
from app.utils import ssrf
from app.utils.ssrf import UrlFetchError, fetch_image, validate_url

PUBLIC_IP = ipaddress.ip_address("93.184.216.34")
PRIVATE_IP = ipaddress.ip_address("127.0.0.1")


def fake_resolve(host: str, port: int):
    try:
        return [ipaddress.ip_address(host)]
    except ValueError:
        pass
    if host == "localhost" or "private" in host:
        return [PRIVATE_IP]
    return [PUBLIC_IP]


@pytest.fixture(autouse=True)
def patch_resolver(monkeypatch):
    monkeypatch.setattr(ssrf, "_resolve", fake_resolve)


@pytest.fixture
async def async_client():
    async with httpx.AsyncClient(trust_env=False) as client:
        yield client


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.com/a.png",
        "file:///etc/passwd",
        "http://user:pass@example.com/a.png",
        "http://127.0.0.1/a.png",
        "http://localhost/a.png",
        "http://169.254.169.254/latest/meta-data",
        "http://10.0.0.1/a.png",
        "http://192.168.1.1/a.png",
        "http://[::1]/a.png",
    ],
)
async def test_rejects_unsafe_urls(url: str) -> None:
    with pytest.raises(UrlFetchError):
        await validate_url(url)


async def test_fetch_public_url(async_client) -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock.get("https://public.example/a.png").mock(
            return_value=httpx.Response(200, content=b"image-bytes")
        )
        data = await fetch_image(async_client, "https://public.example/a.png", 5.0, 1024)
    assert data == b"image-bytes"


async def test_fetch_rejects_private_redirect_without_second_request(async_client) -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock.get("https://public.example/a.png").mock(
            return_value=httpx.Response(
                302, headers={"Location": "http://private.example/secret.png"}
            )
        )
        private_route = mock.get("http://private.example/secret.png").mock(
            return_value=httpx.Response(200, content=b"nope")
        )
        with pytest.raises(UrlFetchError):
            await fetch_image(async_client, "https://public.example/a.png", 5.0, 1024)
    assert private_route.call_count == 0


async def test_fetch_rejects_too_many_redirects(async_client) -> None:
    with respx.mock(assert_all_called=False) as mock:
        for index in range(5):
            mock.get(f"https://public.example/{index}.png").mock(
                return_value=httpx.Response(
                    302, headers={"Location": f"https://public.example/{index + 1}.png"}
                )
            )
        with pytest.raises(UrlFetchError):
            await fetch_image(async_client, "https://public.example/0.png", 5.0, 1024)


async def test_fetch_rejects_oversized_body(async_client) -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock.get("https://public.example/big.png").mock(
            return_value=httpx.Response(200, content=b"x" * 2048)
        )
        with pytest.raises(UrlFetchError):
            await fetch_image(async_client, "https://public.example/big.png", 5.0, 1024)


async def test_fetch_timeout_maps_to_client_error(async_client) -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock.get("https://public.example/slow.png").mock(
            side_effect=httpx.ReadTimeout("slow")
        )
        with pytest.raises(UrlFetchError):
            await fetch_image(async_client, "https://public.example/slow.png", 5.0, 1024)


async def test_fetch_non_200_is_client_error(async_client) -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock.get("https://public.example/missing.png").mock(
            return_value=httpx.Response(404)
        )
        with pytest.raises(UrlFetchError):
            await fetch_image(async_client, "https://public.example/missing.png", 5.0, 1024)


def test_cache_rejects_empty_text() -> None:
    cache = ResultCache(True, 10, 60)
    cache.set("k", {"provider": "baidu", "text": "", "lines": []})
    assert cache.get("k") is None


def test_cache_rejects_oversized_results() -> None:
    cache = ResultCache(True, 10, 60)
    cache.set(
        "k",
        {"provider": "baidu", "text": "x" * (MAX_RESULT_BYTES + 1), "lines": []},
    )
    assert cache.get("k") is None


def test_cache_lru_eviction() -> None:
    cache = ResultCache(True, 2, 60)
    cache.set("a", {"provider": "baidu", "text": "a", "lines": []})
    cache.set("b", {"provider": "baidu", "text": "b", "lines": []})
    cache.set("c", {"provider": "baidu", "text": "c", "lines": []})
    assert cache.get("a") is None
    assert cache.get("b") is not None
    assert cache.get("c") is not None


async def test_cache_ttl_expiry() -> None:
    cache = ResultCache(True, 10, 0.05)
    cache.set("k", {"provider": "baidu", "text": "x", "lines": []})
    assert cache.get("k") is not None
    await asyncio.sleep(0.1)
    assert cache.get("k") is None


def test_cache_disabled() -> None:
    cache = ResultCache(False, 10, 60)
    cache.set("k", {"provider": "baidu", "text": "x", "lines": []})
    assert cache.get("k") is None
    assert cache.clear() == 0


async def test_rejects_invalid_port() -> None:
    with pytest.raises(UrlFetchError):
        await validate_url("http://example.com:notaport/a.png")


def test_ipv4_mapped_ipv6_is_forbidden() -> None:
    assert ssrf._is_forbidden(ipaddress.ip_address("::ffff:127.0.0.1"))
    assert ssrf._is_forbidden(ipaddress.ip_address("::ffff:169.254.169.254"))
    assert not ssrf._is_forbidden(ipaddress.ip_address("8.8.8.8"))


async def test_rejects_ipv4_mapped_loopback() -> None:
    with pytest.raises(UrlFetchError):
        await validate_url("http://[::ffff:127.0.0.1]/a.png")
