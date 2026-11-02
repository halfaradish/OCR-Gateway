from __future__ import annotations

import base64
import logging
from datetime import UTC, datetime, timedelta

import httpx

from app.providers.base import (
    LANGUAGE_MAP,
    AccountRuntime,
    ErrorKind,
    InputError,
    Line,
    ProviderResult,
    RetryableError,
)

logger = logging.getLogger(__name__)

TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"
OCR_URL = "https://aip.baidubce.com/rest/2.0/ocr/v1/general_basic"
AUTH_CODES = {110, 111}
QUOTA_CODES = {17, 19, 216604}
RATE_CODES = {18, 4}
INPUT_CODES = {100, 216201}
TOKEN_REFRESH_MARGIN = timedelta(minutes=5)


class BaiduAdapter:
    provider = "baidu"

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client
        self._tokens: dict[int, tuple[str, datetime, str]] = {}

    def invalidate(self, account_id: int) -> None:
        self._tokens.pop(account_id, None)

    async def recognize(
        self,
        account: AccountRuntime,
        image: bytes,
        language: str,
        timeout: float,
    ) -> ProviderResult:
        encoded = base64.b64encode(image).decode("ascii")
        language_type = LANGUAGE_MAP["baidu"].get(language, "CHN_ENG")
        for attempt in (0, 1):
            token = await self._get_token(account, timeout)
            try:
                response = await self._client.post(
                    OCR_URL,
                    params={"access_token": token},
                    data={"image": encoded, "language_type": language_type},
                    timeout=timeout,
                )
            except httpx.TimeoutException as exc:
                raise RetryableError(ErrorKind.TIMEOUT, "baidu request timed out") from exc
            except httpx.HTTPError as exc:
                raise RetryableError(ErrorKind.TIMEOUT, "baidu network error") from exc

            if response.status_code in (401, 403):
                if attempt == 0:
                    self.invalidate(account.id)
                    continue
                raise RetryableError(ErrorKind.AUTH_FAILED, "baidu rejected credentials")
            if response.status_code == 429:
                retry_after = _parse_retry_after(response.headers.get("Retry-After"))
                raise RetryableError(
                    ErrorKind.RATE_LIMITED, "baidu rate limited", retry_after
                )
            if response.status_code >= 500:
                raise RetryableError(ErrorKind.PROVIDER_ERROR, "baidu server error")

            try:
                payload = response.json()
            except ValueError as exc:
                raise RetryableError(
                    ErrorKind.PROVIDER_ERROR, "baidu returned invalid json"
                ) from exc
            if not isinstance(payload, dict):
                raise RetryableError(ErrorKind.PROVIDER_ERROR, "baidu returned invalid json")

            error_code = payload.get("error_code")
            if error_code is not None:
                code = int(error_code)
                if code in AUTH_CODES:
                    self.invalidate(account.id)
                    if attempt == 0:
                        continue
                    raise RetryableError(
                        ErrorKind.AUTH_FAILED, str(payload.get("error_msg", "auth failed"))
                    )
                if code in QUOTA_CODES:
                    raise RetryableError(
                        ErrorKind.QUOTA_EXCEEDED, str(payload.get("error_msg", "quota"))
                    )
                if code in RATE_CODES:
                    raise RetryableError(
                        ErrorKind.RATE_LIMITED, str(payload.get("error_msg", "rate limited"))
                    )
                if code in INPUT_CODES:
                    raise InputError(str(payload.get("error_msg", "invalid input")))
                raise RetryableError(
                    ErrorKind.PROVIDER_ERROR, f"baidu error_code={code}"
                )

            words = payload.get("words_result") or []
            lines = [
                Line(text=str(item.get("words", "")), confidence=None)
                for item in words
                if isinstance(item, dict)
            ]
            return ProviderResult(
                provider="baidu",
                text="\n".join(line.text for line in lines),
                lines=lines,
            )
        raise RetryableError(ErrorKind.AUTH_FAILED, "baidu auth failed")

    async def _get_token(self, account: AccountRuntime, timeout: float) -> str:
        cached = self._tokens.get(account.id)
        api_key = account.credentials.get("api_key", "")
        now = datetime.now(UTC)
        if cached is not None and cached[2] == api_key and cached[1] > now + TOKEN_REFRESH_MARGIN:
            return cached[0]

        try:
            response = await self._client.post(
                TOKEN_URL,
                params={
                    "grant_type": "client_credentials",
                    "client_id": api_key,
                    "client_secret": account.credentials.get("secret_key", ""),
                },
                timeout=min(2.0, timeout),
            )
        except httpx.TimeoutException as exc:
            raise RetryableError(ErrorKind.TIMEOUT, "baidu token request timed out") from exc
        except httpx.HTTPError as exc:
            raise RetryableError(ErrorKind.PROVIDER_ERROR, "baidu token network error") from exc

        if response.status_code in (401, 403):
            raise RetryableError(ErrorKind.AUTH_FAILED, "baidu token rejected")
        if response.status_code == 429:
            raise RetryableError(ErrorKind.RATE_LIMITED, "baidu token rate limited")
        if response.status_code >= 500:
            raise RetryableError(ErrorKind.PROVIDER_ERROR, "baidu token server error")

        try:
            payload = response.json()
        except ValueError as exc:
            raise RetryableError(
                ErrorKind.PROVIDER_ERROR, "baidu token invalid json"
            ) from exc
        if not isinstance(payload, dict):
            raise RetryableError(ErrorKind.PROVIDER_ERROR, "baidu token invalid json")

        if payload.get("error"):
            error = str(payload.get("error"))
            description = str(payload.get("error_description", ""))
            if error in {"invalid_client", "invalid_grant", "unauthorized_client"}:
                raise RetryableError(ErrorKind.AUTH_FAILED, description or error)
            raise RetryableError(ErrorKind.PROVIDER_ERROR, description or error)

        token = payload.get("access_token")
        if not token:
            raise RetryableError(ErrorKind.PROVIDER_ERROR, "baidu token missing")
        expires_in = int(payload.get("expires_in", 2592000))
        self._tokens[account.id] = (
            str(token),
            now + timedelta(seconds=expires_in),
            api_key,
        )
        return str(token)


def _parse_retry_after(raw: str | None) -> float | None:
    if not raw:
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    return min(max(value, 1.0), 300.0)
