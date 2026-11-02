from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from datetime import UTC, datetime

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

TENCENT_HOST = "ocr.tencentcloudapi.com"
TENCENT_SERVICE = "ocr"
TENCENT_VERSION = "2018-11-19"
SIGNED_HEADERS = "content-type;host;x-tc-action"
CONTENT_TYPE = "application/json; charset=utf-8"

AUTH_CODES = {"AuthFailure.SignatureFailure", "AuthFailure.SecretIdNotFound"}
QUOTA_CODES = {"ResourceUnavailable.InArrears"}
RATE_CODES = {"RequestLimitExceeded"}
INPUT_CODES = {"FailedOperation.ImageDecodeFailed", "InvalidParameterValue"}
SIGNATURE_EXPIRE = "AuthFailure.SignatureExpire"


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hmac_sha256(key: bytes, message: str) -> bytes:
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()


def canonical_request(
    action: str, payload: bytes, host: str = TENCENT_HOST
) -> tuple[str, str]:
    canonical_headers = (
        f"content-type:{CONTENT_TYPE}\n"
        f"host:{host}\n"
        f"x-tc-action:{action.lower()}\n"
    )
    request = "\n".join(
        [
            "POST",
            "/",
            "",
            canonical_headers,
            SIGNED_HEADERS,
            _sha256_hex(payload),
        ]
    )
    return request, SIGNED_HEADERS


def tc3_signature(
    secret_key: str,
    timestamp: int,
    service: str,
    host: str,
    action: str,
    payload: bytes,
) -> tuple[str, str]:
    """Return (signature_hex, canonical_request_string) per Tencent TC3."""
    date = datetime.fromtimestamp(timestamp, tz=UTC).strftime("%Y-%m-%d")
    request, signed_headers = canonical_request(action, payload, host)
    string_to_sign = "\n".join(
        [
            "TC3-HMAC-SHA256",
            str(timestamp),
            f"{date}/{service}/tc3_request",
            _sha256_hex(request.encode("utf-8")),
        ]
    )
    secret_date = _hmac_sha256(("TC3" + secret_key).encode("utf-8"), date)
    secret_service = _hmac_sha256(secret_date, service)
    secret_signing = _hmac_sha256(secret_service, "tc3_request")
    signature = hmac.new(
        secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return signature, request


def build_tc3_headers(
    secret_id: str,
    secret_key: str,
    action: str,
    payload: bytes,
    timestamp: int,
    service: str = TENCENT_SERVICE,
    host: str = TENCENT_HOST,
    version: str = TENCENT_VERSION,
) -> dict[str, str]:
    signature, _ = tc3_signature(secret_key, timestamp, service, host, action, payload)
    date = datetime.fromtimestamp(timestamp, tz=UTC).strftime("%Y-%m-%d")
    credential_scope = f"{date}/{service}/tc3_request"
    authorization = (
        f"TC3-HMAC-SHA256 Credential={secret_id}/{credential_scope}, "
        f"SignedHeaders={SIGNED_HEADERS}, Signature={signature}"
    )
    return {
        "Authorization": authorization,
        "Content-Type": CONTENT_TYPE,
        "Host": host,
        "X-TC-Action": action,
        "X-TC-Timestamp": str(timestamp),
        "X-TC-Version": version,
    }


class TencentAdapter:
    provider = "tencent"

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    def invalidate(self, account_id: int) -> None:
        return None

    async def recognize(
        self,
        account: AccountRuntime,
        image: bytes,
        language: str,
        timeout: float,
    ) -> ProviderResult:
        action = "GeneralBasicOCR"
        encoded = base64.b64encode(image).decode("ascii")
        body = {
            "ImageBase64": encoded,
            "LanguageType": LANGUAGE_MAP["tencent"].get(language, "auto"),
        }
        payload = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        timestamp = int(time.time())
        headers = build_tc3_headers(
            account.credentials.get("secret_id", ""),
            account.credentials.get("secret_key", ""),
            action,
            payload,
            timestamp,
        )
        try:
            response = await self._client.post(
                f"https://{TENCENT_HOST}",
                content=payload,
                headers=headers,
                timeout=timeout,
            )
        except httpx.TimeoutException as exc:
            raise RetryableError(ErrorKind.TIMEOUT, "tencent request timed out") from exc
        except httpx.HTTPError as exc:
            raise RetryableError(ErrorKind.TIMEOUT, "tencent network error") from exc

        if response.status_code == 401:
            raise RetryableError(ErrorKind.AUTH_FAILED, "tencent rejected credentials")
        if response.status_code == 403:
            raise RetryableError(ErrorKind.AUTH_FAILED, "tencent rejected credentials")
        if response.status_code == 429:
            raise RetryableError(ErrorKind.RATE_LIMITED, "tencent rate limited")
        if response.status_code >= 500:
            raise RetryableError(ErrorKind.PROVIDER_ERROR, "tencent server error")

        try:
            payload_json = response.json()
        except ValueError as exc:
            raise RetryableError(
                ErrorKind.PROVIDER_ERROR, "tencent returned invalid json"
            ) from exc
        if not isinstance(payload_json, dict):
            raise RetryableError(ErrorKind.PROVIDER_ERROR, "tencent returned invalid json")
        payload_obj = payload_json.get("Response")
        if not isinstance(payload_obj, dict):
            raise RetryableError(ErrorKind.PROVIDER_ERROR, "tencent response missing")

        error = payload_obj.get("Error")
        if isinstance(error, dict):
            code = str(error.get("Code", ""))
            message = str(error.get("Message", ""))
            if code == SIGNATURE_EXPIRE:
                raise RetryableError(ErrorKind.PROVIDER_ERROR, message, 30.0)
            if code in AUTH_CODES:
                raise RetryableError(ErrorKind.AUTH_FAILED, message)
            if code in QUOTA_CODES:
                raise RetryableError(ErrorKind.QUOTA_EXCEEDED, message)
            if code in RATE_CODES:
                raise RetryableError(ErrorKind.RATE_LIMITED, message)
            if code in INPUT_CODES:
                raise InputError(message)
            raise RetryableError(
                ErrorKind.PROVIDER_ERROR, f"tencent error={code or 'unknown'}"
            )

        detections = payload_obj.get("TextDetections") or []
        lines: list[Line] = []
        if isinstance(detections, list):
            for item in detections:
                if not isinstance(item, dict):
                    continue
                confidence = item.get("Confidence")
                try:
                    confidence_value = float(confidence) if confidence is not None else None
                except (TypeError, ValueError):
                    confidence_value = None
                lines.append(
                    Line(text=str(item.get("DetectedText", "")), confidence=confidence_value)
                )
        return ProviderResult(
            provider="tencent",
            text="\n".join(line.text for line in lines),
            lines=lines,
        )
