from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime, timedelta
from io import BytesIO
from typing import Any, Literal

from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile
from PIL import Image, ImageDraw
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ApiError, get_session, get_state, require_admin
from app.core.quota import SHANGHAI
from app.db import utcnow
from app.models import Account, ApiKey, UsageEvent, User
from app.providers.base import InputError, RetryableError
from app.providers.templates import DISCLAIMER, QUOTA_TEMPLATES
from app.schemas import (
    AccountCreate,
    AccountUpdate,
    ApiKeyCreate,
    ApiKeyUpdate,
    LoginRequest,
    UserCreate,
    UserUpdate,
)
from app.security import (
    constant_time_equals,
    create_admin_token,
    decrypt_credentials,
    display_prefix,
    encrypt_credentials,
    generate_api_key,
    hash_api_key,
    mask_secret,
)
from app.state import AppState
from app.utils.images import normalize_image

router = APIRouter(prefix="/api/admin")

REQUIRED_CREDENTIALS: dict[str, tuple[str, ...]] = {
    "baidu": ("app_id", "api_key", "secret_key"),
    "tencent": ("secret_id", "secret_key"),
}


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _validate_credentials(provider: str, credentials: dict[str, str]) -> dict[str, str]:
    if not isinstance(credentials, dict):
        raise ApiError(400, "BAD_REQUEST", "credentials must be an object")
    for field in REQUIRED_CREDENTIALS[provider]:
        value = credentials.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ApiError(400, "BAD_REQUEST", f"credentials.{field} is required")
    return {str(key): str(value) for key, value in credentials.items()}


def _masked_credentials(state: AppState, account: Account) -> dict[str, str]:
    try:
        credentials = decrypt_credentials(state.settings.master_key_bytes, account.credentials_enc)
    except Exception:  # noqa: BLE001 - never leak a decrypt failure to the client
        return {field: "****" for field in REQUIRED_CREDENTIALS[account.provider]}
    return {key: mask_secret(str(value)) for key, value in credentials.items()}


def _account_out(state: AppState, account: Account) -> dict[str, Any]:
    return {
        "id": account.id,
        "provider": account.provider,
        "name": account.name,
        "owner_id": account.owner_id,
        "priority": account.priority,
        "weight": account.weight,
        "enabled": account.enabled,
        "timeout_ms": account.timeout_ms,
        "max_concurrency": account.max_concurrency,
        "qps_limit": account.qps_limit,
        "quota_daily": account.quota_daily,
        "quota_monthly": account.quota_monthly,
        "quota_total": account.quota_total,
        "quota_unit": account.quota_unit,
        "reset_day": account.reset_day,
        "state": account.state if account.enabled else "disabled",
        "last_error_code": account.last_error_code,
        "last_error_message": account.last_error_message,
        "ewma_latency_ms": account.ewma_latency_ms,
        "last_used_at": account.last_used_at.isoformat() if account.last_used_at else None,
        "created_at": account.created_at.isoformat(),
        "credential_fields": _masked_credentials(state, account),
    }


def _key_out(key: ApiKey) -> dict[str, Any]:
    return {
        "id": key.id,
        "user_id": key.user_id,
        "name": key.name,
        "key_prefix": key.key_prefix,
        "enabled": key.enabled,
        "daily_limit": key.daily_limit,
        "rpm_limit": key.rpm_limit,
        "last_used_at": key.last_used_at.isoformat() if key.last_used_at else None,
        "created_at": key.created_at.isoformat(),
    }


def _user_out(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "name": user.name,
        "enabled": user.enabled,
        "created_at": user.created_at.isoformat(),
    }


@router.post("/login")
async def login(
    payload: LoginRequest, request: Request, state: AppState = Depends(get_state)
) -> dict[str, Any]:
    ip = _client_ip(request)
    if state.login_limiter.blocked(ip):
        raise ApiError(429, "RATE_LIMITED", "too many login attempts")
    if not constant_time_equals(payload.password, state.settings.admin_password):
        state.login_limiter.record_failure(ip)
        delay = state.login_limiter.delay()
        if delay:
            await asyncio.sleep(delay)
        raise ApiError(401, "UNAUTHORIZED", "invalid password")
    state.login_limiter.record_success(ip)
    token = create_admin_token(state.settings.master_key_bytes)
    return {"token": token, "expires_in": state.settings.session_ttl_seconds}


@router.get("/me")
async def admin_me(_: str = Depends(require_admin)) -> dict[str, str]:
    return {"username": "admin"}


@router.get("/users")
async def list_users(
    _: str = Depends(require_admin), session: AsyncSession = Depends(get_session)
) -> list[dict[str, Any]]:
    rows = (await session.execute(select(User).order_by(User.id))).scalars().all()
    return [_user_out(row) for row in rows]


@router.post("/users")
async def create_user(
    payload: UserCreate,
    _: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    user = User(name=payload.name, enabled=True)
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ApiError(400, "BAD_REQUEST", "user name already exists") from exc
    await session.refresh(user)
    return _user_out(user)


@router.patch("/users/{user_id}")
async def update_user(
    user_id: int,
    payload: UserUpdate,
    _: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    user = await session.get(User, user_id)
    if user is None:
        raise ApiError(404, "NOT_FOUND", "user not found")
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(user, key, value)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ApiError(400, "BAD_REQUEST", "user name already exists") from exc
    await session.refresh(user)
    return _user_out(user)


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    _: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> Response:
    user = await session.get(User, user_id)
    if user is None:
        raise ApiError(404, "NOT_FOUND", "user not found")
    await session.delete(user)
    await session.commit()
    return Response(status_code=204)


@router.get("/api-keys")
async def list_api_keys(
    _: str = Depends(require_admin), session: AsyncSession = Depends(get_session)
) -> list[dict[str, Any]]:
    rows = (await session.execute(select(ApiKey).order_by(ApiKey.id))).scalars().all()
    return [_key_out(row) for row in rows]


@router.post("/api-keys")
async def create_api_key(
    payload: ApiKeyCreate,
    _: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    user = await session.get(User, payload.user_id)
    if user is None:
        raise ApiError(400, "BAD_REQUEST", "user not found")
    plaintext = generate_api_key()
    key = ApiKey(
        user_id=payload.user_id,
        name=payload.name,
        key_prefix=display_prefix(plaintext),
        key_hash=hash_api_key(plaintext),
        enabled=True,
        daily_limit=payload.daily_limit,
        rpm_limit=payload.rpm_limit,
    )
    session.add(key)
    await session.commit()
    await session.refresh(key)
    result = _key_out(key)
    result["key"] = plaintext
    return result


@router.patch("/api-keys/{key_id}")
async def update_api_key(
    key_id: int,
    payload: ApiKeyUpdate,
    _: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    key = await session.get(ApiKey, key_id)
    if key is None:
        raise ApiError(404, "NOT_FOUND", "api key not found")
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(key, field, value)
    await session.commit()
    await session.refresh(key)
    return _key_out(key)


@router.delete("/api-keys/{key_id}")
async def delete_api_key(
    key_id: int,
    _: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> Response:
    key = await session.get(ApiKey, key_id)
    if key is None:
        raise ApiError(404, "NOT_FOUND", "api key not found")
    await session.delete(key)
    await session.commit()
    return Response(status_code=204)


@router.get("/accounts")
async def list_accounts(
    _: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    state: AppState = Depends(get_state),
) -> list[dict[str, Any]]:
    rows = (await session.execute(select(Account).order_by(Account.id))).scalars().all()
    return [_account_out(state, row) for row in rows]


@router.post("/accounts")
async def create_account(
    payload: AccountCreate,
    _: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    state: AppState = Depends(get_state),
) -> dict[str, Any]:
    credentials = _validate_credentials(payload.provider, payload.credentials)
    if payload.owner_id is not None:
        if await session.get(User, payload.owner_id) is None:
            raise ApiError(400, "BAD_REQUEST", "owner_id not found")
    account = Account(
        provider=payload.provider,
        name=payload.name,
        owner_id=payload.owner_id,
        credentials_enc=encrypt_credentials(state.settings.master_key_bytes, credentials),
        priority=payload.priority,
        weight=payload.weight,
        enabled=payload.enabled,
        timeout_ms=payload.timeout_ms,
        max_concurrency=payload.max_concurrency,
        qps_limit=payload.qps_limit,
        quota_daily=payload.quota_daily,
        quota_monthly=payload.quota_monthly,
        quota_total=payload.quota_total,
        quota_unit="image",
        reset_day=payload.reset_day,
        state="active",
        ewma_latency_ms=1000.0,
    )
    session.add(account)
    await session.commit()
    await session.refresh(account)
    state.registry.register(account)
    return _account_out(state, account)


@router.patch("/accounts/{account_id}")
async def update_account(
    account_id: int,
    payload: AccountUpdate,
    _: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    state: AppState = Depends(get_state),
) -> dict[str, Any]:
    account = await session.get(Account, account_id)
    if account is None:
        raise ApiError(404, "NOT_FOUND", "account not found")
    data = payload.model_dump(exclude_unset=True)
    credentials = data.pop("credentials", None)
    if credentials is not None:
        validated = _validate_credentials(account.provider, credentials)
        account.credentials_enc = encrypt_credentials(
            state.settings.master_key_bytes, validated
        )
    for field, value in data.items():
        setattr(account, field, value)
    account.updated_at = utcnow()
    await session.commit()
    await session.refresh(account)
    state.registry.update(account)
    if credentials is not None:
        state.adapters[account.provider].invalidate(account.id)
    return _account_out(state, account)


@router.delete("/accounts/{account_id}")
async def delete_account(
    account_id: int,
    _: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    state: AppState = Depends(get_state),
) -> Response:
    account = await session.get(Account, account_id)
    if account is None:
        raise ApiError(404, "NOT_FOUND", "account not found")
    provider = account.provider
    await session.delete(account)
    await session.commit()
    state.registry.remove(account_id)
    state.adapters[provider].invalidate(account_id)
    return Response(status_code=204)


@router.post("/accounts/{account_id}/reset-state")
async def reset_account_state(
    account_id: int,
    _: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    state: AppState = Depends(get_state),
) -> dict[str, str]:
    account = await session.get(Account, account_id)
    if account is None:
        raise ApiError(404, "NOT_FOUND", "account not found")
    account.state = "active"
    account.cooldown_until = None
    account.last_error_code = None
    account.last_error_message = None
    account.updated_at = utcnow()
    await state.quota.reset_account_db(session, account_id)
    await session.commit()
    state.quota.reset_account(account_id)
    state.registry.reset_state(account_id)
    return {"state": "active"}


def _sample_image() -> bytes:
    image = Image.new("RGB", (320, 120), "white")
    draw = ImageDraw.Draw(image)
    draw.text((20, 40), "OCR TEST 123", fill="black")
    out = BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


@router.post("/accounts/{account_id}/test")
async def test_account(
    account_id: int,
    _: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    state: AppState = Depends(get_state),
    file: UploadFile | None = File(default=None),
) -> dict[str, Any]:
    account = await session.get(Account, account_id)
    if account is None:
        raise ApiError(404, "NOT_FOUND", "account not found")
    runtime = state.registry.get(account_id)
    if runtime is None:
        # Registry may have not loaded a just-created row in a stale process; rebuild it.
        state.registry.register(account)
        runtime = state.registry.get(account_id)
    assert runtime is not None
    data = await file.read(state.settings.max_upload_bytes + 1) if file else _sample_image()
    if len(data) > state.settings.max_upload_bytes:
        raise ApiError(400, "BAD_REQUEST", "image exceeds the upload size limit")
    try:
        normalized = normalize_image(
            data,
            account.provider,
            state.settings.max_upload_bytes,
            state.settings.max_image_pixels,
        )
    except InputError as exc:
        raise ApiError(400, "BAD_REQUEST", str(exc)) from exc
    adapter = state.adapters[account.provider]
    started = time.monotonic()
    try:
        result = await adapter.recognize(
            runtime, normalized, "zh", account.timeout_ms / 1000.0
        )
    except RetryableError as exc:
        return {
            "ok": False,
            "provider": account.provider,
            "error_code": exc.kind.value,
            "message": exc.message,
            "latency_ms": int((time.monotonic() - started) * 1000),
        }
    except InputError as exc:
        return {
            "ok": False,
            "provider": account.provider,
            "error_code": "BAD_REQUEST",
            "message": str(exc),
            "latency_ms": int((time.monotonic() - started) * 1000),
        }
    return {
        "ok": True,
        "provider": account.provider,
        "text": result.text,
        "latency_ms": int((time.monotonic() - started) * 1000),
    }


@router.get("/quota-templates")
async def quota_templates(_: str = Depends(require_admin)) -> dict[str, Any]:
    return {"disclaimer": DISCLAIMER, "providers": list(QUOTA_TEMPLATES.values())}


def _parse_time(raw: str | None, default: datetime) -> datetime:
    if not raw:
        return default
    try:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ApiError(400, "BAD_REQUEST", "invalid time filter") from exc
    if value.tzinfo is None:
        value = value.replace(tzinfo=SHANGHAI)
    return value.astimezone(UTC).replace(tzinfo=None)


@router.get("/usage/summary")
async def usage_summary(
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = Query(default=None),
    group_by: Literal["user", "provider", "account"] = "provider",
    _: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    end = _parse_time(to, datetime.now(UTC).replace(tzinfo=None))
    start = _parse_time(from_, end - timedelta(days=7))
    rows = (
        await session.execute(
            select(UsageEvent).where(
                UsageEvent.created_at >= start, UsageEvent.created_at <= end
            )
        )
    ).scalars().all()
    attribute = {"user": "user_id", "provider": "provider", "account": "account_id"}[group_by]
    buckets: dict[Any, dict[str, Any]] = {}
    for event in rows:
        key = getattr(event, attribute)
        bucket = buckets.setdefault(
            key,
            {"key": key, "requests": 0, "success": 0, "failure": 0, "cached": 0, "quota_used": 0},
        )
        bucket["requests"] += 1
        if event.success:
            bucket["success"] += 1
        else:
            bucket["failure"] += 1
        if event.cached:
            bucket["cached"] += 1
        bucket["quota_used"] += event.quota_used
    return {
        "from": start.isoformat(),
        "to": end.isoformat(),
        "group_by": group_by,
        "rows": list(buckets.values()),
    }


@router.get("/logs")
async def list_logs(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    success: bool | None = None,
    provider: str | None = None,
    _: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    statement = select(UsageEvent).order_by(UsageEvent.id.desc())
    if success is not None:
        statement = statement.where(UsageEvent.success == success)
    if provider is not None:
        statement = statement.where(UsageEvent.provider == provider)
    rows = (
        await session.execute(statement.offset(offset).limit(limit))
    ).scalars().all()
    return {
        "limit": limit,
        "offset": offset,
        "rows": [
            {
                "id": event.id,
                "request_id": event.request_id,
                "user_id": event.user_id,
                "api_key_id": event.api_key_id,
                "account_id": event.account_id,
                "provider": event.provider,
                "success": event.success,
                "error_code": event.error_code,
                "latency_ms": event.latency_ms,
                "quota_used": event.quota_used,
                "cached": event.cached,
                "image_hash": event.image_hash,
                "created_at": event.created_at.isoformat(),
            }
            for event in rows
        ],
    }


@router.post("/cache/clear")
async def clear_cache(
    _: str = Depends(require_admin), state: AppState = Depends(get_state)
) -> dict[str, int]:
    return {"cleared": state.cache.clear()}
