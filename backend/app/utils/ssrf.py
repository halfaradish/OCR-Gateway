from __future__ import annotations

import asyncio
import ipaddress
import socket
from urllib.parse import urlsplit

import httpx

from app.providers.base import UrlFetchError

MAX_REDIRECTS = 3
_METADATA_IP = ipaddress.ip_address("169.254.169.254")


def _is_forbidden(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if address == _METADATA_IP:
        return True
    return (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )


def _parse_target(url: str) -> tuple[str, int, str]:
    try:
        parsed = urlsplit(url)
    except ValueError as exc:
        raise UrlFetchError("invalid url") from exc
    if parsed.scheme not in ("http", "https"):
        raise UrlFetchError("only http/https urls are allowed")
    if parsed.username or parsed.password:
        raise UrlFetchError("url credentials are not allowed")
    host = parsed.hostname
    if not host:
        raise UrlFetchError("url has no host")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    return parsed.scheme, port, host


def _resolve(host: str, port: int) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UrlFetchError("url host cannot be resolved") from exc
    addresses: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for info in infos:
        sockaddr = info[4]
        try:
            addresses.append(ipaddress.ip_address(sockaddr[0]))
        except ValueError:
            continue
    if not addresses:
        raise UrlFetchError("url host cannot be resolved")
    return addresses


async def validate_url(url: str) -> None:
    _, port, host = _parse_target(url)
    loop = asyncio.get_running_loop()
    addresses = await loop.run_in_executor(None, _resolve, host, port)
    for address in addresses:
        if _is_forbidden(address):
            raise UrlFetchError("url target is not allowed")


async def fetch_image(
    client: httpx.AsyncClient,
    url: str,
    timeout_seconds: float,
    max_bytes: int,
) -> bytes:
    current = url
    redirects = 0
    while True:
        await validate_url(current)
        try:
            async with client.stream(
                "GET",
                current,
                timeout=timeout_seconds,
                follow_redirects=False,
            ) as response:
                if response.status_code in (301, 302, 303, 307, 308):
                    location = response.headers.get("Location")
                    redirects += 1
                    if not location or redirects > MAX_REDIRECTS:
                        raise UrlFetchError("too many redirects")
                    current = str(httpx.URL(current).join(location))
                    continue
                if response.status_code != 200:
                    raise UrlFetchError("url fetch failed")
                chunks: list[bytes] = []
                total = 0
                async for chunk in response.aiter_bytes():
                    total += len(chunk)
                    if total > max_bytes:
                        raise UrlFetchError("url image exceeds the size limit")
                    chunks.append(chunk)
                if total == 0:
                    raise UrlFetchError("url returned an empty body")
                return b"".join(chunks)
        except UrlFetchError:
            raise
        except httpx.TimeoutException as exc:
            raise UrlFetchError("url fetch timed out") from exc
        except httpx.HTTPError as exc:
            raise UrlFetchError("url fetch failed") from exc
