from __future__ import annotations

import asyncio
import base64
import binascii
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import UploadFile

from app.api.deps import ApiError, KeyContext, get_session, get_state, require_api_key
from app.core.scheduler import SchedulerError
from app.db import utcnow
from app.models import UsageEvent
from app.providers.base import PROVIDER_NAMES, InputError
from app.state import AppState
from app.utils.images import image_hash, normalize_image
from app.utils.ssrf import fetch_image

router = APIRouter(prefix="/v1")

VALID_LANGUAGES = {"zh", "en", "auto"}
VALID_PROVIDERS = {"auto", "baidu", "tencent"}


@dataclass
class _ParsedInput:
    data: bytes
    language: str
    provider: str


def _as_str(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _validate_options(language: str, provider: str) -> None:
    if language not in VALID_LANGUAGES:
        raise ApiError(400, "BAD_REQUEST", "unsupported language")
    if provider not in VALID_PROVIDERS:
        raise ApiError(400, "BAD_REQUEST", "unsupported provider")


def _decode_base64(value: str, max_bytes: int) -> bytes:
    try:
        data = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ApiError(400, "BAD_REQUEST", "invalid base64 image") from exc
    if len(data) > max_bytes:
        raise ApiError(400, "BAD_REQUEST", "image exceeds the upload size limit")
    return data


async def _parse_request(request: Request, state: AppState) -> _ParsedInput:
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    max_bytes = state.settings.max_upload_bytes
    if content_type == "multipart/form-data":
        try:
            form = await request.form()
        except Exception as exc:  # noqa: BLE001 - malformed multipart is a client error
            raise ApiError(400, "BAD_REQUEST", "invalid multipart body") from exc
        file = form.get("file")
        image_base64 = _as_str(form.get("image_base64"))
        image_url = _as_str(form.get("image_url"))
        language = _as_str(form.get("language")) or "zh"
        provider = _as_str(form.get("provider")) or "auto"
        provided = int(isinstance(file, UploadFile)) + int(bool(image_base64)) + int(
            bool(image_url)
        )
        if provided != 1:
            raise ApiError(400, "BAD_REQUEST", "provide exactly one image input")
        if isinstance(file, UploadFile):
            data = await file.read(max_bytes + 1)
            if len(data) > max_bytes:
                raise ApiError(400, "BAD_REQUEST", "image exceeds the upload size limit")
        elif image_base64:
            data = _decode_base64(image_base64, max_bytes)
        else:
            data = await fetch_image(
                state.http,
                image_url,
                state.settings.url_fetch_timeout_seconds,
                state.settings.url_fetch_max_bytes,
            )
    elif content_type == "application/json":
        try:
            body = await request.json()
        except ValueError as exc:
            raise ApiError(400, "BAD_REQUEST", "invalid json body") from exc
        if not isinstance(body, dict):
            raise ApiError(400, "BAD_REQUEST", "json body must be an object")
        image_base64_value = body.get("image_base64")
        image_url_value = body.get("image_url")
        language_value = body.get("language", "zh")
        provider_value = body.get("provider", "auto")
        if not isinstance(language_value, str) or not isinstance(provider_value, str):
            raise ApiError(400, "BAD_REQUEST", "invalid language or provider")
        language = language_value
        provider = provider_value
        has_b64 = isinstance(image_base64_value, str) and bool(image_base64_value)
        has_url = isinstance(image_url_value, str) and bool(image_url_value)
        if int(has_b64) + int(has_url) != 1:
            raise ApiError(400, "BAD_REQUEST", "provide exactly one image input")
        if has_b64:
            data = _decode_base64(str(image_base64_value), max_bytes)
        else:
            data = await fetch_image(
                state.http,
                str(image_url_value),
                state.settings.url_fetch_timeout_seconds,
                state.settings.url_fetch_max_bytes,
            )
    else:
        raise ApiError(400, "BAD_REQUEST", "unsupported content type")
    _validate_options(language, provider)
    return _ParsedInput(data=data, language=language, provider=provider)


def _response_payload(
    request_id: str,
    provider: str,
    text: str,
    lines: list[dict[str, Any]],
    latency_ms: int,
    cached: bool,
    quota_used: int,
) -> dict[str, Any]:
    warnings = ["EMPTY_TEXT"] if text == "" else []
    return {
        "request_id": request_id,
        "provider": provider,
        "text": text,
        "lines": lines,
        "latency_ms": latency_ms,
        "cached": cached,
        "quota": {"unit": "image", "used": quota_used},
        "warnings": warnings,
    }


async def _record_event(
    session: AsyncSession,
    state: AppState,
    *,
    request_id: str,
    context: KeyContext,
    provider: str,
    success: bool,
    error_code: str | None,
    latency_ms: int,
    quota_used: int,
    cached: bool,
    account_id: int | None,
    image_hash_value: str | None,
) -> None:
    session.add(
        UsageEvent(
            request_id=request_id,
            user_id=context.user.id,
            api_key_id=context.key.id,
            account_id=account_id,
            provider=provider,
            capability="general_text",
            success=success,
            error_code=error_code,
            latency_ms=latency_ms,
            quota_used=quota_used,
            cached=cached,
            image_hash=image_hash_value,
            created_at=utcnow(),
        )
    )
    await state.registry.persist(session)
    await session.commit()


@router.post("/ocr/image")
async def ocr_image(
    request: Request,
    context: KeyContext = Depends(require_api_key),
    state: AppState = Depends(get_state),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    started = time.monotonic()
    deadline = started + state.settings.request_deadline_ms / 1000.0
    request_id: str = request.state.request_id

    try:
        parsed = await _parse_request(request, state)
    except InputError as exc:
        raise ApiError(400, "BAD_REQUEST", str(exc)) from exc
    try:
        normalized = normalize_image(
            parsed.data,
            parsed.provider,
            state.settings.max_upload_bytes,
            state.settings.max_image_pixels,
        )
    except InputError as exc:
        raise ApiError(400, "BAD_REQUEST", str(exc)) from exc

    image_digest = image_hash(parsed.data)
    cache_key = state.cache.build_key(parsed.data, parsed.language, parsed.provider)
    cached = state.cache.get(cache_key)
    if cached is not None:
        latency = int((time.monotonic() - started) * 1000)
        await _record_event(
            session,
            state,
            request_id=request_id,
            context=context,
            provider=str(cached["provider"]),
            success=True,
            error_code=None,
            latency_ms=latency,
            quota_used=0,
            cached=True,
            account_id=None,
            image_hash_value=image_digest,
        )
        cached_lines = cached.get("lines", [])
        if not isinstance(cached_lines, list):
            cached_lines = []
        return _response_payload(
            request_id,
            str(cached["provider"]),
            str(cached["text"]),
            [dict(item) for item in cached_lines if isinstance(item, dict)],
            latency,
            True,
            0,
        )

    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise ApiError(504, "TIMEOUT", "request deadline exhausted")
    try:
        await asyncio.wait_for(state.semaphore.acquire(), timeout=remaining)
    except TimeoutError as exc:
        raise ApiError(503, "PROVIDER_UNAVAILABLE", "gateway at capacity") from exc

    try:
        try:
            result = await state.scheduler.recognize(
                parsed.provider, normalized, parsed.language
            )
        finally:
            state.semaphore.release()
    except SchedulerError as exc:
        latency = int((time.monotonic() - started) * 1000)
        await _record_event(
            session,
            state,
            request_id=request_id,
            context=context,
            provider=exc.provider or parsed.provider,
            success=False,
            error_code=exc.code,
            latency_ms=latency,
            quota_used=0,
            cached=False,
            account_id=exc.account_id,
            image_hash_value=image_digest,
        )
        raise ApiError(exc.status_code, exc.code, exc.message) from exc
    except InputError as exc:
        latency = int((time.monotonic() - started) * 1000)
        await _record_event(
            session,
            state,
            request_id=request_id,
            context=context,
            provider=parsed.provider,
            success=False,
            error_code="BAD_REQUEST",
            latency_ms=latency,
            quota_used=0,
            cached=False,
            account_id=None,
            image_hash_value=image_digest,
        )
        raise ApiError(400, "BAD_REQUEST", str(exc)) from exc

    account = state.registry.get(result.account_id)
    if account is not None:
        state.quota.increment(account)
        state.registry.apply_quota_limit(account, state.quota)

    response_lines: list[dict[str, Any]] = [
        {"text": line.text, "confidence": line.confidence} for line in result.lines
    ]
    payload: dict[str, Any] = {
        "provider": result.provider,
        "text": result.text,
        "lines": response_lines,
    }
    state.cache.set(cache_key, payload)
    latency = int((time.monotonic() - started) * 1000)
    await _record_event(
        session,
        state,
        request_id=request_id,
        context=context,
        provider=result.provider,
        success=True,
        error_code=None,
        latency_ms=latency,
        quota_used=1,
        cached=False,
        account_id=result.account_id,
        image_hash_value=image_digest,
    )
    return _response_payload(
        request_id,
        result.provider,
        result.text,
        response_lines,
        latency,
        False,
        1,
    )


@router.get("/providers")
async def list_providers(
    _: KeyContext = Depends(require_api_key), state: AppState = Depends(get_state)
) -> dict[str, Any]:
    providers = []
    for code in ("baidu", "tencent"):
        accounts = [account for account in state.registry.all() if account.provider == code]
        providers.append(
            {
                "code": code,
                "name": PROVIDER_NAMES[code],
                "available_accounts": state.registry.available_count(code, state.quota),
                "enabled": any(account.enabled for account in accounts),
            }
        )
    return {"providers": providers}


def _utc_start_of_today() -> datetime:
    from app.api.deps import utc_start_of_today

    return utc_start_of_today()


@router.get("/me")
async def me(
    context: KeyContext = Depends(require_api_key),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    requests, quota_used = (
        await session.execute(
            select(
                func.count(UsageEvent.id),
                func.coalesce(func.sum(UsageEvent.quota_used), 0),
            ).where(
                UsageEvent.api_key_id == context.key.id,
                UsageEvent.created_at >= _utc_start_of_today(),
            )
        )
    ).one()
    return {
        "user": context.user.name,
        "key_prefix": context.key.key_prefix,
        "today": {"requests": int(requests), "quota_used": int(quota_used)},
        "limits": {
            "daily_limit": context.key.daily_limit,
            "rpm_limit": context.key.rpm_limit,
        },
    }
