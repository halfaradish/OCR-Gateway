from __future__ import annotations

import asyncio
import ipaddress
import logging
import time
from collections.abc import Iterable, Mapping
from datetime import timedelta
from io import BytesIO
from typing import Any, Literal

from fastapi import APIRouter, Body, Depends, File, Query, Request, Response, UploadFile
from PIL import Image, ImageDraw
from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import __version__
from app.analytics import (
    DAY_BUCKET_FORMAT,
    LOCAL_DAY_MODIFIER,
    TimeWindow,
    parse_window,
    to_local,
    to_utc_naive,
)
from app.api.deps import (
    ADMIN_CSRF_COOKIE,
    ApiError,
    clear_admin_cookies,
    get_session,
    get_state,
    new_csrf_token,
    require_admin,
    set_admin_cookies,
    set_csrf_cookie,
)
from app.core.quota import daily_key, monthly_key
from app.db import utcnow
from app.models import Account, ApiKey, UsageEvent, User
from app.providers.base import PROVIDER_NAMES, AccountRuntime, InputError, RetryableError
from app.providers.templates import DISCLAIMER, QUOTA_TEMPLATES
from app.runtime_settings import (
    FIELD_RULES,
    RuntimeSettings,
    upsert_settings,
    validate_value,
)
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
logger = logging.getLogger(__name__)

REQUIRED_CREDENTIALS: dict[str, tuple[str, ...]] = {
    "baidu": ("app_id", "api_key", "secret_key"),
    "tencent": ("secret_id", "secret_key"),
}


def _client_ip(request: Request, state: AppState) -> str:
    """[impl-review-fix] Resolve the rate-limit identity.

    Behind a reverse proxy every request appears to come from the proxy, which would turn the
    per-IP login limit into a global lockout. Only when the operator explicitly opts in
    (`TRUST_PROXY_HEADERS=true`) do we take the first X-Forwarded-For / X-Real-IP hop, and only
    if it parses as an IP address.
    """
    if state.settings.trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for")
        candidate = forwarded.split(",")[0].strip() if forwarded else ""
        if not candidate:
            candidate = request.headers.get("x-real-ip", "").strip()
        if candidate:
            try:
                ipaddress.ip_address(candidate)
            except ValueError:
                pass
            else:
                return candidate
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


def _quota_usage_from_runtime(
    state: AppState, runtime: AccountRuntime
) -> dict[str, Any]:
    now = utcnow()
    return {
        "daily": {
            "used": state.quota.used(runtime, "daily", now),
            "limit": runtime.quota_daily,
            "period_key": daily_key(now),
        },
        "monthly": {
            "used": state.quota.used(runtime, "monthly", now),
            "limit": runtime.quota_monthly,
            "period_key": monthly_key(now, runtime.reset_day),
        },
        "total": {
            "used": state.quota.used(runtime, "total", now),
            "limit": runtime.quota_total,
            "period_key": "all",
        },
    }


def _quota_usage(state: AppState, account: Account) -> dict[str, Any]:
    """Runtime counters are authoritative; a missing runtime degrades to zero + warning."""
    runtime = state.registry.get(account.id)
    if runtime is not None:
        return _quota_usage_from_runtime(state, runtime)
    logger.warning(
        "account.runtime_missing", extra={"extra_fields": {"account_id": account.id}}
    )
    now = utcnow()
    return {
        "daily": {
            "used": 0,
            "limit": account.quota_daily,
            "period_key": daily_key(now),
        },
        "monthly": {
            "used": 0,
            "limit": account.quota_monthly,
            "period_key": monthly_key(now, account.reset_day),
        },
        "total": {"used": 0, "limit": account.quota_total, "period_key": "all"},
    }


def _account_out(
    state: AppState,
    account: Account,
    owner_names: Mapping[int, str] | None = None,
    owner_name: str | None = None,
) -> dict[str, Any]:
    if owner_name is None and owner_names is not None and account.owner_id is not None:
        owner_name = owner_names.get(account.owner_id)
    return {
        "id": account.id,
        "provider": account.provider,
        "name": account.name,
        "owner_id": account.owner_id,
        "owner_name": owner_name,
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
        "quota_usage": _quota_usage(state, account),
        "reset_day": account.reset_day,
        "state": account.state if account.enabled else "disabled",
        "last_error_code": account.last_error_code,
        "last_error_message": account.last_error_message,
        "ewma_latency_ms": account.ewma_latency_ms,
        "last_used_at": account.last_used_at.isoformat() if account.last_used_at else None,
        "created_at": account.created_at.isoformat(),
        "credential_fields": _masked_credentials(state, account),
    }


async def _user_name_map(session: AsyncSession, user_ids: Iterable[int | None]) -> dict[int, str]:
    ids = {user_id for user_id in user_ids if user_id is not None}
    if not ids:
        return {}
    rows = (await session.execute(select(User.id, User.name).where(User.id.in_(ids)))).all()
    return {int(row[0]): str(row[1]) for row in rows}


async def _account_name_map(
    session: AsyncSession, account_ids: Iterable[int | None]
) -> dict[int, str]:
    ids = {account_id for account_id in account_ids if account_id is not None}
    if not ids:
        return {}
    rows = (
        await session.execute(select(Account.id, Account.name).where(Account.id.in_(ids)))
    ).all()
    return {int(row[0]): str(row[1]) for row in rows}


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
    payload: LoginRequest,
    request: Request,
    response: Response,
    state: AppState = Depends(get_state),
) -> dict[str, Any]:
    ip = _client_ip(request, state)
    if state.login_limiter.blocked(ip):
        logger.info(
            "admin.login.failed",
            extra={"extra_fields": {"ip": ip, "reason": "rate_limited"}},
        )
        raise ApiError(429, "RATE_LIMITED", "too many login attempts")
    if not constant_time_equals(payload.password, state.settings.admin_password):
        state.login_limiter.record_failure(ip)
        logger.info(
            "admin.login.failed",
            extra={"extra_fields": {"ip": ip, "reason": "bad_password"}},
        )
        delay = state.login_limiter.delay()
        if delay:
            await asyncio.sleep(delay)
        raise ApiError(401, "UNAUTHORIZED", "invalid password")
    state.login_limiter.record_success(ip)
    token = create_admin_token(state.settings.master_key_bytes)
    csrf_token = new_csrf_token()
    set_admin_cookies(response, request, state, token, csrf_token)
    logger.info("admin.login.succeeded", extra={"extra_fields": {"ip": ip}})
    return {
        "token": token,
        "expires_in": state.settings.session_ttl_seconds,
        "csrf_token": csrf_token,
    }


@router.get("/me")
async def admin_me(
    request: Request,
    response: Response,
    _: str = Depends(require_admin),
    state: AppState = Depends(get_state),
) -> dict[str, str]:
    payload = {"username": "admin"}
    if getattr(request.state, "admin_auth_source", "bearer") != "cookie":
        # Bearer callers never depend on CSRF; the SPA reads the cookie instead.
        return payload
    csrf_token = request.cookies.get(ADMIN_CSRF_COOKIE)
    if not csrf_token:
        # Older session without the CSRF cookie: a GET may only refresh the cookie.
        csrf_token = new_csrf_token()
        set_csrf_cookie(response, request, state, csrf_token)
    payload["csrf_token"] = csrf_token
    return payload


@router.post("/logout")
async def logout(
    request: Request, _: str = Depends(require_admin), state: AppState = Depends(get_state)
) -> Response:
    cleared = Response(status_code=204)
    clear_admin_cookies(cleared, request, state)
    return cleared


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
    owners = await _user_name_map(session, [row.owner_id for row in rows])
    return [_account_out(state, row, owners) for row in rows]


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
        timeout_ms=payload.timeout_ms or state.runtime.default_timeout_ms,
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
    owner = await session.get(User, account.owner_id) if account.owner_id else None
    return _account_out(state, account, owner_name=owner.name if owner else None)


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
    if "timeout_ms" in data and data["timeout_ms"] is None:
        # accounts.timeout_ms is NOT NULL; "keep the current value" is expressed by omitting.
        raise ApiError(400, "BAD_REQUEST", "timeout_ms cannot be null")
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
    owner = await session.get(User, account.owner_id) if account.owner_id else None
    return _account_out(state, account, owner_name=owner.name if owner else None)


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
    # Drop in-memory counters too: a stale counter would make the next quota flush fail on the
    # missing FK (and leak usage into a reused account id).
    state.quota.reset_account(account_id)
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


def _log_query(path: str, started: float, rows: int) -> None:
    logger.info(
        "admin.query",
        extra={
            "extra_fields": {
                "path": path,
                "duration_ms": int((time.monotonic() - started) * 1000),
                "rows": rows,
            }
        },
    )


def _event_conditions(
    window: TimeWindow,
    *,
    user_id: int | None = None,
    provider: str | None = None,
    account_id: int | None = None,
    success: bool | None = None,
    error_code: str | None = None,
) -> list[Any]:
    conditions: list[Any] = window.conditions(UsageEvent.created_at)
    if user_id is not None:
        conditions.append(UsageEvent.user_id == user_id)
    if provider is not None:
        conditions.append(UsageEvent.provider == provider)
    if account_id is not None:
        conditions.append(UsageEvent.account_id == account_id)
    if success is not None:
        conditions.append(UsageEvent.success.is_(success))
    if error_code is not None:
        conditions.append(UsageEvent.error_code == error_code)
    return conditions


def _success_sum() -> Any:
    return func.coalesce(func.sum(case((UsageEvent.success.is_(True), 1), else_=0)), 0)


def _failure_sum() -> Any:
    return func.coalesce(func.sum(case((UsageEvent.success.is_(False), 1), else_=0)), 0)


def _cached_sum() -> Any:
    return func.coalesce(func.sum(case((UsageEvent.cached.is_(True), 1), else_=0)), 0)


def _avg_latency(value: Any) -> int | None:
    if value is None:
        return None
    return int(round(float(value)))


def _zero_day_bucket() -> dict[str, Any]:
    return {
        "requests": 0,
        "success": 0,
        "failure": 0,
        "cached": 0,
        "quota_used": 0,
        "avg_latency_ms": None,
        "auto_failures": 0,
    }


async def _daily_aggregates(
    session: AsyncSession, window: TimeWindow, **filters: Any
) -> dict[str, dict[str, Any]]:
    """Aggregate per Shanghai local day in SQL; missing days are filled by the callers."""
    day = func.strftime(
        DAY_BUCKET_FORMAT, UsageEvent.created_at, LOCAL_DAY_MODIFIER
    ).label("day")
    statement = (
        select(
            day,
            func.count(UsageEvent.id),
            _success_sum(),
            _failure_sum(),
            _cached_sum(),
            func.coalesce(func.sum(UsageEvent.quota_used), 0),
            func.avg(UsageEvent.latency_ms),
            # `auto` failures are counted separately so today's totals reconcile with the two
            # provider rows (D-A3 / R-ADM-09).
            func.coalesce(
                func.sum(
                    case(
                        (
                            (UsageEvent.provider == "auto")
                            & (UsageEvent.success.is_(False)),
                            1,
                        ),
                        else_=0,
                    )
                ),
                0,
            ),
        )
        .where(*_event_conditions(window, **filters))
        .group_by(day)
    )
    result: dict[str, dict[str, Any]] = {}
    for row in (await session.execute(statement)).all():
        result[str(row[0])] = {
            "requests": int(row[1]),
            "success": int(row[2]),
            "failure": int(row[3]),
            "cached": int(row[4]),
            "quota_used": int(row[5]),
            "avg_latency_ms": _avg_latency(row[6]),
            "auto_failures": int(row[7]),
        }
    return result


@router.get("/overview")
async def overview(
    _: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    state: AppState = Depends(get_state),
) -> dict[str, Any]:
    started = time.monotonic()
    now = utcnow()
    now_local = to_local(now)
    today_start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    series_window = TimeWindow(
        to_utc_naive(today_start_local - timedelta(days=6)), now, False
    )
    today_window = TimeWindow(to_utc_naive(today_start_local), now, False)

    per_day = await _daily_aggregates(session, series_window)
    today = dict(per_day.get(now_local.date().isoformat(), _zero_day_bucket()))
    auto_failures = int(today.pop("auto_failures", 0))

    provider_rows: dict[str, dict[str, int]] = {}
    provider_statement = (
        select(UsageEvent.provider, func.count(UsageEvent.id), _failure_sum())
        .where(*_event_conditions(today_window))
        .group_by(UsageEvent.provider)
    )
    for code, requests, failures in (await session.execute(provider_statement)).all():
        provider_rows[str(code)] = {"requests": int(requests), "failures": int(failures)}

    providers = []
    for code in ("baidu", "tencent"):
        stats = provider_rows.get(code, {"requests": 0, "failures": 0})
        providers.append(
            {
                "code": code,
                "name": PROVIDER_NAMES[code],
                "accounts": len(
                    [item for item in state.registry.all() if item.provider == code]
                ),
                "available_accounts": state.registry.available_count(code, state.quota),
                "today_requests": stats["requests"],
                "today_failures": stats["failures"],
            }
        )
    local_stats = provider_rows.get("local")
    if local_stats is not None:
        providers.append(
            {
                "code": "local",
                "name": PROVIDER_NAMES["local"],
                "accounts": 0,
                "available_accounts": 0,
                "today_requests": local_stats["requests"],
                "today_failures": local_stats["failures"],
            }
        )

    account_rows = [
        {
            "id": runtime.id,
            "name": runtime.name,
            "provider": runtime.provider,
            "state": runtime.state if runtime.enabled else "disabled",
            "quota_usage": _quota_usage_from_runtime(state, runtime),
        }
        for runtime in state.registry.all()
    ]

    error_rows = (
        await session.execute(
            select(UsageEvent)
            .where(UsageEvent.success.is_(False))
            .order_by(UsageEvent.created_at.desc(), UsageEvent.id.desc())
            .limit(10)
        )
    ).scalars().all()
    account_names = await _account_name_map(
        session, [event.account_id for event in error_rows]
    )
    recent_errors = [
        {
            "id": event.id,
            "request_id": event.request_id,
            "provider": event.provider,
            "account_id": event.account_id,
            "account_name": account_names.get(event.account_id)
            if event.account_id is not None
            else None,
            "error_code": event.error_code,
            "latency_ms": event.latency_ms,
            "created_at": event.created_at.isoformat(),
        }
        for event in error_rows
    ]

    series = []
    for day in series_window.local_dates():
        bucket = per_day.get(day.isoformat(), _zero_day_bucket())
        series.append(
            {
                "date": day.isoformat(),
                "requests": bucket["requests"],
                "success": bucket["success"],
                "failure": bucket["failure"],
                "cached": bucket["cached"],
                "quota_used": bucket["quota_used"],
                "avg_latency_ms": bucket["avg_latency_ms"],
            }
        )

    requests_today = today["requests"]
    success_today = today["success"]
    _log_query("overview", started, len(series) + len(account_rows) + len(recent_errors))
    return {
        "generated_at": now_local.isoformat(),
        "today": {
            "requests": requests_today,
            "success": success_today,
            "failure": today["failure"],
            "cached": today["cached"],
            "quota_used": today["quota_used"],
            "success_rate": round(success_today / requests_today, 4)
            if requests_today
            else None,
            "cache_hit_rate": round(today["cached"] / requests_today, 4)
            if requests_today
            else None,
            "avg_latency_ms": today["avg_latency_ms"],
            "auto_failures": auto_failures,
        },
        "providers": providers,
        "accounts": account_rows,
        "recent_errors": recent_errors,
        "cache": {
            "enabled": state.runtime.cache_enabled,
            "entries": len(state.cache),
            "ttl_seconds": state.runtime.cache_ttl_seconds,
            "max_entries": state.runtime.cache_max_entries,
        },
        "series": series,
    }


@router.get("/usage/series")
async def usage_series(
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = Query(default=None),
    user_id: int | None = None,
    provider: str | None = None,
    account_id: int | None = None,
    _: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    started = time.monotonic()
    window = parse_window(from_, to)
    per_day = await _daily_aggregates(
        session, window, user_id=user_id, provider=provider, account_id=account_id
    )
    rows = []
    for day in window.local_dates():
        bucket = per_day.get(day.isoformat(), _zero_day_bucket())
        rows.append(
            {
                "date": day.isoformat(),
                "requests": bucket["requests"],
                "success": bucket["success"],
                "failure": bucket["failure"],
                "cached": bucket["cached"],
                "quota_used": bucket["quota_used"],
                "avg_latency_ms": bucket["avg_latency_ms"],
            }
        )
    _log_query("usage.series", started, len(rows))
    return {
        "from": to_local(window.start).isoformat(),
        "to": to_local(window.end).isoformat(),
        "bucket": "day",
        "rows": rows,
    }


_GROUP_ATTRIBUTE: dict[str, Any] = {
    "user": UsageEvent.user_id,
    "provider": UsageEvent.provider,
    "account": UsageEvent.account_id,
}


@router.get("/usage/summary")
async def usage_summary(
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = Query(default=None),
    group_by: Literal["user", "provider", "account"] = "provider",
    user_id: int | None = None,
    provider: str | None = None,
    account_id: int | None = None,
    _: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    started = time.monotonic()
    window = parse_window(from_, to)
    attribute = _GROUP_ATTRIBUTE[group_by]
    statement = (
        select(
            attribute,
            func.count(UsageEvent.id),
            _success_sum(),
            _failure_sum(),
            _cached_sum(),
            func.coalesce(func.sum(UsageEvent.quota_used), 0),
            func.avg(UsageEvent.latency_ms),
        )
        .where(
            *_event_conditions(
                window, user_id=user_id, provider=provider, account_id=account_id
            )
        )
        .group_by(attribute)
    )
    raw_rows = (await session.execute(statement)).all()

    labels: dict[Any, str] = {}
    if group_by == "user":
        labels = await _user_name_map(session, [row[0] for row in raw_rows])
    elif group_by == "account":
        labels = await _account_name_map(session, [row[0] for row in raw_rows])
    else:
        labels = dict(PROVIDER_NAMES)
        labels["auto"] = "自动路由"

    rows = [
        {
            "key": row[0],
            "label": labels.get(row[0]) if row[0] is not None else None,
            "requests": int(row[1]),
            "success": int(row[2]),
            "failure": int(row[3]),
            "cached": int(row[4]),
            "quota_used": int(row[5]),
            "avg_latency_ms": _avg_latency(row[6]),
        }
        for row in raw_rows
    ]
    # Ascending by key with the "deleted entity" bucket (null key) last.
    rows.sort(key=lambda item: (item["key"] is None, item["key"] or 0))
    _log_query("usage.summary", started, len(rows))
    return {
        "from": window.start.isoformat(),
        "to": window.end.isoformat(),
        "group_by": group_by,
        "rows": rows,
    }


@router.get("/logs")
async def list_logs(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = Query(default=None),
    success: bool | None = None,
    provider: str | None = None,
    error_code: str | None = None,
    user_id: int | None = None,
    account_id: int | None = None,
    _: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    started = time.monotonic()
    window = parse_window(from_, to)
    conditions = _event_conditions(
        window,
        user_id=user_id,
        provider=provider,
        account_id=account_id,
        success=success,
        error_code=error_code,
    )
    total = int(
        (
            await session.execute(select(func.count(UsageEvent.id)).where(*conditions))
        ).scalar_one()
    )
    rows = (
        await session.execute(
            select(UsageEvent)
            .where(*conditions)
            .order_by(UsageEvent.id.desc())
            .offset(offset)
            .limit(limit)
        )
    ).scalars().all()
    user_names = await _user_name_map(session, [event.user_id for event in rows])
    account_names = await _account_name_map(session, [event.account_id for event in rows])
    _log_query("logs", started, len(rows))
    return {
        "limit": limit,
        "offset": offset,
        "total": total,
        "rows": [
            {
                "id": event.id,
                "request_id": event.request_id,
                "user_id": event.user_id,
                "user_name": user_names.get(event.user_id)
                if event.user_id is not None
                else None,
                "api_key_id": event.api_key_id,
                "account_id": event.account_id,
                "account_name": account_names.get(event.account_id)
                if event.account_id is not None
                else None,
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


def _readonly_settings(state: AppState) -> dict[str, Any]:
    return {
        "api_auth_enabled": True,
        "version": __version__,
        "max_upload_bytes": state.settings.max_upload_bytes,
        "max_image_pixels": state.settings.max_image_pixels,
        "max_concurrent_requests": state.settings.max_concurrent_requests,
        "session_ttl_seconds": state.settings.session_ttl_seconds,
        "frontend_built": state.frontend_built,
    }


async def _apply_settings(
    state: AppState, updates: dict[str, Any]
) -> tuple[RuntimeSettings, bool]:
    """Serialize merge+commit+apply; the runtime swap happens only after the commit returns."""
    async with state.settings_lock:
        async with state.session_factory() as session:
            await upsert_settings(session, updates)
            await session.commit()
        merged = RuntimeSettings(**{**state.runtime.as_dict(), **updates})
        local_changed = merged.local_ocr_enabled != state.runtime.local_ocr_enabled
        cache_cleared = state.cache.reconfigure(
            merged.cache_enabled, merged.cache_max_entries, merged.cache_ttl_seconds
        )
        if local_changed:
            state.cache.clear()
            cache_cleared = True
        state.runtime = merged
        await state.local_engine.set_enabled(merged.local_ocr_enabled)
        return merged, cache_cleared


@router.get("/settings")
async def get_settings(
    _: str = Depends(require_admin), state: AppState = Depends(get_state)
) -> dict[str, Any]:
    return {"editable": state.runtime.as_dict(), "readonly": _readonly_settings(state)}


@router.get("/local-ocr/status")
async def local_ocr_status(
    _: str = Depends(require_admin), state: AppState = Depends(get_state)
) -> dict[str, Any]:
    return state.local_engine.status(
        total_budget_ms=state.runtime.request_deadline_ms
    )


@router.put("/settings")
async def update_settings(
    payload: dict[str, Any] = Body(...),
    _: str = Depends(require_admin),
    state: AppState = Depends(get_state),
) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    updates: dict[str, Any] = {}
    for key, value in payload.items():
        if key not in FIELD_RULES:
            errors.append({"field": key, "message": f"未知设置项：{key}。"})
            continue
        ok, normalized, message = validate_value(key, value)
        if not ok:
            errors.append({"field": key, "message": message})
        else:
            updates[key] = normalized
    if errors:
        logger.info(
            "admin.settings.rejected",
            extra={"extra_fields": {"fields": [item["field"] for item in errors]}},
        )
        raise ApiError(400, "BAD_REQUEST", "invalid settings", fields=errors)
    try:
        runtime, cache_cleared = await _apply_settings(state, updates)
    except Exception as exc:  # noqa: BLE001 - DB failure must not leak internals
        logger.exception("admin.settings.write_failed")
        raise ApiError(
            500, "INTERNAL_ERROR", "failed to save settings", fields=None
        ) from exc
    logger.info(
        "admin.settings.updated", extra={"extra_fields": {"keys": sorted(updates)}}
    )
    return {"settings": runtime.as_dict(), "cache_cleared": cache_cleared}
